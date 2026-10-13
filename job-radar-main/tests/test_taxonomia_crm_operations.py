"""Regressão da taxonomia CRM/Operations e dos critérios de elegibilidade."""

from core.config import (
    DIAS_MAXIMOS_PUBLICACAO,
    GRUPOS_CARGOS,
    KEYWORDS,
    PRIORIDADES_CARGO,
    TERMOS_BUSCA,
    TERMOS_PRIORITARIOS,
    _grupo_do_termo,
)


def test_pesos_dos_grupos_somam_100_e_respeitam_proposta():
    assert {chave: grupo["peso"] for chave, grupo in GRUPOS_CARGOS.items()} == {
        "A": 40,
        "B": 40,
        "C": 20,
    }
    assert sum(grupo["peso"] for grupo in GRUPOS_CARGOS.values()) == 100


def test_familias_novas_entram_no_filtro_e_na_busca():
    titulos = [
        "CRM Operations Analyst",
        "CS Ops Analyst",
        "Business Operations Analyst",
        "Sales Operations Analyst",
        "RevOps Analyst Jr",
        "SaaS Implementation Analyst",
        "Customer Onboarding Specialist",
        "Marketing Operations Analyst",
        "Marketing Automation Specialist",
        "SaaS Support Analyst",
    ]
    normalizadas = {termo.casefold() for termo in KEYWORDS}
    termos_busca = set(TERMOS_BUSCA)
    for titulo in titulos:
        assert titulo.casefold() in normalizadas
        assert titulo.casefold() in termos_busca


def test_prioridade_dos_grupos_e_decrescente():
    assert PRIORIDADES_CARGO["CRM Operations Analyst"] == 3
    assert PRIORIDADES_CARGO["RevOps Analyst Jr"] == 2
    assert PRIORIDADES_CARGO["Marketing Operations Analyst"] == 1


def test_familias_principais_sao_buscadas_em_todo_ciclo():
    # Esses termos ficam fora do rodízio, para a expansão não depender de
    # esperar uma volta completa pela lista crescente de keywords.
    assert {
        "crm operations",
        "cs ops",
        "business operations",
        "sales operations",
        "revops",
        "marketing operations",
    }.issubset(set(TERMOS_PRIORITARIOS))


def test_recencia_brasil_permanece_em_cinco_dias():
    assert DIAS_MAXIMOS_PUBLICACAO == 5



def test_rodizio_distribui_termos_na_proporcao_40_40_20():
    primeiros = TERMOS_BUSCA[:5]
    assert [_grupo_do_termo(termo) for termo in primeiros] == [
        "A", "A", "B", "B", "C"
    ]
    # O intercalamento não pode perder nem duplicar termos.
    assert len(TERMOS_BUSCA) == len(set(TERMOS_BUSCA))
