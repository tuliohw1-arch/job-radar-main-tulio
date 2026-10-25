"""Verificação do filtro de modalidade nos detalhes públicos do LinkedIn."""
import pytest

from scrapers.linkedin_modalidade import (
    URL_DETALHE,
    classificar_modalidade_html,
    extrair_id_vaga_linkedin,
    ler_modalidade_anuncio,
)


@pytest.mark.parametrize(
    "html, esperado",
    [
        (
            "<div>São Paulo, Av. Paulista | 100% presencial | CLT</div>"
            "<p>Esta vaga é 100% presencial. Não há modelo híbrido nem remoto.</p>",
            "Presencial",
        ),
        (
            "<div>Modelo de trabalho: Híbrido - Rua Itapeva, 26</div>",
            "Híbrido",
        ),
        (
            "<div>✅ Modelo de Trabalho: Hibrido</div>",
            "Híbrido",
        ),
        (
            "<div>Modalidade: Remoto - 100% home office no Brasil</div>",
            "Remoto",
        ),
        ("<div>Local: São Paulo, SP | Tempo integral</div>", ""),
    ],
)
def test_classifica_modalidade_do_texto_visivel(html, esperado):
    assert classificar_modalidade_html(html) == esperado


def test_hibrido_ou_presencial_prevalece_sobre_mencao_remota():
    assert classificar_modalidade_html(
        "<p>Modelo de trabalho: Híbrido. A equipe atende clientes remotamente.</p>"
    ) == "Híbrido"
    assert classificar_modalidade_html(
        "<p>100% presencial; possibilidade futura de trabalho remoto.</p>"
    ) == "Presencial"


@pytest.mark.parametrize(
    "link, esperado",
    [
        ("https://www.linkedin.com/jobs/view/analista-4482787122/", "4482787122"),
        ("https://br.linkedin.com/jobs/view/4482787122?trk=abc", "4482787122"),
        ("https://www.linkedin.com/jobs/view/sem-id/", ""),
    ],
)
def test_extrai_id_do_permalink(link, esperado):
    assert extrair_id_vaga_linkedin(link) == esperado


class _Resposta:
    def __init__(self, status, corpo):
        self.status = status
        self._corpo = corpo

    def text(self):
        return self._corpo


class _Request:
    def __init__(self, resposta=None, erro=None):
        self.resposta = resposta
        self.erro = erro
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append((url, kwargs))
        if self.erro:
            raise self.erro
        return self.resposta


def test_le_modalidade_no_endpoint_de_detalhe_e_cacheia_por_link():
    request = _Request(_Resposta(200, "<div>Modelo de Trabalho: Híbrido</div>"))
    link = "https://www.linkedin.com/jobs/view/analista-4481944321/"
    cache = {}

    resultado = ler_modalidade_anuncio(request, link, cache)
    repetido = ler_modalidade_anuncio(request, link, cache)

    assert resultado == ("Híbrido", "Híbrido")
    assert repetido == resultado
    assert len(request.urls) == 1
    url, kwargs = request.urls[0]
    assert url == URL_DETALHE.format("4481944321")
    assert kwargs["timeout"] > 0
    assert kwargs["headers"]["User-Agent"]


@pytest.mark.parametrize(
    "request_context, link, esperado",
    [
        (_Request(_Resposta(503, "")), "https://www.linkedin.com/jobs/view/x-12345678", ("", "HTTP 503")),
        (_Request(erro=TimeoutError()), "https://www.linkedin.com/jobs/view/x-12345678", ("", "falha ao ler o detalhe")),
        (_Request(_Resposta(200, "<div>São Paulo, SP</div>")), "https://www.linkedin.com/jobs/view/x-12345678", ("", "modalidade não declarada no anúncio")),
        (_Request(_Resposta(200, "<div>Modelo de trabalho: Presencial</div>")), "https://www.linkedin.com/jobs/view/sem-id", ("", "ID do anúncio ausente")),
    ],
)
def test_falha_ou_modalidade_ausente_e_rejeitada(request_context, link, esperado):
    assert ler_modalidade_anuncio(request_context, link) == esperado
