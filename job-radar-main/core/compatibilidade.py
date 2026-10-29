"""Classificação determinística e explicável da compatibilidade com o perfil Brasil.

Não é IA nem probabilidade de contratação. Pontos são sinais textuais da vaga
comparados com competências comprovadas; SQL/automação ficam como lacunas em
desenvolvimento, nunca como experiência comprovada.
"""
from __future__ import annotations

import re
import unicodedata

PESOS_COMPATIBILIDADE = {
    "familia_profissional": 25,
    "experiencia_operacional": 25,
    "ferramentas_comprovadas": 20,
    "crm_hubspot": 15,
    "senioridade": 10,
    "remoto_brasil": 5,
}
LIMIAR_COMPATIBILIDADE_MINIMA = 55


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", (texto or "").casefold())
    return "".join(c for c in texto if not unicodedata.combining(c))


def _tem(texto: str, termos: tuple[str, ...] | list[str]) -> list[str]:
    normal = _normalizar(texto)
    return [termo for termo in termos if re.search(r"(?<!\w)" + re.escape(_normalizar(termo)) + r"(?!\w)", normal)]


def pontuar_compatibilidade(job) -> dict:
    titulo = getattr(job, "titulo", "") or ""
    descricao = getattr(job, "descricao", "") or ""
    texto = f"{titulo}\n{descricao}"
    detalhes = []
    lacunas = []
    obrigatorios = getattr(job, "requisitos_obrigatorios", []) or []
    requisitos = " ".join(obrigatorios) if isinstance(obrigatorios, list) else str(obrigatorios)
    score = 0
    pesos = PESOS_COMPATIBILIDADE

    familia = _tem(texto, (
        "crm", "customer success", "customer experience", "cx", "service desk",
        "suporte", "support", "implantacao", "onboarding", "operacoes",
        "operations", "processos", "process", "business analyst", "power bi",
        "business intelligence", "relatorios", "reporting", "indicadores",
        "data analyst", "analista de dados", "analista de bi",
    ))
    if familia:
        score += pesos["familia_profissional"]
        detalhes.append("Família de cargo alinhada: " + ", ".join(familia[:5]))
    else:
        lacunas.append("Responsabilidades/título não mostram alinhamento claro às áreas-alvo.")

    operacao = _tem(texto, (
        "jira", "chamados", "ticket", "service level", "sla", "suporte a usuarios",
        "atendimento corporativo", "resolucao de problemas", "processos",
        "indicadores", "kpi", "relatorios", "operacoes", "operations",
    ))
    if operacao:
        score += pesos["experiencia_operacional"]
        detalhes.append("Experiência transferível em suporte/operações: " + ", ".join(operacao[:5]))
    else:
        lacunas.append("Poucos sinais de suporte corporativo, chamados, SLA ou operações.")

    ferramentas = _tem(texto, ("excel", "power bi", "jira", "papercut", "hubspot"))
    if ferramentas:
        # Só sinaliza correspondência com competências comprovadas.
        score += min(pesos["ferramentas_comprovadas"], 7 * len(set(ferramentas)))
        detalhes.append("Ferramentas compatíveis com experiência/certificações conhecidas: " + ", ".join(dict.fromkeys(ferramentas)))
    else:
        lacunas.append("A descrição não cita ferramentas já comprovadas no perfil (Excel, Power BI, Jira, HubSpot).")

    crm = _tem(texto, ("crm", "hubspot", "marketing automation", "customer relationship management"))
    if crm:
        score += pesos["crm_hubspot"]
        detalhes.append("Alinhamento com objetivo de transição para CRM/Customer Success.")
    else:
        lacunas.append("Sem sinal textual relevante de CRM/HubSpot.")

    senioridade = _normalizar(titulo + " " + descricao)
    if re.search(r"\b(junior|jr\.?|entry.level|associate|assistente|analista i)\b", senioridade):
        score += pesos["senioridade"]
        detalhes.append("Senioridade de entrada/júnior alinhada.")
    elif re.search(r"\b(senior|sr\.?|lead|principal|manager|head|diretor|coordenador)\b", senioridade):
        lacunas.append("Senioridade possivelmente acima do alvo; confirmar escopo real.")
    else:
        score += pesos["senioridade"] // 2
        lacunas.append("Senioridade não identificada; confiança reduzida.")

    modalidade = _normalizar(getattr(job, "modalidade", ""))
    local = _normalizar(getattr(job, "local", ""))
    remoto = any(t in modalidade for t in ("remoto", "remote", "home office"))
    brasil = any(t in local for t in ("brasil", "brazil", "br"))
    if remoto and (brasil or not local or "nao informado" in local):
        score += pesos["remoto_brasil"]
        detalhes.append("Modalidade remota informada; escopo Brasil aceito pelo filtro anterior.")
    else:
        lacunas.append("Modalidade/escopo Brasil não foi confirmado pelo modelo de compatibilidade.")

    requisitos_norm = _normalizar(requisitos)
    hard_gaps = []
    # Ferramentas que o perfil conhece parcialmente/em desenvolvimento não viram experiência.
    if re.search(r"\b(sql|python|salesforce|tableau|looker|aws|azure)\b", requisitos_norm):
        for termo in ("sql", "python", "salesforce", "tableau", "looker", "aws", "azure"):
            if re.search(r"\b" + termo + r"\b", requisitos_norm):
                hard_gaps.append(termo.upper() + " aparece nos requisitos obrigatórios; validar proficiência.")
    if hard_gaps:
        lacunas.extend(hard_gaps)
        score = max(0, score - min(15, 5 * len(hard_gaps)))

    descricao_ok = len(descricao.strip()) >= 180
    if not descricao_ok:
        score = min(score, 54)
        lacunas.append("Descrição ausente/incompleta: avaliação limitada aos metadados do anúncio.")

    score = max(0, min(100, int(round(score))))
    return {
        "score": score,
        "criterios_positivos": detalhes,
        "lacunas": list(dict.fromkeys(lacunas)),
        "requisitos_obrigatorios_nao_atendidos": hard_gaps,
        "justificativa": "; ".join(detalhes) if detalhes else "Não foram encontrados sinais textuais suficientes de compatibilidade.",
        "informacoes_insuficientes": not descricao_ok or not getattr(job, "modalidade", ""),
        "status_descricao": getattr(job, "status_extracao", "indisponivel"),
    }
