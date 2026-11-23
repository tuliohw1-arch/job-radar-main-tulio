"""Auditoria estruturada por ciclo do JobRadar (JSONL, sem segredos)."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid


class AuditoriaCiclo:
    def __init__(self, perfil: str, caminho: str | None = None):
        self.perfil = perfil
        self.ciclo_id = uuid.uuid4().hex[:12]
        self.iniciado_em = datetime.now(timezone.utc).isoformat()
        self.contadores = Counter()
        self.eventos: list[dict] = []
        self.caminho = Path(caminho or os.getenv("JOBRADAR_AUDIT_PATH", "data/audit/ciclos.jsonl"))

    def contar(self, etapa: str, quantidade: int = 1) -> None:
        self.contadores[etapa] += quantidade

    def registrar(self, job, etapa: str, motivo: str = "") -> None:
        self.eventos.append({
            "ciclo_id": self.ciclo_id,
            "perfil": self.perfil,
            "etapa": etapa,
            "motivo": motivo,
            "vaga_id": getattr(job, "id", ""),
            "titulo": getattr(job, "titulo", ""),
            "empresa": getattr(job, "empresa", ""),
            "fonte": getattr(job, "site", ""),
            "url": getattr(job, "link", ""),
            "publicado_em": getattr(job, "publicado_em", ""),
            "modalidade": getattr(job, "modalidade", ""),
            "status_extracao": getattr(job, "status_extracao", "indisponivel"),
            "origem_descricao": getattr(job, "origem_descricao", ""),
            "erro_extracao": getattr(job, "erro_extracao", ""),
            "descricao_chars": len(getattr(job, "descricao", "") or ""),
            "compatibilidade_score": getattr(job, "compatibilidade_score", 0),
            "senioridade_detectada": getattr(job, "senioridade_detectada", ""),
            "ferramentas_detectadas": getattr(job, "ferramentas_detectadas", []) or [],
            "criterios_positivos": getattr(job, "compatibilidade_criterios", []) or [],
            "lacunas": getattr(job, "compatibilidade_lacunas", []) or [],
            "requisitos_obrigatorios_nao_atendidos": getattr(job, "compatibilidade_requisitos_nao_atendidos", []) or [],
            "justificativa_compatibilidade": getattr(job, "compatibilidade_justificativa", ""),
        })

    def registrar_fonte(self, fonte: str, etapa: str, motivo: str = "") -> None:
        self.eventos.append({
            "ciclo_id": self.ciclo_id,
            "perfil": self.perfil,
            "etapa": etapa,
            "motivo": motivo,
            "fonte": fonte,
            "vaga_id": "",
            "url": "",
        })

    def finalizar(self) -> dict:
        resumo = {
            "tipo": "resumo_ciclo",
            "ciclo_id": self.ciclo_id,
            "perfil": self.perfil,
            "iniciado_em": self.iniciado_em,
            "finalizado_em": datetime.now(timezone.utc).isoformat(),
            "contadores": dict(self.contadores),
            "eventos": self.eventos,
        }
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self.caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps(resumo, ensure_ascii=False, sort_keys=True) + "\n")
        return resumo
