"""Teste integrado de um ciclo: coleta simulada até o resultado de notificação."""
import json
from datetime import date

import main
from core.job import Job
from core.perfis import PERFIL_BR


class ScraperSimulado:
    def buscar_vagas(self):
        return [
            Job(
                titulo="Analista de CRM Júnior",
                empresa="Empresa Exemplo",
                local="Remote - Brazil",
                link="https://example.com/jobs/crm-junior",
                site="FonteSimulada",
                publicado_em=date.today().isoformat(),
                modalidade="Remoto",
                descricao=(
                    "Responsabilidades: apoiar operações de CRM, acompanhar chamados, "
                    "organizar processos e produzir relatórios. Requisitos obrigatórios: "
                    "Excel, Jira e atendimento a usuários corporativos. Desejáveis: Power BI. "
                ) * 3,
                origem_descricao="payload_simulado",
                status_extracao="completa",
            )
        ]


def test_ciclo_completo_simulado_registra_score_dedup_e_notificacao(monkeypatch, tmp_path):
    auditoria_path = tmp_path / "ciclos.jsonl"
    monkeypatch.setenv("JOBRADAR_AUDIT_PATH", str(auditoria_path))
    salvas = []
    enviadas = []

    monkeypatch.setattr(main, "_proximo_bloco_termos", lambda perfil: ["crm"])
    monkeypatch.setattr(main, "_construir_scrapers", lambda perfil, termos: [ScraperSimulado()])
    monkeypatch.setattr(main, "_marcar_fonte_baixa_frequencia_concluida", lambda *args: None)
    monkeypatch.setattr(main, "ja_vista", lambda job: False)
    monkeypatch.setattr(main, "salvar_vaga", lambda job, **kwargs: salvas.append((job, kwargs)))
    monkeypatch.setattr(main, "notificar_vaga", lambda job: (enviadas.append(job) or True))
    monkeypatch.setattr(main, "notificar_vaga_exploratoria", lambda job: True)
    monkeypatch.setattr(main, "_enviar_heartbeat_diario", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "_enviar_digest_diario", lambda *args, **kwargs: None)

    main.ciclo_de_busca(PERFIL_BR)

    assert len(salvas) == 1
    assert len(enviadas) == 1
    job = enviadas[0]
    assert job.compatibilidade_score >= 55
    assert job.status_extracao == "completa"
    assert salvas[0][1]["perfil_chave"] == "brasil"

    registro = json.loads(auditoria_path.read_text(encoding="utf-8").splitlines()[0])
    etapas = [evento["etapa"] for evento in registro["eventos"]]
    assert "coletada" in etapas
    assert "avaliada_compatibilidade" in etapas
    assert "notificacao_enviada" in etapas
    assert registro["contadores"]["atendem_criterios_finais"] == 1
    assert registro["contadores"]["notificacoes_enviadas"] == 1
