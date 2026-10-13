from datetime import date, datetime, timezone
import json
import re
import time
from urllib.parse import quote, urlsplit

import requests

from core.job import Job
from core.logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()

# API que o proprio portal da Solides chama pra montar a busca.
#
# MEDIDO (2026-08-29): o scraper anterior abria um NAVEGADOR e raspava HTML
# com "li:has(h2 a)", lendo 3 paginas de 10 = teto de 30 vagas por termo, e
# levava ~7 minutos por ciclo (45 cargas de pagina). Esta API responde, pro
# mesmo termo "analista de dados":
#
#     {"data": {"count": 205, "totalPages": 21}}
#
# 205 contra 30. Mesma historia da Gupy: a fonte sempre teve volume, o
# scraper e que so via o comeco.
#
# O que a troca resolve, alem do alcance:
#   - paginacao deixa de ser adivinhada CONTANDO cards (mecanismo que ja
#     produziu alarme falso aqui, ver 9520409). A resposta declara count e
#     totalPages.
#   - state.code vem com a SIGLA pronta ("ES"), melhor que a Gupy, que da o
#     estado por extenso.
#   - createdAt ja vem em AAAA-MM-DD, o formato que Job.publicacao_antiga
#     espera.
#   - sem navegador: nada de seletor pra quebrar, e o ciclo encurta muito.
#
# O QUE NAO MUDOU, de proposito: o Job montado, o filtro, a pontuacao, a
# deduplicacao e o formato do log. So a camada de busca foi trocada.
URL_API = "https://apigw.solides.com.br/jobs/v3/portal-vacancies-new"

# MEDIDO: take so aceita 10. Testado com 20, 30, 50, 60 e 100 -- todos
# devolvem count=0, nao so lista vazia. O tamanho de pagina e fixo.
TAKE = 10

# ONDE PARAR DE PAGINAR.
#
# A primeira versao usava teto fixo de 15 paginas, escolhido porque o unico
# termo que eu tinha medido tinha 21. Ao ver "power bi: 523 vagas em 53
# paginas, lidas as 15 primeiras" no log, minha leitura foi que o teto estava
# APERTADO e vaga estava sendo perdida.
#
# MEDIDO (30/08), sondando os 45 termos do perfil BR: era o contrario.
#
#   termo                 vagas  pags   pagina em que a vaga passa de 7 dias
#   sql                     642    65          7
#   power bi                523    53          6
#   python                  347    35          5
#   analista de dados       205    21          4
#   business intelligence   138    14          3
#
# NENHUM termo passa da pagina 7 antes das vagas ficarem com mais de uma
# semana. O teto de 15 nunca cortou vaga nova -- ele lia 9 paginas a mais de
# vaga VELHA. Estava frouxo, nao apertado.
#
# Por isso o criterio deixou de ser "quantas paginas" e passou a ser "ate
# quando". A lista vem da mais recente pra mais antiga, entao basta parar
# quando as vagas ficarem velhas demais pra interessar. Custo medido, em
# requisicoes por termo:
#
#     teto fixo de 15 paginas   4,6
#     parar apos  7 dias        2,2
#     parar apos 14 dias        3,0
#     parar apos 30 dias        4,8   <- escolhido
#
# 30 dias custa praticamente o mesmo que o teto de hoje, mas distribui muito
# melhor: le fundo onde ha volume novo (power bi vai ate a pagina 18) e sai
# na pagina 2 onde o termo e parado. E se adapta sozinho quando o mercado
# muda, sem precisar recalibrar numero nenhum.
#
# 30 dias tambem e o limiar que Job.publicacao_antiga ja usa -- vaga mais
# velha que isso ganha o aviso de "pode ja estar preenchida" e sai do alerta
# imediato. Ler alem disso seria buscar exatamente o que o filtro desprioriza.
DIAS_PARA_PARAR = 30

# Trava de seguranca, nao criterio: impede laco infinito se a API passar a
# devolver data invalida ou parar de ordenar por data. O termo mais fundo
# medido (sql) precisa de 19 paginas pra passar de 30 dias.
MAX_PAGINAS = 30

PAUSA_ENTRE_PAGINAS = 0.5
TIMEOUT = 30
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# jobType da API -> vocabulario que o filtro ja usa (ver core/job.py).
_MODALIDADE = {
    "presencial": "Presencial",
    "hibrido": "Híbrido",
    "híbrido": "Híbrido",
    "remoto": "Remoto",
    "home office": "Remoto",
    "homeoffice": "Remoto",
}


