"""Cobertura dos títulos monitorados no MVP do perfil Brasil."""

import pytest

from core.perfis import PERFIL_BR
from core.job import Job

REGRAS = PERFIL_BR.regras


def _vaga(titulo: str, local: str = "Remoto - Brasil") -> Job:
    return Job(
        titulo=titulo,
        empresa="Empresa",
        local=local,
        link="https://www.linkedin.com/jobs/view/" + titulo,
        site="LinkedIn",
        modalidade="Remoto",
    )


@pytest.mark.parametrize("titulo", [
    "Analista de CRM",
    "CRM Analyst",
    "Customer Success Analyst",
    "Analista de Experiência do Cliente",

])
def test_titulos_das_areas_prioritarias_passam(titulo):
    assert _vaga(titulo).combina_com(REGRAS)


@pytest.mark.parametrize("titulo", [
    "Analista de Atendimento ao Cliente",
    "Analista de Relacionamento com Cliente",
    "Analista de Dados",
    "Business Intelligence Analyst",
    "Analista de Banco de Dados",
    "Financial Analyst",
    "Vendedor Externo",
])
def test_titulos_fora_do_mvp_nao_passam(titulo):
    assert not _vaga(titulo).combina_com(REGRAS)
