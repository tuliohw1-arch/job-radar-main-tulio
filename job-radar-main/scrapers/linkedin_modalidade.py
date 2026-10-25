"""Verificação fail-closed da modalidade no anúncio público do LinkedIn.

O filtro de busca f_WT=2 serve para descobrir candidatos; não é prova de que
o anúncio é remoto. A resposta do endpoint público de detalhe contém o texto
completo da vaga e é a fonte usada aqui para confirmar a modalidade antes de
criar um Job que possa chegar ao filtro/notificação.
"""
from html.parser import HTMLParser
import re
from urllib.parse import urlparse

from core.job import _e_remoto, _modalidade_contraditoria, _normalizar

URL_DETALHE = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{}"
TIMEOUT_DETALHE_MS = 20_000
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


class _TextoVisivelHTML(HTMLParser):
    """Coleta texto/atributos acessíveis do fragmento HTML do anúncio."""

    _TAGS_IGNORADAS = {"script", "style", "noscript", "svg"}
    _ATRIBUTOS_TEXTO = {"aria-label", "title"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self._ignorar = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self._TAGS_IGNORADAS:
            self._ignorar += 1
            return
        if self._ignorar:
            return
        for nome, valor in attrs:
            if nome.lower() in self._ATRIBUTOS_TEXTO and valor:
                self.partes.append(valor)

    def handle_endtag(self, tag):
        if tag.lower() in self._TAGS_IGNORADAS and self._ignorar:
            self._ignorar -= 1

    def handle_data(self, data):
        if not self._ignorar and data and data.strip():
            self.partes.append(data.strip())


def classificar_modalidade_html(html: str) -> str:
    """Retorna Remoto/Híbrido/Presencial; string vazia quando não verificável.

    Regra fail-closed: híbrido ou presencial explícito sempre vence qualquer
    menção a remoto; sem sinal remoto explícito, a vaga também não é aprovada.
    """
    if not html or not html.strip():
        return ""
    parser = _TextoVisivelHTML()
    parser.feed(html)
    texto = _normalizar(" ".join(parser.partes))

    contraditoria = _modalidade_contraditoria(texto)
    if contraditoria:
        return contraditoria
    if _e_remoto(texto):
        return "Remoto"
    return ""


def extrair_id_vaga_linkedin(link: str) -> str:
    """Extrai o ID numérico do permalink LinkedIn (com ou sem slug)."""
    caminho = urlparse(link).path.rstrip("/")
    for segmento in reversed(caminho.split("/")):
        if segmento.isdigit():
            return segmento
        match = re.search(r"-(\d+)$", segmento)
        if match:
            return match.group(1)
    return ""


def ler_modalidade_anuncio(
    request_context,
    link: str,
    cache: dict[str, tuple[str, str]] | None = None,
) -> tuple[str, str]:
    """Consulta o detalhe público e devolve (modalidade, motivo).

    Falha de rede, resposta não-200, ID ausente ou página sem modalidade
    explícita resultam em modalidade vazia. A vaga será descartada pelo
    scraper; o resultado é armazenado no cache para não repetir chamadas
    quando o mesmo link aparecer em mais de uma busca do ciclo.
    """
    if cache is not None and link in cache:
        return cache[link]

    job_id = extrair_id_vaga_linkedin(link)
    if not job_id:
        resultado = ("", "ID do anúncio ausente")
    else:
        try:
            resposta = request_context.get(
                URL_DETALHE.format(job_id),
                timeout=TIMEOUT_DETALHE_MS,
                headers=HEADERS,
            )
            if resposta.status != 200:
                resultado = ("", f"HTTP {resposta.status}")
            else:
                modalidade = classificar_modalidade_html(resposta.text())
                resultado = (
                    modalidade,
                    modalidade or "modalidade não declarada no anúncio",
                )
        except Exception:
            resultado = ("", "falha ao ler o detalhe")
    if cache is not None:
        cache[link] = resultado
    return resultado
