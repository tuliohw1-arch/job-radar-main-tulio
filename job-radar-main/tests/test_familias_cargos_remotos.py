"""Cobertura das famílias profissionais ampliadas para o perfil Brasil remoto."""

import pytest

from core.config import (
    DIAS_MAXIMOS_PUBLICACAO,
    KEYWORDS,
    KEYWORDS_SUPORTE_OPERACOES_TI,
    KEYWORDS_OPERACOES_PROCESSOS_PROJETOS,
    KEYWORDS_CUSTOMER_SUCCESS_COMPLEMENTAR,
    KEYWORDS_DADOS_BI,
    TERMOS_BUSCA,
    TERMOS_PRIORITARIOS,
)
from core.job import Job
from core.perfis import PERFIL_BR

REGRAS = PERFIL_BR.regras


def vaga(titulo, local="Remote - Brazil", modalidade="Remoto"):
    return Job(
        titulo=titulo,
        empresa="Empresa de teste",
        local=local,
        link="https://example.com/jobs/" + titulo.lower().replace(" ", "-"),
        site="Teste",
        publicado_em="2026-10-28",
        modalidade=modalidade,
    )


@pytest.mark.parametrize("titulo", [
    "Analista de TI Júnior",
    "Analista de Suporte Técnico Júnior",
    "Analista de Service Desk Júnior",
    "Analista de Operações de TI Júnior",
    "Analista de Suporte a Sistemas",
    "Analista de Implantação de Sistemas Júnior",
    "Técnico de Suporte Remoto",
    "Analista de Operações Júnior",
    "Analista de Processos Júnior",
    "Analista de Operações de Negócio Júnior",
    "Analista de Projetos Júnior",
    "Assistente de Projetos",
    "Analista de PMO Júnior",
    "Analista de Implantação Júnior",
    "Analista de Requisitos Júnior",
    "Customer Operations",
    "Analista de Onboarding Júnior",
    "Analista de Implantação de Clientes",
    "Analista de Customer Experience Júnior",
    "Analista de Atendimento ao Cliente Júnior",
    "Analista de Qualidade de Atendimento",
    "Analista de Indicadores",
    "Analista de Dados Júnior",
    "Analista de BI Júnior",
    "Assistente de BI",
    "Analista de Relatórios",
    "Analista de Performance Operacional",
    "Analista de Dados de Clientes Júnior",
])
def test_novas_familias_sao_aceitas_quando_remotas_no_brasil(titulo):
    assert vaga(titulo).combina_com(REGRAS), f"deveria aceitar: {titulo}"


@pytest.mark.parametrize("titulo", [
    "Junior IT Support Analyst",
    "Junior Operations Analyst",
    "Junior Project Analyst",
    "Junior Data Analyst",
    "BI Analyst Junior",
    "Reporting Analyst",
    "Customer Service Quality Analyst",
])
def test_variantes_em_ingles_sao_aceitas(titulo):
    assert vaga(titulo).combina_com(REGRAS), f"deveria aceitar: {titulo}"


@pytest.mark.parametrize("titulo", [
    "SDR - Sales Development Representative",
    "Executivo de Vendas",
    "Vendedor Externo",
    "Analista Financeiro Jr",
    "Desenvolvedor Backend Sênior",
])
def test_cargos_comerciais_genericos_e_areas_nao_relacionadas_continuam_fora(titulo):
    assert not vaga(titulo).combina_com(REGRAS), f"não deveria aceitar: {titulo}"


def test_novas_keywords_tambem_entram_nos_termos_de_busca():
    for termo in (
        KEYWORDS_SUPORTE_OPERACOES_TI
        + KEYWORDS_OPERACOES_PROCESSOS_PROJETOS
        + KEYWORDS_CUSTOMER_SUCCESS_COMPLEMENTAR
        + KEYWORDS_DADOS_BI
    ):
        assert termo.casefold() in {k.casefold() for k in KEYWORDS}
        assert termo.casefold() in {k.casefold() for k in TERMOS_BUSCA}


def test_termos_prioritarios_cobrem_familias_novas_sem_remover_prioridades_atuais():
    termos = {t.casefold() for t in TERMOS_PRIORITARIOS}
    assert "crm" in termos
    assert "analista de suporte junior" in termos
    assert "analista de dados junior" in termos
    assert "analista de bi junior" in termos


def test_regra_de_recencia_continua_em_cinco_dias():
    assert DIAS_MAXIMOS_PUBLICACAO == 5


@pytest.mark.parametrize("modalidade,local", [
    ("Híbrido", "Remote - Brazil"),
    ("Presencial", "Remote - Brazil"),
    ("", "São Paulo, SP"),
])
def test_expansao_nao_afrouxa_a_regra_remota(modalidade, local):
    assert not vaga("Analista de Suporte Técnico Júnior", local=local, modalidade=modalidade).combina_com(REGRAS)
