"""Regressão da ampliação controlada do pool de cargos do perfil Brasil.

A expansão deve alcançar portas de entrada próximas de CRM sem aceitar
atendimento genérico, vendas ou funções sem relação com o ciclo do cliente.
O filtro de modalidade e o limite de recência são exercitados separadamente
pelas suítes existentes.
"""

from core.job import Job
from core.perfis import PERFIL_BR

REGRAS = PERFIL_BR.regras


def vaga(titulo: str, local: str = "Remoto - Brasil", modalidade: str = "Remoto") -> Job:
    return Job(
        titulo=titulo,
        empresa="Empresa SaaS",
        local=local,
        link="https://example.com/jobs/" + titulo.lower().replace(" ", "-"),
        site="Teste",
        modalidade=modalidade,
    )


def test_novos_cargos_proximos_de_crm_sao_aceitos():
    titulos = [
        "Analista de CRM Júnior",
        "Analista de CRM Junior",
        "Analista Jr de CRM",
        "CRM Jr",
        "Analista CRM Jr",
        "Analista Jr CRM",
        "CRM Analyst Junior",
        "CRM Marketing Analyst",
        "Assistente CRM",
        "Customer Success Analyst Jr",
        "Analista CS Jr",
        "CS Analyst Junior",
        "Customer Success Specialist Jr",
        "Analista Jr de Customer Success",
        "Customer Success Associate Jr",
        "Assistente de Customer Success",
        "Analista de Sucesso do Cliente Jr",
        "Customer Success Jr",
        "Customer Success Junior",
        "Analista de Sucesso do Cliente Júnior",
        "Customer Experience Analyst Jr",
        "CX Analyst Jr",
        "Analista CX Junior",
        "Customer Experience Specialist Jr",
        "Analista Jr de CX",
        "Analista de Customer Experience Jr",
        "Analista de Experiência do Cliente Jr",
        "CX Jr",
        "Analista de CX Junior",
        "Customer Experience Jr",
        "Customer Experience Associate",
        "Customer Onboarding Specialist",
        "Analista de Onboarding",
        "Implementation Analyst",
        "Analista de Implantação",
        "Customer Operations Analyst",
        "CS Ops Analyst",
        "Analista de Suporte ao Cliente Jr",
        "Marketing Automation Analyst",
        "Lifecycle Marketing Analyst",
        "Retention Marketing Analyst",
    ]
    for titulo in titulos:
        assert vaga(titulo).combina_com(REGRAS), f"deveria aceitar: {titulo}"


def test_pool_expandido_continua_exigindo_modalidade_remota():
    assert not vaga("Customer Success Jr", local="São Paulo, SP", modalidade="Híbrido").combina_com(REGRAS)
    assert not vaga("Customer Onboarding Specialist", local="Belo Horizonte, MG", modalidade="Presencial").combina_com(REGRAS)


def test_expansao_nao_libera_atendimento_ou_vendas_genericos():
    titulos = [
        "Analista de Atendimento ao Cliente",
        "Customer Support Representative",
        "Atendente de SAC",
        "SDR - Sales Development Representative",
        "Executivo de Vendas",
        "Analista Financeiro Jr",
    ]
    for titulo in titulos:
        assert not vaga(titulo).combina_com(REGRAS), f"não deveria aceitar: {titulo}"


def test_prioridade_do_ranking_preserva_crm_acima_das_portas_de_entrada():
    crm = vaga("Analista de CRM Jr").pontuar_relevancia(REGRAS)
    customer_success = vaga("Customer Success Jr").pontuar_relevancia(REGRAS)
    onboarding = vaga("Customer Onboarding Specialist").pontuar_relevancia(REGRAS)
    assert crm > customer_success > onboarding


def test_variantes_junior_estao_nas_keywords_e_nos_termos_de_busca():
    from core.config import KEYWORDS, TERMOS_BUSCA, TERMOS_PRIORITARIOS

    keywords_normalizadas = {termo.casefold() for termo in KEYWORDS}
    buscas_normalizadas = {termo.casefold() for termo in TERMOS_BUSCA}
    prioritarias_normalizadas = {termo.casefold() for termo in TERMOS_PRIORITARIOS}

    esperadas = [
        "Analista CRM Jr",
        "CRM Analyst Junior",
        "Analista CS Jr",
        "Customer Success Analyst Junior",
        "CX Analyst Jr",
        "Analista Jr de CX",
    ]
    for termo in esperadas:
        assert termo.casefold() in keywords_normalizadas, f"keyword ausente: {termo}"
        assert termo.casefold() in buscas_normalizadas, f"termo de busca ausente: {termo}"

    assert "analista crm jr" in prioritarias_normalizadas
    assert "analista cs jr" in prioritarias_normalizadas
    assert "analista de cx jr" in prioritarias_normalizadas
