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
        "Customer Success Jr",
        "Customer Success Junior",
        "Analista de Sucesso do Cliente Júnior",
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
