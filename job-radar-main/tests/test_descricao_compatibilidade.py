"""Testes de extração de descrição e classificação explicável sem rede real."""
import requests

from core.compatibilidade import LIMIAR_COMPATIBILIDADE_MINIMA, pontuar_compatibilidade
from core.descricao import detectar_senioridade, extrair_descricao, extrair_ferramentas, analisar_secoes
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


def test_meta_description_e_tratada_como_resumo_incompleto():
    html = f'<html><head><meta property="og:description" content="{DESCRICAO}"></head></html>'
    resultado = extrair_descricao("https://example.com/job", session=SessaoFake(RespostaFake(html)))
    assert resultado["status_extracao"] == "incompleta"
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



def test_fallback_playwright_captura_conteudo_renderizado(monkeypatch):
    from types import SimpleNamespace
    import playwright.sync_api

    texto = "Responsabilidades: " + ("acompanhar chamados e relatórios operacionais. " * 12)

    class Page:
        url = "https://example.com/final"
        def goto(self, *args, **kwargs):
            return None
        def locator(self, *_):
            return SimpleNamespace(inner_text=lambda **__: texto)

    class Browser:
        def new_page(self):
            return Page()
        def close(self):
            return None

    class Context:
        def __enter__(self):
            return SimpleNamespace(chromium=SimpleNamespace(launch=lambda **__: Browser()))
        def __exit__(self, *args):
            return False

    monkeypatch.setattr(playwright.sync_api, "sync_playwright", lambda: Context())
    resultado = extrair_descricao(
        "https://example.com/job",
        session=SessaoFake(RespostaFake("<html><body>conteúdo carregado por JavaScript</body></html>")),
        renderizar_dinamico=True,
    )
    assert resultado["status_extracao"] == "completa"
    assert resultado["origem_descricao"] == "playwright_visivel"
    assert resultado["url_final"] == "https://example.com/final"



def test_helper_integrado_enriquece_job_e_grava_score_explicavel():
    from main import _enriquecer_e_pontuar

    job = _job()
    job.origem_descricao = "payload_teste"
    _enriquecer_e_pontuar(job, {})
    assert job.status_extracao == "completa"
    assert 0 <= job.compatibilidade_score <= 100
    assert job.compatibilidade_justificativa
    assert job.compatibilidade_criterios
    assert isinstance(job.compatibilidade_lacunas, list)



def test_extrai_ferramentas_e_senioridade_sem_inferir_proficiencia_do_candidato():
    ferramentas = extrair_ferramentas("Requisitos: Excel, Power BI, Jira e SQL.")
    assert {"Excel", "Power BI", "Jira", "SQL"}.issubset(set(ferramentas))
    assert detectar_senioridade("A oportunidade é para perfil júnior.") == "Júnior"


def test_modalidade_da_descricao_complementa_e_pode_contradizer_o_card():
    remoto = Job(
        titulo="Analista de Operações",
        empresa="Empresa",
        local="Brasil",
        link="https://example.com/remote",
        site="Teste",
        descricao="This is a fully remote role with responsibilities in operations.",
    )
    assert remoto.modalidade == "Remoto"

    hibrido = Job(
        titulo="Analista de Operações",
        empresa="Empresa",
        local="Brasil",
        link="https://example.com/hybrid",
        site="Teste",
        modalidade="Remoto",
        descricao="This is a hybrid role with three days in the office.",
    )
    assert hibrido.modalidade == "Híbrido"



def test_modalidade_hibrida_da_pagina_substitui_card_remoto_no_enriquecimento(monkeypatch):
    import main

    descricao = (
        "Responsibilities: support operations and reporting. "
        "This is a hybrid role requiring three days in the office. "
    ) * 4
    monkeypatch.setattr(main, "extrair_descricao", lambda url: {
        "descricao": descricao,
        "status_extracao": "completa",
        "origem_descricao": "html_visivel",
        "erro_extracao": "",
        "url_final": url,
    })
    job = Job(
        titulo="Analista de Operações Júnior",
        empresa="Empresa",
        local="Remote - Brazil",
        link="https://example.com/hybrid-role",
        site="Teste",
        modalidade="Remoto",
    )
    main._enriquecer_e_pontuar(job, {})
    assert job.modalidade == "Híbrido"



def test_remote_em_url_ou_titulo_ou_descricao_eh_elegivel():
    casos = [
        Job(titulo="Analista de CRM Jr", empresa="A", local="Brasil", link="https://jobs.example.com/remote-crm", site="Teste"),
        Job(titulo="Remote Customer Support Analyst", empresa="A", local="Brasil", link="https://jobs.example.com/123", site="Teste"),
        Job(titulo="Analista de Operações Jr", empresa="A", local="Brasil", link="https://jobs.example.com/123", site="Teste", descricao="Oportunidade 100% homeoffice. " * 12),
    ]
    assert all(v.modalidade == "Remoto" for v in casos)


def test_remote_no_link_nao_supera_contradicao_hibrida_ou_presencial():
    hibrida = Job(
        titulo="Remote CRM Analyst",
        empresa="A",
        local="Brasil",
        link="https://jobs.example.com/remote",
        site="Teste",
        descricao="This is a hybrid position with three days in office. " * 5,
    )
    presencial = Job(
        titulo="Analista de CRM",
        empresa="A",
        local="Brasil",
        link="https://jobs.example.com/homeoffice",
        site="Teste",
        descricao="This role is on-site at the office every day. " * 5,
    )
    assert hibrida.modalidade == "Híbrido"
    assert presencial.modalidade == "Presencial"


def test_score_minimo_agora_aceita_qualquer_sinal_profissional():
    from core.compatibilidade import LIMIAR_COMPATIBILIDADE_MINIMA
    assert LIMIAR_COMPATIBILIDADE_MINIMA == 1
    vaga = _job(descricao="Responsabilidades: acompanhar chamados e SLAs. " * 5)
    resultado = pontuar_compatibilidade(vaga)
    assert resultado["score"] >= 1
