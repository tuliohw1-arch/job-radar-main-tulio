from datetime import date, datetime, timezone
import time

import requests

from core.job import Job
from core.logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()

# Busca atual chamada pelo portal público da Sólides. A resposta tem
# {count, totalPages, currentPage, data}; o detalhe de cada vaga usa
# https://vagas.solides.com.br/vaga/{id}.
URL_API = "https://vagas.solides.com.br/api/vacancies"

# O portal público atual usa 14 resultados por página.
TAKE = 14

# MEDIDO: take so aceita 10. Testado com 20, 30, 50, 60 e 100 -- todos
# devolvem count=0, nao so lista vazia. O tamanho de pagina e fixo.
TAKE = 10

# Para quando uma página inteira passou do limite de idade; a API atual
# ordena por data decrescente. 30 dias coincide com o limite de idade usado
# pelo filtro de vagas.
DIAS_PARA_PARAR = 30

# Trava para evitar paginação sem fim se a ordenação ou as datas mudarem.
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
    # O redirectLink pode vir com o subdomínio da empresa malformado.
    # O portal atual publica os detalhes no caminho /vaga/{id}.
    id_vaga = str(vaga.get("id") or "").strip()
    link = f"https://vagas.solides.com.br/vaga/{id_vaga}" if id_vaga.isdigit() else ""
    if not titulo or not link:
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
                resposta = requests.get(
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
                if resposta.status_code in (403, 404):
                    self._api_indisponivel = True
                break

            try:
                corpo = resposta.json()
            except ValueError:
                logger.warning(f"[Solides] Resposta não-JSON em '{termo}' (página {pagina}).")
                break

            # O endpoint atual devolve a lista em corpo["data"]; aceitar também
            # o envelope antigo {data: {count, totalPages, data}}.
            envelope = corpo.get("data")
            dados = envelope if isinstance(envelope, dict) else corpo
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
