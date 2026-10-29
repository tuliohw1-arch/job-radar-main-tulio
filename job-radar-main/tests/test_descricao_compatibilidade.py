"""Testes de extração de descrição e classificação explicável sem rede real."""
import requests

from core.compatibilidade import LIMIAR_COMPATIBILIDADE_MINIMA, pontuar_compatibilidade
from core.descricao import extrair_descricao, analisar_secoes
from core.job import Job


class RespostaFake:
    def __init__(self, html="", status=200, content_type="text/html; charset=utf-8", url="https://example.com/job"):
        self.text = html
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        self.url = url
        self.reason = "simulated"

    def raise_for_status(self):
        if self.status_code >= 400:
            erro = requests.HTTPError("simulated")
            erro.response = self
            raise erro


class SessaoFake:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.response


DESCRICAO = (
    "Responsabilidades: acompanhar chamados corporativos, SLAs e indicadores; "
    "produzir relatórios operacionais e apoiar usuários internos. "
    "Requisitos obrigatórios: experiência com Jira, Excel e atendimento a usuários. "
    "Desejáveis: Power BI e conhecimento de CRM. " * 3
)


def test_extrai_descricao_completa_de_jsonld_jobposting():
    html = (
        '<html><head><script type="application/ld+json">'
        + __import__("json").dumps({"@context": "https://schema.org", "@type": "JobPosting", "description": DESCRICAO})
        + "</script></head><body>vaga</body></html>"
    )
    session = SessaoFake(RespostaFake(html))
    resultado = extrair_descricao("https://example.com/job", session=session)
    assert resultado["status_extracao"] == "completa"
    assert resultado["origem_descricao"] == "jsonld"
    assert "Jira" in resultado["descricao"]
    assert session.calls[0][1]["timeout"] > 0


def test_extrai_descricao_por_meta_quando_estrutura_jsonld_nao_existe():
    html = f'<html><head><meta property="og:description" content="{DESCRICAO}"></head></html>'
    resultado = extrair_descricao("https://example.com/job", session=SessaoFake(RespostaFake(html)))
    assert resultado["status_extracao"] == "completa"
    assert resultado["origem_descricao"] == "meta"


def test_descricao_curta_fica_marcada_como_incompleta_nao_completa():
    html = '<html><head><meta name="description" content="Vaga com suporte técnico e atendimento."></head></html>'
    resultado = extrair_descricao("https://example.com/job", session=SessaoFake(RespostaFake(html)))
    assert resultado["status_extracao"] == "incompleta"
    assert resultado["descricao"]
    assert resultado["erro_extracao"] == ""


def test_pagina_sem_descricao_e_marcada_indisponivel():
    resultado = extrair_descricao("https://example.com/job", session=SessaoFake(RespostaFake("<html><body>Menu rodape</body></html>")), renderizar_dinamico=False)
    assert resultado["status_extracao"] == "indisponivel"
    assert resultado["descricao"] == ""
    assert resultado["erro_extracao"] == "descricao_nao_encontrada_ou_curta"


def test_http_403_registra_status_sem_expor_detalhes_sensiveis():
    resultado = extrair_descricao("https://example.com/job", session=SessaoFake(RespostaFake(status=403)), renderizar_dinamico=False)
    assert resultado["status_extracao"] == "indisponivel"
    assert resultado["erro_extracao"] == "http_403"


def test_timeout_e_registrado_sem_excecao_para_o_pipeline():
    resultado = extrair_descricao("https://example.com/job", session=SessaoFake(error=requests.Timeout()), renderizar_dinamico=False)
    assert resultado["status_extracao"] == "indisponivel"
    assert resultado["erro_extracao"] == "timeout"


def test_parseia_responsabilidades_requisitos_obrigatorios_e_desejaveis():
    secoes = analisar_secoes(
        "Responsabilidades\nAcompanhar chamados e SLAs\n"
        "Requisitos obrigatórios\nJira e Excel\n"
        "Diferenciais desejáveis\nPower BI"
    )
    assert any("chamados" in s for s in secoes["responsabilidades"])
    assert any("Jira" in s for s in secoes["requisitos_obrigatorios"])
    assert any("Power BI" in s for s in secoes["requisitos_desejaveis"])


def _job(descricao=DESCRICAO, titulo="Analista de Suporte Júnior", modalidade="Remoto"):
    return Job(
        titulo=titulo,
        empresa="Empresa Teste",
        local="Brasil",
        link="https://example.com/job",
        site="Teste",
        modalidade=modalidade,
        descricao=descricao,
        status_extracao="completa" if len(descricao) >= 180 else "incompleta",
        requisitos_obrigatorios=["Jira", "Excel"],
    )


def test_score_compatibilidade_fica_entre_zero_e_cem_e_explica_sinais():
    resultado = pontuar_compatibilidade(_job())
    assert 0 <= resultado["score"] <= 100
    assert resultado["score"] >= LIMIAR_COMPATIBILIDADE_MINIMA
    assert resultado["criterios_positivos"]
    assert resultado["justificativa"]
    assert isinstance(resultado["lacunas"], list)


def test_descricao_indisponivel_nao_e_tratada_como_completa_e_limita_confianca():
    resultado = pontuar_compatibilidade(_job(descricao="", titulo="Analista de CRM Júnior"))
    assert resultado["score"] < LIMIAR_COMPATIBILIDADE_MINIMA
    assert resultado["informacoes_insuficientes"] is True
    assert any("Descrição ausente" in item for item in resultado["lacunas"])


def test_sql_obrigatorio_e_registrado_como_lacuna_nao_como_competencia_comprovada():
    job = _job()
    job.requisitos_obrigatorios = ["SQL avançado obrigatório", "Jira"]
    resultado = pontuar_compatibilidade(job)
    assert resultado["requisitos_obrigatorios_nao_atendidos"]
    assert any("SQL" in item for item in resultado["requisitos_obrigatorios_nao_atendidos"])
