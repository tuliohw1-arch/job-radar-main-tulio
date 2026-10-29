"""Testes do formato de auditoria por ciclo."""
import json

from core.auditoria import AuditoriaCiclo
from core.job import Job


def test_auditoria_grava_resumo_e_evento_com_id_e_url(tmp_path):
    destino = tmp_path / "audit.jsonl"
    auditoria = AuditoriaCiclo("brasil", caminho=str(destino))
    job = Job(
        titulo="Analista de CRM Júnior",
        empresa="Empresa Teste",
        local="Brasil",
        link="https://example.com/jobs/123",
        site="Gupy",
        publicado_em="2026-10-28",
        modalidade="Remoto",
    )
    auditoria.contar("coletadas", 1)
    auditoria.registrar(job, "rejeitada_score", "score abaixo do limiar")
    resumo = auditoria.finalizar()

    linha = json.loads(destino.read_text(encoding="utf-8").splitlines()[0])
    assert linha["tipo"] == "resumo_ciclo"
    assert linha["contadores"]["coletadas"] == 1
    assert linha["eventos"][0]["vaga_id"] == job.id
    assert linha["eventos"][0]["url"] == job.link
    assert linha["eventos"][0]["motivo"] == "score abaixo do limiar"
    assert resumo["ciclo_id"] == linha["ciclo_id"]
    assert "token" not in destino.read_text(encoding="utf-8").casefold()
