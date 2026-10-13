"""Filtros de elegibilidade e regras de negócio do JobRadar."""

import re
from collections import Counter
from datetime import date, datetime, timezone

from core.job import Job, RegrasFiltro


_PADRAO_RELATIVO_DIAS = re.compile(
    r"(?:h[aá]\s*(\d+)\s*(?:dia|dias)|\b(\d+)\s+days?\s+ago\b)",
    re.IGNORECASE,
)
_PADRAO_RELATIVO_HORAS = re.compile(
    r"(?:h[aá]\s*(\d+)\s*(?:hora|horas)|\b(\d+)\s+hours?\s+ago\b)",
    re.IGNORECASE,
)


def idade_publicacao_em_dias(publicado_em: str, hoje: date | None = None) -> int | None:
    """Retorna idade em dias quando a data pode ser confirmada; None se ausente/ambígua.

    Aceita datas ISO (YYYY-MM-DD), "hoje"/"ontem" e idades relativas em
    português/inglês. Datas ambíguas ou não reconhecidas não são presumidas
    recentes: o chamador pode rejeitá-las quando recência é requisito.
    """
    bruto = (publicado_em or "").strip()
    if not bruto:
        return None
    hoje = hoje or datetime.now(timezone.utc).date()
    iso = bruto[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso):
        try:
            publicada = date.fromisoformat(iso)
        except ValueError:
            return None
        return (hoje - publicada).days

    texto = bruto.casefold().strip()
    if texto in {"hoje", "today", "agora", "just now"}:
        return 0
    if texto in {"ontem", "yesterday"}:
        return 1

    m = _PADRAO_RELATIVO_DIAS.search(texto)
    if m:
        return int(m.group(1) or m.group(2))
    m = _PADRAO_RELATIVO_HORAS.search(texto)
    if m:
        return int(m.group(1) or m.group(2)) // 24
    if re.search(r"\b(?:há\s*menos de uma hora|less than an hour ago|just posted)\b", texto):
        return 0
    return None


def filtrar_publicadas_recentemente(
    vagas: list[Job], dias_maximos: int = 5, hoje: date | None = None
) -> tuple[list[Job], int]:
    """Mantém apenas vagas com data verificável e idade entre 0 e N dias.

    Datas ausentes/ambíguas, datas futuras e vagas antigas são excluídas de
    propósito: quando recência é requisito, não se deve apresentar incerteza
    como se fosse confirmação. Devolve também a quantidade descartada.
    """
    if dias_maximos < 0:
        raise ValueError("dias_maximos precisa ser >= 0")
    recentes = []
    descartadas = 0
    for vaga in vagas:
        idade = idade_publicacao_em_dias(vaga.publicado_em, hoje=hoje)
        if idade is not None and 0 <= idade <= dias_maximos:
            recentes.append(vaga)
        else:
            descartadas += 1
    return recentes, descartadas


def filtrar_vagas(vagas: list[Job], regras: RegrasFiltro) -> tuple[list[Job], Counter]:
    """Devolve vagas aprovadas e um contador de escopos remotos rejeitados."""
    aprovadas = []
    descartes_escopo: Counter = Counter()
    for v in vagas:
        if v.combina_com(regras):
            v.relevancia = v.pontuar_relevancia(regras)
            v.motivo = v.motivo_aprovacao(regras)
            aprovadas.append(v)
        else:
            escopo = v.escopo_rejeitado_por_mercado(regras)
            if escopo:
                descartes_escopo[", ".join(sorted(escopo))] += 1
    return aprovadas, descartes_escopo