def extrair_vagas_html(html: str) -> list[dict]:
    """Extrai objetos de vagas do stream Flight do Next.js sem depender do DOM.

    O HTML público da Sólides incorpora segmentos como
    self.__next_f.push([1, "..."]). Cada segmento é uma string JavaScript
    escapada; json.loads decodifica os escapes antes de procurar os objetos.
    Retorna somente objetos com campos mínimos reconhecíveis como vaga.
    """
    segmentos = re.findall(
        r"self\.__next_f\.push\(\[1,\s*(\"(?:\\.|[^\"\\])*\")\s*\]\)",
        html,
    )
    partes = []
    for segmento in segmentos:
        try:
            partes.append(json.loads(segmento))
        except (json.JSONDecodeError, TypeError):
            continue
    payload = "\n".join(partes)
    if not payload:
        return []

    decoder = json.JSONDecoder()
    vagas = []
    vistos = set()
    # IDs/títulos aparecem em objetos JSON completos no stream decodificado.
    for match in re.finditer(r'"id"\s*:\s*(\d+)\s*,\s*"title"\s*:', payload):
        inicio = payload.rfind("{", 0, match.start())
        if inicio < 0:
            continue
        try:
            objeto, _ = decoder.raw_decode(payload[inicio:])
        except json.JSONDecodeError:
            continue
        if not isinstance(objeto, dict):
            continue
        if not objeto.get("title") or not objeto.get("redirectLink"):
            continue
        if "jobType" not in objeto and "homeOffice" not in objeto:
            continue
        identidade = str(objeto.get("id"))
        if identidade not in vistos:
            vistos.add(identidade)
            vagas.append(objeto)
    return vagas


def url_busca_publica(termo: str) -> str:
    """Constrói a rota pública observada no portal para o termo de busca."""
    slug = re.sub(r"[^a-z0-9]+", "-", termo.lower()).strip("-")
    return "https://vagas.solides.com.br/vagas/" + quote(slug, safe="-")


def pagina_toda_antiga(itens: list[dict], dias: int, hoje: date | None = None) -> bool:
    """A vaga MAIS NOVA desta pagina ja passou do limite de idade?

    A lista da API vem ordenada da mais recente pra mais antiga, entao a
    partir daqui so vem coisa ainda mais velha -- da pra parar.

    Devolve False quando nenhuma data da pra ler: sem data nao ha o que
    concluir, e parar por engano custa vaga. Errar pro lado de continuar
    custa uma requisicao.
    """
    hoje = hoje or datetime.now(timezone.utc).date()
    idades = []
    for vaga in itens:
        bruto = (vaga.get("createdAt") or "").strip()[:10]
        try:
            idades.append((hoje - date.fromisoformat(bruto)).days)
        except ValueError:
            continue
    if not idades:
        return False
    return min(idades) > dias


def montar_local(vaga: dict) -> str:
    """Monta `local` como "Cidade - UF", que e um dos formatos que o filtro
    ja reconhece.

    A Solides entrega a SIGLA em state.code ("ES"), diferente da Gupy, que
    so da o nome por extenso. Sigla e o caminho mais curto e mais seguro na
    conferencia de UF (ver _uf_declarada em core/job.py).
    """
    cidade = ((vaga.get("city") or {}).get("name") or "").strip()
    sigla = ((vaga.get("state") or {}).get("code") or "").strip()
    if cidade and sigla:
        return f"{cidade} - {sigla}"
    return cidade or sigla or "Não informado"


def montar_modalidade(vaga: dict) -> str:
    """Traduz jobType. homeOffice entra como reforco: sao campos
    independentes, e vaga remota as vezes chega com so um deles."""
    bruto = (vaga.get("jobType") or "").strip().lower()
    if bruto in _MODALIDADE:
        return _MODALIDADE[bruto]
    if vaga.get("homeOffice") is True:
        return "Remoto"
    return ""


def montar_job(vaga: dict) -> Job | None:
    """Converte um item da API num Job. None quando falta o essencial.

    Funcao pura de proposito: e o que da pra testar sem rede, e onde mora
    todo o risco da troca -- mapear campo errado nao quebra nada, so muda
    silenciosamente o que e aprovado.
    """
    titulo = (vaga.get("title") or "").strip()
    link = (vaga.get("redirectLink") or "").strip()
    if not titulo or not link:
        return None

    # Não propagar URLs evidentemente quebradas do payload público.
    # Ex.: https://empresa./vacancies/123 — o hostname não contém domínio
    # registrável/TLD e não é um link de candidatura utilizável.
    try:
        parsed_link = urlsplit(link)
        hostname = (parsed_link.hostname or "").rstrip(".")
        if (
            parsed_link.scheme not in ("http", "https")
            or not parsed_link.netloc
            or "." not in hostname
            or hostname.startswith(".")
            or hostname.endswith(".")
        ):
            logger.warning(
                f"[Solides] Vaga descartada por link inválido: "
                f"título={titulo!r}, link={link!r}."
            )
            return None
    except ValueError:
        logger.warning(
            f"[Solides] Vaga descartada por URL inválida: "
            f"título={titulo!r}, link={link!r}."
        )
        return None

    return Job(
        titulo=titulo,
        empresa=(vaga.get("companyName") or "Não informado").strip(),
        local=montar_local(vaga),
        link=link,
        site="Solides",
        publicado_em=(vaga.get("createdAt") or "").strip()[:10],
        modalidade=montar_modalidade(vaga),
    )


