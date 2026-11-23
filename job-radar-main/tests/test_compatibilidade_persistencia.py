"""Persistência dos novos campos sem perder compatibilidade com SQLite existente."""
import sqlite3

import database.database as db
from core.job import Job


def test_persiste_score_e_estado_de_extracao_em_banco_temporario(monkeypatch, tmp_path):
    caminho = str(tmp_path / "jobs.db")
    monkeypatch.setattr(db, "DB_PATH", caminho)
    db.iniciar_db()
    job = Job(
        titulo="Analista de CRM Júnior",
        empresa="Empresa",
        local="Brasil",
        link="https://example.com/vaga/1",
        site="Teste",
        publicado_em="2026-10-28",
        modalidade="Remoto",
        compatibilidade_score=82,
        status_extracao="completa",
        compatibilidade_justificativa="CRM e operações alinhados",
    )
    db.salvar_vaga(job, perfil_chave="brasil")

    with sqlite3.connect(caminho) as conn:
        linha = conn.execute(
            "SELECT compatibilidade_score, status_extracao, justificativa_compatibilidade "
            "FROM vagas_vistas WHERE id = ?",
            (job.id,),
        ).fetchone()
    assert linha == (82, "completa", "CRM e operações alinhados")
