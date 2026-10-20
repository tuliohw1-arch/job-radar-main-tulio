"""Regra de negócio: somente vagas remotas de alta compatibilidade
para contratação no Brasil. Híbridas, presenciais e mercados internacionais
são rejeitados."""

import pytest
from datetime import date

from core.config import LIMIAR_RELEVANCIA_MINIMA, MERCADOS_REMOTO_ACEITOS
from core.job import Job
from core.perfis import PERFIL_BR
from utils.filtro import filtrar_publicadas_recentemente, idade_publicacao_em_dias


def vaga(titulo, local="Remote - Brazil", modalidade="Remoto"):
    return Job(titulo=titulo, empresa="Teste", local=local,
               link=f"https://exemplo.com/{abs(hash((titulo, local, modalidade)))}",
               site="Teste", modalidade=modalidade)


@pytest.mark.parametrize("titulo", [
    "Analista de CRM", "CRM Analyst", "CRM Operations Analyst",
    "Analista de Automação de Marketing", "Marketing Automation Specialist",
    "Customer Success Analyst", "Analista de Experiência do Cliente",
])
def test_aceita_cargos_alinhados(titulo):
    assert vaga(titulo).combina_com(PERFIL_BR.regras)


@pytest.mark.parametrize("titulo, local", [
    ("Analista de CRM - Homeoffice", "São Paulo - SP"),
    ("CRM Analyst - Home Office", "Remote - Brazil"),
    ("CRM Analyst - Work from Home", "São Paulo - SP"),
    ("Analista de CRM - Remote", "Brasil"),
])
def test_aceita_indicacao_remota_no_titulo_ou_local(titulo, local):
    job = vaga(titulo, local, modalidade="")
    assert job.modalidade == "Remoto"
    assert job.combina_com(PERFIL_BR.regras)


@pytest.mark.parametrize("titulo, local, modalidade", [
    ("CRM Analyst - Hybrid Remote", "Remote - Brazil", "Remoto"),
    ("Analista de CRM - Homeoffice", "São Paulo - SP", "Híbrido"),
    ("CRM Analyst", "Home Office", "Presencial"),
])
def test_sinal_hibrido_ou_presencial_prevalece(titulo, local, modalidade):
    assert not vaga(titulo, local, modalidade).combina_com(PERFIL_BR.regras)


@pytest.mark.parametrize("modalidade, local", [
    ("Híbrido", "Belo Horizonte, MG"), ("Presencial", "Belo Horizonte, MG"),
    ("Híbrido", "Recife, PE"), ("Presencial", "São Paulo, SP"),
    ("", "Belo Horizonte, MG"),
])
def test_rejeita_hibrido_presencial_ou_modalidade_desconhecida(modalidade, local):
    assert not vaga("Analista de CRM", local, modalidade).combina_com(PERFIL_BR.regras)


@pytest.mark.parametrize("local", [
    "Remote - US only", "Remote - United States", "Remote - India",
    "Remote - Portugal", "Remote - Spain", "Remote - Mexico",
    "Remote - LATAM", "Remote - Worldwide",
])
def test_rejeita_escopo_internacional_ou_nao_confirmado(local):
    assert not vaga("CRM Analyst", local).combina_com(PERFIL_BR.regras)


@pytest.mark.parametrize("local", [
    "Remote - Brazil", "Remote, Brazil", "Remoto - Brasil", "Brasil (remoto)",
])
def test_aceita_remoto_com_escopo_brasileiro(local):
    assert vaga("Analista de CRM", local).combina_com(PERFIL_BR.regras)


def test_cargos_genericos_nao_entram():
    assert not vaga("Customer Support Analyst").combina_com(PERFIL_BR.regras)
    assert not vaga("Analista de Atendimento ao Cliente").combina_com(PERFIL_BR.regras)
    assert not vaga("Analista de Dados").combina_com(PERFIL_BR.regras)


@pytest.mark.parametrize("titulo", [
    "CRM Analyst (Hybrid)",
    "Analista de CRM Híbrida",
    "Analista de CRM Semi-presencial",
    "CRM Analyst - In-person",
    "CRM Analyst - Office-based",
])
def test_titulo_contradiz_modalidade_remota(titulo):
    vaga_remota = vaga(titulo, local="Remote - Brazil", modalidade="Remoto")
    assert vaga_remota.modalidade in {"Híbrido", "Presencial"}
    assert not vaga_remota.combina_com(PERFIL_BR.regras)


def test_minimo_de_relevancia_alto():
    assert LIMIAR_RELEVANCIA_MINIMA >= 7


def test_so_brasil_e_remoto():
    assert MERCADOS_REMOTO_ACEITOS == ["Brasil"]
    assert PERFIL_BR.regras.cidades == ["Remoto"]


@pytest.mark.parametrize(
    "publicado, esperado",
    [
        ("2026-10-11", 0),
        ("2026-10-09", 2),
        ("2026-10-07", 4),
        ("há 2 dias", 2),
        ("2 days ago", 2),
        ("há 12 horas", 0),
        ("12 hours ago", 0),
        ("hoje", 0),
        ("ontem", 1),
        ("", None),
        ("Publicada em 11/08", None),
    ],
)
def test_idade_publicacao_com_data_fixa(publicado, esperado):
    assert idade_publicacao_em_dias(publicado, hoje=date(2026, 10, 11)) == esperado


def test_recencia_descarta_data_ausente_antiga_futura_e_ambigua():
    vagas = [
        vaga("Analista de CRM Júnior", modalidade="Remoto"),
        Job("CRM Analyst", "Teste", "Brasil", "https://exemplo.com/old", "Teste", publicado_em="2026-10-07", modalidade="Remoto"),
        Job("CRM Analyst", "Teste", "Brasil", "https://exemplo.com/future", "Teste", publicado_em="2026-10-12", modalidade="Remoto"),
        Job("CRM Analyst", "Teste", "Brasil", "https://exemplo.com/recent", "Teste", publicado_em="2026-10-09", modalidade="Remoto"),
        Job("CRM Analyst", "Teste", "Brasil", "https://exemplo.com/ambiguous", "Teste", publicado_em="Publicada em 11/08", modalidade="Remoto"),
    ]
    recentes, descartadas = filtrar_publicadas_recentemente(vagas, dias_maximos=3, hoje=date(2026, 10, 11))
    assert [v.link for v in recentes] == ["https://exemplo.com/recent"]
    assert descartadas == 4