class SolidesScraper(BaseScraper):
    """Busca vagas na API publica do portal da Sólides."""

    def __init__(self, termos_busca: list[str]):
        self.termos_busca = termos_busca
        self._api_indisponivel = False
        self._session = requests.Session()
        self._sessao_inicializada = False

    def buscar_vagas(self) -> list[Job]:
        vagas: list[Job] = []
        for termo in self.termos_busca:
            if self._api_indisponivel:
                logger.warning("[Solides] Busca interrompida: endpoint indisponível; evitando repetir a mesma falha em cada termo.")
                break
            vagas.extend(self._buscar_termo(termo))
        logger.info(f"[Solides] {len(vagas)} vaga(s) encontrada(s) no total")
        return vagas

    def _buscar_termo(self, termo: str) -> list[Job]:
        logger.info(f"[Solides] Buscando: {termo}")
        vagas: list[Job] = []
        total_paginas = None
        total = None

        for pagina in range(1, MAX_PAGINAS + 1):
            try:
                if not self._sessao_inicializada:
                    portal = self._session.get(
                        "https://vagas.solides.com.br/",
                        timeout=TIMEOUT,
                        headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"},
                    )
                    self._sessao_inicializada = True
                    logger.info(f"[Solides] Portal público inicializado (HTTP {portal.status_code}).")
                resposta = self._session.get(
                    URL_API,
                    params={"title": termo, "take": TAKE, "page": pagina},
                    timeout=TIMEOUT,
                    headers={"User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7", "Referer": "https://vagas.solides.com.br/", "Origin": "https://vagas.solides.com.br"},
                )
            except Exception as erro:
                logger.error(f"[Solides] Erro ao buscar '{termo}' (página {pagina}): {erro}")
                break

            if resposta.status_code != 200:
                detalhe = " ".join((resposta.text or "").split())[:240]
                logger.warning(
                    f"[Solides] Status {resposta.status_code} em '{termo}' "
                    f"(página {pagina}); URL={resposta.url}; corpo={detalhe!r}. "
                    "Não é busca vazia."
                )
                if pagina == 1 and resposta.status_code in (403, 404):
                    try:
                        pagina_publica = self._session.get(
                            url_busca_publica(termo),
                            timeout=TIMEOUT,
                            headers={
                                "User-Agent": UA,
                                "Accept": "text/html,application/xhtml+xml",
                                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                                "Referer": "https://vagas.solides.com.br/",
                            },
                        )
                        if pagina_publica.status_code == 200:
                            itens_html = extrair_vagas_html(pagina_publica.text)
                            logger.info(
                                f"[Solides] HTML público '{termo}': "
                                f"{len(itens_html)} vaga(s) extraída(s)."
                            )
                            validas = 0
                            for item in itens_html:
                                job = montar_job(item)
                                if job is not None:
                                    vagas.append(job)
                                    validas += 1
                            if itens_html and validas == 0:
                                logger.warning(
                                    f"[Solides] Fallback encontrou {len(itens_html)} "
                                    "registro(s), mas nenhum tinha link de candidatura válido."
                                )
                            return vagas
                        logger.warning(
                            f"[Solides] Fallback HTML retornou HTTP "
                            f"{pagina_publica.status_code} para '{termo}'."
                        )
                    except Exception as erro:
                        logger.warning(
                            f"[Solides] Fallback HTML falhou para '{termo}': {erro}"
                        )
                if resposta.status_code in (403, 404):
                    self._api_indisponivel = True
                break

            try:
                corpo = resposta.json()
            except ValueError:
                logger.warning(f"[Solides] Resposta não-JSON em '{termo}' (página {pagina}).")
                break

            dados = corpo.get("data") or {}
            lote = dados.get("data") or []

            if total_paginas is None:
                total = dados.get("count", 0)
                total_paginas = dados.get("totalPages", 0)
                if not total:
                    logger.info(f"[Solides] 0 resultados reais para '{termo}'.")
                    break

            for item in lote:
                job = montar_job(item)
                if job is not None:
                    vagas.append(job)

            if not lote or pagina >= total_paginas:
                break

            if pagina_toda_antiga(lote, DIAS_PARA_PARAR):
                logger.info(
                    f"[Solides] '{termo}': parou na página {pagina} de {total_paginas} "
                    f"— daqui pra frente só vaga com mais de {DIAS_PARA_PARAR} dias."
                )
                break

            time.sleep(PAUSA_ENTRE_PAGINAS)

        if total_paginas and total_paginas > MAX_PAGINAS:
            logger.warning(
                f"[Solides] '{termo}': bateu a trava de {MAX_PAGINAS} páginas sem "
                f"chegar em vaga de {DIAS_PARA_PARAR} dias ({total_paginas} páginas no "
                "total) — a API pode ter parado de ordenar por data."
            )
        return vagas
