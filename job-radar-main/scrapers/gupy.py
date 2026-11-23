import time

import requests

from core.job import Job
from core.logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()

# API atual de busca pública da Gupy.
# Com limit=10 a resposta informa o total correto; valores maiores fazem
# a API reportar total=100 e podem interromper a paginação antes do fim.
URL_API = "https://portal.gupy.io/api/job-search/jobs"

# Tamanho que mantém correta a paginação do endpoint atual.
LIMITE_POR_PAGINA = 10

# A API aceita limit alto (testado com 100). 100 por requisicao cobre a
# maioria dos termos numa chamada so.
LIMITE_POR_PAGINA = 100

# Teto de vagas por termo. Para termos concorridos, isso limita a leitura
# às 30 páginas mais recentes, sem percorrer todo o histórico.
MAX_VAGAS_POR_TERMO = 300

TIMEOUT = 30
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# workplaceType da API -> vocabulario que o filtro ja usa (ver
# _FLAGS_REMOTO e as regras de cidade em core/job.py).
_MODALIDADE = {
    "on-site": "Presencial",
    "onsite": "Presencial",
    "hybrid": "Híbrido",
    "remote": "Remoto",
}


def montar_local(vaga: dict) -> str:
    """Monta o campo `local` a partir de city/state.

    A API devolve o estado por EXTENSO ("São Paulo", "Ceará"), nao a sigla.
    Isso funciona porque a guarda de UF passou a ler estado por extenso em
    5e91895 -- antes desse commit, "Campina Grande, Paraná" passaria como se
    fosse a Campina Grande da Paraiba. Os testes cobrem exatamente esse caso.
    """
    cidade = (vaga.get("city") or "").strip()
    estado = (vaga.get("state") or "").strip()
    if cidade and estado:
        return f"{cidade}, {estado}"
    return cidade or estado or "Não informado"


def montar_modalidade(vaga: dict) -> str:
    """Traduz workplaceType. isRemoteWork entra como reforco: sao dois campos
    independentes na resposta, e vaga remota as vezes chega com um so."""
    bruto = (vaga.get("workplaceType") or "").strip().lower()
    if bruto in _MODALIDADE:
        return _MODALIDADE[bruto]
    if vaga.get("isRemoteWork") is True:
        return "Remoto"
    return ""


def montar_job(vaga: dict) -> Job | None:
    """Converte um item da API num Job. None quando falta o essencial.

    Funcao pura de proposito: e o que da pra testar sem rede, e onde mora
    todo o risco da troca (mapear campo errado passa despercebido).
    """
    titulo = (vaga.get("name") or "").strip()
    link = (vaga.get("jobUrl") or "").strip()
    if not titulo or not link:
        return None

    # publishedDate vem como "2026-08-28T21:28:28.868Z". Job.publicacao_antiga
    # e publicado_em_legivel esperam a data ISO pura (ver core/job.py).
    publicado = (vaga.get("publishedDate") or "")[:10]

    return Job(
        titulo=titulo,
        empresa=(vaga.get("careerPageName") or "Não informado").strip(),
        local=montar_local(vaga),
        link=link,
        site="Gupy",
        publicado_em=publicado,
        modalidade=montar_modalidade(vaga),
        descricao=(vaga.get("description") or vaga.get("jobDescription") or vaga.get("responsibilities") or "").strip(),
        origem_descricao="api_payload" if any(vaga.get(k) for k in ("description", "jobDescription", "responsibilities")) else "",
        status_extracao="completa" if len((vaga.get("description") or vaga.get("jobDescription") or vaga.get("responsibilities") or "").strip()) >= 180 else ("incompleta" if (vaga.get("description") or vaga.get("jobDescription") or vaga.get("responsibilities") or "").strip() else "indisponivel"),
    )


class GupyScraper(BaseScraper):
    """Busca vagas na API publica do portal da Gupy."""

    def __init__(self, termos_busca: list[str]):
        self.termos_busca = termos_busca
        self._api_indisponivel = False

    def buscar_vagas(self) -> list[Job]:
        vagas: list[Job] = []
        for termo in self.termos_busca:
            if self._api_indisponivel:
                logger.warning("[Gupy] Busca interrompida: endpoint indisponível; evitando repetir a mesma falha em cada termo.")
                break
            vagas.extend(self._buscar_termo(termo))
        logger.info(f"[Gupy] {len(vagas)} vaga(s) encontrada(s) no total")
        return vagas

    def _buscar_termo(self, termo: str) -> list[Job]:
        logger.info(f"[Gupy] Buscando: {termo}")
        vagas: list[Job] = []
        offset = 0
        total = None

        while offset < MAX_VAGAS_POR_TERMO:
            try:
                resposta = requests.get(
                    URL_API,
                    params={"jobName": termo, "limit": LIMITE_POR_PAGINA, "offset": offset},
                    timeout=TIMEOUT,
                    headers={"User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7", "Referer": "https://portal.gupy.io/", "Origin": "https://portal.gupy.io"},
                )
            except Exception as erro:
                logger.error(f"[Gupy] Erro ao buscar '{termo}' (offset {offset}): {erro}")
                break

            if resposta.status_code != 200:
                detalhe = " ".join((resposta.text or "").split())[:240]
                logger.warning(
                    f"[Gupy] Status {resposta.status_code} em '{termo}' (offset {offset}); "
                    f"URL={resposta.url}; corpo={detalhe!r}. Não é busca vazia."
                )
                if resposta.status_code in (403, 404):
                    self._api_indisponivel = True
                break

            try:
                dados = resposta.json()
            except ValueError:
                logger.warning(f"[Gupy] Resposta não-JSON em '{termo}' (offset {offset}).")
                break

            lote = dados.get("data") or []
            if total is None:
                total = (dados.get("pagination") or {}).get("total", 0)
                if not total:
                    logger.info(f"[Gupy] 0 resultados reais para '{termo}'.")
                    break

            for item in lote:
                job = montar_job(item)
                if job is not None:
                    vagas.append(job)

            offset += LIMITE_POR_PAGINA
            if not lote or offset >= total:
                break
            time.sleep(1)

        if total and total > MAX_VAGAS_POR_TERMO:
            logger.info(
                f"[Gupy] '{termo}': {total} vagas no total, lidas as {MAX_VAGAS_POR_TERMO} "
                "mais recentes (teto do scraper, não fim dos resultados)."
            )
        return vagas
