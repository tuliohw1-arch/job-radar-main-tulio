
import os
from dotenv import load_dotenv

load_dotenv()

# Áreas monitoradas no perfil Brasil, em ordem de prioridade.
# O filtro aceita títulos destas três frentes; o ranking usa a mesma ordem
# para decidir quais vagas merecem mais destaque.

# 1) Objetivo principal: CRM.
KEYWORDS_CARGO_FORTE = [
    "Analista de CRM",
    "Analista de CRM Júnior",
    "Analista de CRM Junior",
    "Analista CRM Jr",
    "Analista CRM Junior",
    "Analista Jr de CRM",
    "Analista Jr CRM",
    "CRM Jr",
    "CRM Junior",
    "CRM Analyst Jr",
    "CRM Analyst Junior",
    "Junior CRM Analyst",
    "Customer Relationship Management Analyst",
    "CRM Marketing Analyst",
    "Analista de Marketing CRM",
    "Assistente CRM",
    "CRM Assistant",
    "CRM Coordinator",
    "CRM Analyst",
    "Especialista em CRM",
    "Especialista de CRM",
    "CRM Specialist",
    "Assistente de CRM",
    "Consultor de CRM",
    "Consultor CRM",
    "CRM Consultant",
    "Analista de CRM Operations",
    "CRM Operations Analyst",
    "CRM Ops Analyst",
    "CRM Operations Specialist",
    "Analista de Automação de Marketing",
    "Marketing Automation Analyst",
    "Marketing Automation Specialist",
    "Lifecycle Marketing Analyst",
    "Retention Marketing Analyst",
]

# 2) Segunda prioridade: Customer Success e Experiência do Cliente.
# Inclui variantes Jr/Junior e títulos usados por empresas SaaS; a checagem
# continua sendo pelo título e o filtro remoto/recência permanece obrigatório.
KEYWORDS_CUSTOMER_SUCCESS_CX = [
    "Analista de Customer Success",
    "Customer Success Analyst",
    "Customer Success Analyst Jr",
    "Customer Success Analyst Junior",
    "Junior Customer Success Analyst",
    "Analista CS Jr",
    "Analista CS Junior",
    "CS Analyst Jr",
    "CS Analyst Junior",
    "Customer Success Associate Jr",
    "Customer Success Associate Junior",
    "Junior Customer Success Associate",
    "Customer Success Specialist Jr",
    "Customer Success Specialist Junior",
    "Customer Success Coordinator Jr",
    "Customer Success Manager Jr",
    "Assistente de Customer Success",
    "Assistente CS",
    "Analista de Sucesso do Cliente Jr",
    "Analista de Sucesso do Cliente Junior",
    "Analista de Sucesso do Cliente Júnior",
    "Analista Jr de Sucesso do Cliente",
    "Analista Jr de Customer Success",
    "Customer Success Jr",
    "Customer Success Junior",
    "Customer Success Associate",
    "Associate Customer Success Manager",
    "Especialista em Customer Success",
    "Customer Success Specialist",
    "Customer Success Manager",
    "CSM",
    "Analista de Sucesso do Cliente",
    "Analista de Experiência do Cliente",
    "Analista de Experiencia do Cliente",
    "Customer Experience Analyst",
    "Customer Experience Analyst Jr",
    "Customer Experience Analyst Junior",
    "Junior Customer Experience Analyst",
    "CX Analyst Jr",
    "CX Analyst Junior",
    "Customer Experience Specialist Jr",
    "Customer Experience Specialist Junior",
    "Customer Experience Associate Jr",
    "Customer Experience Manager Jr",
    "Analista CX Jr",
    "Analista CX Junior",
    "Analista Jr de CX",
    "Analista Jr de Experiência do Cliente",
    "Analista Jr de Experiencia do Cliente",
    "Analista de Customer Experience Jr",
    "Analista de Customer Experience Junior",
    "Analista de Experiência do Cliente Jr",
    "Analista de Experiencia do Cliente Jr",
    "Customer Experience Junior",
    "Customer Experience Jr",
    "Customer Experience Associate",
    "CX Analyst",
    "CX Jr",
    "CX Junior",
    "Analista de CX Jr",
    "Analista de CX Junior",
    "Customer Experience (CX) Analyst Jr",
    "Customer Experience (CX) Analyst Junior",
    "CX Associate Jr",
    "CX Specialist Jr",
    "Analista de CX",
]

# 3) Terceira prioridade: operações e etapas próximas do ciclo do cliente.
# São portas de entrada plausíveis para CRM/RevOps: onboarding, implantação,
# operações de CS e suporte B2B/SaaS. Não incluímos "atendimento" genérico,
# vendas, SDR ou suporte técnico amplo, para conter falso positivo.
KEYWORDS_OPERACOES_CLIENTE = [
    "Analista de Onboarding",
    "Customer Onboarding Specialist",
    "Customer Onboarding Analyst",
    "Customer Onboarding Associate",
    "Analista de Implantação",
    "Implementation Analyst",
    "Implementation Specialist",
    "Customer Operations Analyst",
    "Customer Operations Associate",
    "Customer Success Operations",
    "CS Operations Analyst",
    "CS Ops Analyst",
    "Analista de Operações de Customer Success",
    "Analista de Operações de Clientes",
    "Customer Support Analyst Jr",
    "Customer Support Analyst Junior",
    "Analista de Suporte ao Cliente Jr",
    "Analista de Suporte ao Cliente Junior",
]

# Famílias adicionais para ampliar a transição sem abrir para cargos genéricos.
# Grupo B — ponte para CRM: operações comerciais e receita.
KEYWORDS_OPERACOES_COMERCIAIS = [
    "Business Operations Analyst",
    "Business Operations Analyst Jr",
    "Junior Business Operations Analyst",
    "Business Operations Associate",
    "Analista de Operações de Negócios",
    "Analista de Operações de Negocio",
    "Analista de Business Operations",
    "Sales Operations Analyst",
    "Sales Operations Analyst Jr",
    "Junior Sales Operations Analyst",
    "Sales Operations Associate",
    "Sales Ops Analyst",
    "Sales Ops Specialist",
    "Analista de Sales Operations",
    "Analista de Operações Comerciais",
    "Revenue Operations Analyst",
    "Revenue Operations Analyst Jr",
    "Junior Revenue Operations Analyst",
    "Revenue Operations Associate",
    "RevOps Analyst",
    "RevOps Analyst Jr",
    "RevOps Associate",
    "Analista de RevOps",
    "Analista de Operações de Receita",
    "Revenue Enablement Analyst",
    "SaaS Implementation Analyst",
    "SaaS Onboarding Specialist",
]

# Grupo C — entrada complementar: operações de marketing e suporte SaaS.
KEYWORDS_MARKETING_OPERATIONS = [
    "Marketing Operations Analyst",
    "Marketing Operations Specialist",
    "Marketing Operations Associate",
    "Marketing Ops Analyst",
    "Marketing Ops Specialist",
    "Analista de Marketing Operations",
    "Analista de Operações de Marketing",
    "Marketing Automation Analyst",
    "Marketing Automation Specialist",
    "Marketing Automation Associate",
    "CRM Automation Analyst",
    "HubSpot Operations Specialist",
    "HubSpot Administrator Jr",
    "Salesforce Administrator Jr",
    "SaaS Support Analyst",
    "SaaS Support Specialist",
    "Technical Support Specialist SaaS",
    "Customer Support Operations Analyst",
    "Customer Support Operations Specialist",
    "Analista de Suporte SaaS",
    "Analista de Suporte a Sistemas SaaS",
]

# 4) CRM adjacente: retenção, jornada e automação de marketing.
KEYWORDS_RELACIONAMENTO_ATENDIMENTO = KEYWORDS_OPERACOES_CLIENTE


# Famílias adicionais explicitamente solicitadas para ampliar a busca além de CRM/CX.
# Mantemos títulos específicos para não transformar palavras genéricas ("analista",
# "suporte", "dados") em critérios de aprovação.
KEYWORDS_SUPORTE_OPERACOES_TI = [
    "Analista de TI Júnior", "Analista de TI Junior", "Analista TI Jr",
    "IT Analyst Junior", "Junior IT Analyst", "IT Support Analyst Jr",
    "Analista de Suporte Júnior", "Analista de Suporte Junior",
    "Analista de Suporte Jr", "Analista de Suporte Técnico Júnior",
    "Analista de Suporte Tecnico Junior", "Analista de Suporte Técnico Jr",
    "Analista de Service Desk Júnior", "Analista de Service Desk Junior",
    "Service Desk Analyst Jr", "Junior Service Desk Analyst",
    "Analista de Operações de TI Júnior", "Analista de Operacoes de TI Junior",
    "IT Operations Analyst Jr", "Junior IT Operations Analyst",
    "Analista de Suporte a Sistemas", "Systems Support Analyst",
    "Analista de Implantação de Sistemas Júnior",
    "Analista de Implantacao de Sistemas Junior",
    "Junior Systems Implementation Analyst",
    "Analista de Sistemas Júnior", "Analista de Sistemas Junior",
    "Junior Systems Analyst", "Técnico de Suporte Remoto",
    "Tecnico de Suporte Remoto", "Remote Technical Support",
]

KEYWORDS_OPERACOES_PROCESSOS_PROJETOS = [
    "Analista de Operações Júnior", "Analista de Operacoes Junior",
    "Junior Operations Analyst", "Operations Analyst Jr",
    "Analista de Processos Júnior", "Analista de Processos Junior",
    "Junior Process Analyst", "Process Analyst Jr",
    "Analista de Operações de Negócio Júnior",
    "Analista de Operacoes de Negocio Junior",
    "Business Operations Analyst Jr", "Junior Business Operations Analyst",
    "Analista de Projetos Júnior", "Analista de Projetos Junior",
    "Junior Project Analyst", "Project Analyst Jr",
    "Assistente de Projetos", "Project Assistant",
    "Analista de PMO Júnior", "Analista de PMO Junior", "Junior PMO Analyst",
    "Analista de Implantação Júnior", "Analista de Implantacao Junior",
    "Implementation Analyst Jr", "Junior Implementation Analyst",
    "Analista de Requisitos Júnior", "Analista de Requisitos Junior",
    "Junior Requirements Analyst", "Requirements Analyst Jr",
]

KEYWORDS_CUSTOMER_SUCCESS_COMPLEMENTAR = [
    "Customer Operations", "Customer Operations Analyst",
    "Analista de Onboarding Júnior", "Analista de Onboarding Junior",
    "Junior Onboarding Analyst", "Analista de Implantação de Clientes",
    "Analista de Implantacao de Clientes", "Customer Implementation Analyst",
    "Analista de Customer Experience Júnior", "Analista de Customer Experience Junior",
    "Customer Experience Analyst Jr", "Junior Customer Experience Analyst",
    "Analista de Atendimento ao Cliente Júnior",
    "Analista de Atendimento ao Cliente Junior",
    "Customer Support Analyst Jr", "Junior Customer Support Analyst",
    "Analista de Qualidade de Atendimento", "Customer Service Quality Analyst",
]

KEYWORDS_DADOS_BI = [
    "Analista de Indicadores", "KPI Analyst", "Operations Metrics Analyst",
    "Analista de Dados Júnior", "Analista de Dados Junior",
    "Analista de Dados Jr", "Junior Data Analyst", "Data Analyst Jr",
    "Data Analyst Junior", "Analista de BI Júnior", "Analista de BI Junior",
    "BI Analyst Jr", "BI Analyst Junior", "Junior BI Analyst",
    "Assistente de BI", "BI Assistant", "Analista de Relatórios",
    "Reporting Analyst", "Analista de Performance Operacional",
    "Operational Performance Analyst", "Analista de Dados de Clientes Júnior",
    "Analista de Dados de Clientes Junior", "Junior Customer Data Analyst",
]


# Todos os títulos inequívocos aceitos pelo filtro.
KEYWORDS_CARGO_FORTE += (
    KEYWORDS_SUPORTE_OPERACOES_TI
    + KEYWORDS_OPERACOES_PROCESSOS_PROJETOS
    + KEYWORDS_CUSTOMER_SUCCESS_COMPLEMENTAR
    + KEYWORDS_DADOS_BI
    +     KEYWORDS_CUSTOMER_SUCCESS_CX
    + KEYWORDS_RELACIONAMENTO_ATENDIMENTO
    + KEYWORDS_OPERACOES_COMERCIAIS
    + KEYWORDS_MARKETING_OPERATIONS
)

# Títulos ambíguos só contam se também tiverem um qualificador da área.
KEYWORDS_CARGO_AMBIGUO = [
    "Customer Success",
    "Customer Experience",
    "Experiência do Cliente",
    "Experiencia do Cliente",
]

# Qualificadores usados exclusivamente junto aos cargos ambíguos acima.
QUALIFICADORES_DADOS = [
    "customer",
    "cliente",
    "crm",
    "cx",
    "cs",
    "sucesso",
    "experiência",
    "experiencia",
    "relacionamento",
    "atendimento",
]

# Não há ferramenta isolada aprovada no MVP. Uma ferramenta no título não
# basta para provar que a vaga pertence a uma das três áreas monitoradas.
FERRAMENTAS_TITULO = []
QUALIFICADORES_CARGO = []

# Peso do cargo no ranking, usando a mesma taxonomia do filtro.
# CRM > Customer Success/CX > Relacionamento/Atendimento.
PRIORIDADES_CARGO = {
    **{cargo: 3 for cargo in [
        "Analista de CRM", "CRM Analyst", "Especialista em CRM",
        "Especialista de CRM", "CRM Specialist", "Assistente de CRM",
        "Consultor de CRM", "Consultor CRM", "CRM Consultant",
        "Analista de CRM Operations", "CRM Operations Analyst",
        "CRM Ops Analyst", "CRM Operations Specialist",
        "Analista de Automação de Marketing", "Marketing Automation Analyst",
        "Marketing Automation Specialist", "Lifecycle Marketing Analyst",
        "Retention Marketing Analyst",
    ]},
    **{cargo: 2 for cargo in KEYWORDS_CUSTOMER_SUCCESS_CX},
    **{cargo: 1 for cargo in KEYWORDS_RELACIONAMENTO_ATENDIMENTO},
}
# Pontuação por família para as novas áreas ponte; CRM continua no topo.
PRIORIDADES_CARGO.update({
    **{cargo: 2 for cargo in KEYWORDS_SUPORTE_OPERACOES_TI},
    **{cargo: 2 for cargo in KEYWORDS_OPERACOES_PROCESSOS_PROJETOS},
    **{cargo: 2 for cargo in KEYWORDS_DADOS_BI},
    **{cargo: 1 for cargo in KEYWORDS_CUSTOMER_SUCCESS_COMPLEMENTAR},
})

# Taxonomia de busca do perfil Brasil. Os pesos expressam prioridade operacional,
# não probabilidade estatística de contratação. O filtro remoto e a data
# verificável continuam sendo critérios eliminatórios independentes.
GRUPOS_CARGOS = {
    "A": {
        "nome": "Objetivo direto",
        "peso": 40,
        "keywords": [
            "CRM Operations Analyst", "CRM Ops Analyst", "Analista de CRM Operations",
            "CRM Analyst", "CRM Analyst Jr", "Junior CRM Analyst",
            "CS Operations Analyst", "CS Ops Analyst", "Customer Success Operations",
            "Analista de Operações de Customer Success",
        ],
    },
    "B": {
        "nome": "Ponte para CRM",
        "peso": 40,
        "keywords": KEYWORDS_SUPORTE_OPERACOES_TI + KEYWORDS_OPERACOES_PROCESSOS_PROJETOS + KEYWORDS_DADOS_BI + KEYWORDS_CUSTOMER_SUCCESS_COMPLEMENTAR + KEYWORDS_OPERACOES_COMERCIAIS + [
            "Analista de Implantação", "Implementation Analyst",
            "Implementation Specialist", "Customer Onboarding Specialist",
            "Customer Onboarding Analyst", "Customer Operations Analyst",
            "Customer Operations Associate",
        ],
    },
    "C": {
        "nome": "Entrada complementar",
        "peso": 20,
        "keywords": KEYWORDS_MARKETING_OPERATIONS + [
            "Marketing Automation Analyst", "Marketing Automation Specialist",
            "Analista de Automação de Marketing", "Marketing Automation Associate",
        ],
    },
}
assert sum(grupo["peso"] for grupo in GRUPOS_CARGOS.values()) == 100

# Prioridades por grupo: A > B > C. Isso afeta a relevância/ranking,
# sem permitir que score compense modalidade ou data inválida.
PRIORIDADES_CARGO.update({
    **{cargo: 3 for cargo in GRUPOS_CARGOS["A"]["keywords"]},
    **{cargo: 2 for cargo in GRUPOS_CARGOS["B"]["keywords"]},
    **{cargo: 1 for cargo in GRUPOS_CARGOS["C"]["keywords"]},
})

KEYWORDS = KEYWORDS_CARGO_FORTE + KEYWORDS_CARGO_AMBIGUO

# Termos de busca enviados a cada site. Ficam separados das KEYWORDS de
# propósito: TERMOS_BUSCA é a rede ampla (o que é pesquisado em cada site,
# incluindo termos de ferramenta/stack pra achar vaga com título atípico),
# enquanto KEYWORDS é o filtro final e só olha o título da vaga já
# encontrada. Um termo de ferramenta (ex: "dax") só resulta em notificação
# se o TÍTULO da vaga também bater com uma keyword de cargo — isso evita
# falso positivo de vaga que só cita a ferramenta como diferencial.
#
# TERMOS_CARGO é derivado direto de KEYWORDS (em vez de mantido à mão em
# lista separada) — antes as duas listas divergiam: metade das KEYWORDS
# (ex: "Desenvolvedor BI", "BI Analyst", "Analista de Negócios") nunca era
# buscada de verdade, só existia como filtro, então só pegava essas vagas
# por sorte via outro termo. Com a derivação automática isso não pode mais
# acontecer — toda keyword nova em KEYWORDS já vira busca também.
TERMOS_CARGO_EXTRA = [
    "crm",
    "crm operations",
    "marketing automation",
    "lifecycle marketing",
    "retention marketing",
    "customer success",
    "customer success jr",
    "analista de sucesso do cliente jr",
    "cx jr",
    "customer experience",
    "customer onboarding",
    "onboarding",
    "implementation analyst",
    "analista de implantação",
    "customer operations",
    "customer success operations",
    "cs ops",
    "experiência do cliente",
    "relacionamento com cliente",
    "sucesso do cliente",
    "suporte ao cliente jr",
    "analista de crm jr",
    "analista de crm junior",
    "analista crm jr",
    "analista crm junior",
    "analista jr de crm",
    "analista jr crm",
    "crm junior",
    "crm analyst jr",
    "crm analyst junior",
    "crm marketing analyst",
    "assistente crm",
    "customer success jr",
    "customer success junior",
    "analista cs jr",
    "analista cs junior",
    "cs analyst jr",
    "cs analyst junior",
    "customer success analyst jr",
    "customer success analyst junior",
    "customer success associate jr",
    "analista de sucesso do cliente jr",
    "analista de sucesso do cliente junior",
    "analista jr de customer success",
    "cx jr",
    "crm operations",
    "cs ops",
    "business operations",
    "sales operations",
    "sales ops",
    "revenue operations",
    "revops",
    "marketing operations",
    "marketing ops",
    "saas support",
    "saas onboarding",
    "implementation analyst",
    "analista cx jr",
    "analista cx junior",
    "analista de cx jr",
    "analista de cx junior",
    "cx analyst jr",
    "cx analyst junior",
    "customer experience jr",
    "customer experience analyst jr",
    "analista de customer experience jr",
    "analista jr de cx",
    "analista jr de experiência do cliente",
    "analista jr de experiencia do cliente",
]

TERMOS_CARGO = sorted(set(k.lower() for k in KEYWORDS) | set(TERMOS_CARGO_EXTRA))

# MEDIDO em jobradar.log (12 rodízios completos, Gupy+99Jobs+GeekHunter+
# Solides): "dax" e "power query" nunca resultaram em nenhuma vaga nova
# notificada nessas 4 fontes — 0 em 48 buscas cada, a maioria vazia
# ("0 resultados reais") e o resto timeout. "microsoft fabric" teve 1 vaga
# no log inteiro (363 notificações) com o termo no título, e essa vaga
# também tinha "Power BI"/"Analista de BI" no título — já seria achada por
# termo que continua na lista. Timeout: os 3 termos concentraram metade
# (13 de 26) dos timeouts dessas 4 fontes sendo só 3 dos 42 termos (7%) —
# confirma o padrão relatado. Removidos por render zero e custarem sessão
# igual a um termo de cargo.
TERMOS_FERRAMENTA = []

def _grupo_do_termo(termo: str) -> str:
    """Classifica termos de busca para distribuir o rodízio entre as famílias."""
    t = termo.casefold()
    # Complementares vêm primeiro para "CRM Automation" não ser confundido
    # com o núcleo só por conter CRM no nome.
    if any(sinal in t for sinal in (
        "marketing operations", "marketing ops", "marketing automation",
        "marketing automation", "automação", "automacao", "automation",
        "saas support", "suporte saas", "hubspot operations",
        "salesforce administrator",
    )):
        return "C"
    if "crm" in t or "cs ops" in t or "cs operations" in t or "customer success operations" in t:
        return "A"
    return "B"


def _ordenar_termos_ponderados(termos: list[str]) -> list[str]:
    """Intercala o rodízio em proporção 40/40/20 (padrão A,A,B,B,C).

    A ordem mantém cada termo uma única vez. Se uma família esgotar os seus
    termos antes das demais, as filas restantes continuam sem duplicação.
    """
    filas = {
        grupo: [termo for termo in termos if _grupo_do_termo(termo) == grupo]
        for grupo in ("A", "B", "C")
    }
    ordem = []
    padrao = ("A", "A", "B", "B", "C")
    while any(filas.values()):
        avancou = False
        for grupo in padrao:
            if filas[grupo]:
                ordem.append(filas[grupo].pop(0))
                avancou = True
        if not avancou:
            break
    return ordem


TERMOS_BUSCA = _ordenar_termos_ponderados(TERMOS_CARGO + TERMOS_FERRAMENTA)

# Termos que rodam em TODO ciclo, fora do rodízio.
#
# MEDIDO: uma vaga real ("Analista de Dados", JCPM Shoppings, Recife) não
# foi notificada. O título bate a keyword mais forte da lista e o local é
# uma das 8 cidades — passaria no filtro sem esforço. Ela nunca chegou a ser
# BUSCADA: com 44 termos e 10 por ciclo, uma volta completa leva 13 horas, e
# o rodízio é alfabético — "analista de dados" disputa vez de igual pra igual
# com "bigquery" e "looker". Vaga publicada logo depois da passagem do termo
# fica invisível por meio dia, e em portal que recebe vaga o tempo todo isso
# é tempo demais.
#
# Prioridade não é sobre volume, é sobre o que define o perfil: são os
# títulos que a usuária de fato procura, e os que mais aparecem nas vagas
# que já foram aprovadas. Passam de 1x a cada 13h para 8x por dia.
#
# Custo: bloco por ciclo vai de 10 para 15 termos (+50%). O ciclo medido é
# de 18 min desde que o Indeed saiu, então cabe — antes disso, com 37 min,
# não caberia. É essa folga que torna a mudança possível agora.
TERMOS_PRIORITARIOS = [
    "analista de crm",
    "analista de crm júnior",
    "analista de crm junior",
    "analista crm jr",
    "analista jr de crm",
    "crm",
    "customer success",
    "analista cs jr",
    "customer success analyst jr",
    "customer experience",
    "cx analyst jr",
    "analista de cx jr",
    "experiência do cliente",
    "customer onboarding",
    "crm operations",
    "cs ops",
    "business operations",
    "sales operations",
    "revops",
    "marketing operations",
    "analista de suporte junior",
    "analista de service desk junior",
    "analista de operacoes junior",
    "analista de processos junior",
    "analista de dados junior",
    "analista de bi junior",
    "junior data analyst",
    "project assistant",
]

# Medido: os TERMOS_BUSCA inteiros (hoje 42) rodando em TODO ciclo é o que
# gera as centenas de sessões de navegador por execução — o custo cresce
# linear com o tamanho da lista, e a lista só cresce (mais ainda com a
# expansão internacional puxando mais termos no radar). TERMOS_POR_CICLO é
# o tamanho do BLOCO usado por ciclo, não o total de termos — main.py roda
# um bloco por vez em rodízio (ver _proximo_bloco_termos) e avança pro
# próximo bloco no ciclo seguinte, salvando a posição no jobs.db. Isso
# desacopla custo por ciclo de tamanho da lista: dobrar TERMOS_BUSCA dobra
# quantos ciclos até cobrir tudo de novo, não o custo de cada ciclo.
TERMOS_POR_CICLO = 10

# Recência estrita do perfil Brasil: data original comprovada, não data de coleta.
DIAS_MAXIMOS_PUBLICACAO = 5

# Onde vaga HIBRIDA ou PRESENCIAL e aceita (mais "Remoto", que nao e
# cidade e sim a porta de entrada da regra de modalidade remota — ver
# _FLAGS_REMOTO em job.py). Vaga hibrida/presencial fora desta lista e
# rejeitada; e uma whitelist, nao uma preferencia de ordenacao.
#
# Lista revisada contra o requisito escrito pela usuaria: as seis cidades
# obrigatorias sao Campina Grande, Joao Pessoa, Recife, Natal, Caruaru e
# Manaus. Maceio e Aracaju ficam por decisao explicita dela (interessam,
# mesmo fora do requisito minimo).
#
# MEDIDO: a lista anterior era "Nordeste", nao "as cidades que interessam",
# e divergia do requisito nos dois sentidos ao mesmo tempo:
#   - FALTAVA Manaus. Confirmado em teste: "Manaus - AM" + Hibrido era
#     REJEITADA. Nenhuma vaga presencial/hibrida de Manaus podia entrar,
#     e a busca por cidade do LinkedIn (derivada desta lista) nunca
#     procurou la.
#   - SOBRAVAM Jaboatao, Teresina, Sao Luis e Petrolina, que aceitavam
#     hibrida/presencial fora da regra. Confirmado em teste.
# Nenhum dos 76 testes existentes cobria essas regras — por isso a
# divergencia sobreviveu. Agora esta em tests/test_regras_de_negocio.py.
#
# Custo: LOCATIONS_LINKEDIN_CIDADES_PRESENCIAL e derivada daqui, entao
# cada cidade e uma busca a mais por termo no LinkedIn. Sai de 11 cidades
# para 8 — menos requisicao por ciclo E cobrindo Manaus, que faltava.
CIDADES = ["Remoto"]

# MEDIDO: "Data Analyst @ Lisboa" e "Analista de Datos @ Madrid" reprovavam
# na localização, não no cargo — CIDADES acima é whitelist só de cidade
# brasileira, e a expansão de LOCATIONS_LINKEDIN pra Argentina/Chile (ver
# abaixo) passou a trazer vaga presencial/híbrida em Portugal/Espanha de
# vez em quando junto. Lista SEPARADA (não misturada em CIDADES, que
# continua só-Brasil de propósito — ver decisão registrada na criação do
# config_intl.py) com toggle próprio, pra dar pra ligar/desligar esse eixo
# sem mexer no resto do filtro. Canônica aqui porque config_intl.py já
# importa de config.py (não o contrário) — o pipeline internacional reusa
# essa mesma lista em vez de manter uma cópia (risco de divergir, mesmo
# motivo da unificação de _contem_termo/_tem_termo).
CIDADES_EUROPA_IBERICA = [
    "Portugal",
    "Lisboa",
    "Porto",
    "Braga",
    "Espanha",
    "España",
    "Spain",
    "Madrid",
    "Barcelona",
    "Valencia",
]

# Toggle independente do ATIVAR_EIXO_IBERICO de config_intl.py — são dois
# eixos diferentes (esse aqui é do pipeline BR/main.py, aquele é do
# pipeline internacional/main_intl.py), cada um com seu próprio liga/
# desliga, mesmo compartilhando a mesma lista de cidades acima.
#
# DESLIGADO: do mercado internacional, só interessa vaga remota — vaga
# presencial/híbrida em Lisboa/Madrid (o que esse eixo notifica, marcada
# "exploratória") não é o que o usuário quer. CIDADES_EUROPA_IBERICA
# continua definida (não precisa apagar) pra caso o eixo volte a ser
# ligado depois — só o toggle muda.
ATIVAR_EIXO_IBERICO_BR = False

# LinkedInScraper é a única fonte do pipeline BR que também alcança vaga
# fora do Brasil (as outras são portais brasileiros) — mas até aqui rodava
# só com location=Brasil fixo no código (scrapers/linkedin.py:88), então
# essa "porta pra fora" nunca era usada.
#
# Mercado "casa": busca modalidade completa (presencial/híbrida + remoto),
# porque o usuário mora aqui e vaga local de verdade interessa.
# MEDIDO (2026-08-20): o endpoint de visitante do LinkedIn NÃO resolve
# "Brasil" — e não devolve erro. Ele devolve um resultado genérico dos EUA
# (Evansville-IN, Sandy-UT, Port Angeles-WA...), o MESMO que devolve pra
# qualquer location que ele não entende. Testado ao vivo, mesmo termo:
#     location="Brasil"  ->  10 vagas,  0 no Brasil
#     location="Brazil"  ->  10 vagas,  8 no Brasil
#
# Efeito no histórico: das 910 vagas que o LinkedIn já tinha trazido pro
# perfil BR, 281 eram dos EUA (o filtro descartava depois, mas elas ocupavam
# o orçamento de 20 resultados por termo) e só 19 eram do Brasil — e essas
# 19 vieram das buscas POR CIDADE, que resolvem normalmente. A passada
# nacional nunca trouxe uma vaga brasileira sequer.
#
# Foi assim que "Analista de Business Intelligence Pleno (Remoto)" da Vitru
# (Brasil/Remoto, relevância 7, APROVADA pelo filtro) nunca chegou a ser
# vista: ela é exatamente o caso que a passada nacional deveria cobrir.
LOCATIONS_LINKEDIN = ["Brazil"]

# Mercados adicionais: só busca REMOTA (f_WT=2) — vaga presencial/híbrida
# num país onde o usuário não mora não serve, então nem faz sentido gastar
# a passada nacional ali (era puro desperdício: Argentina/Chile já rodavam
# as duas passadas antes, mas a nacional nunca batia em CIDADES mesmo,
# que é só cidade brasileira). Espanhol ou português — mesmo critério do
# pipeline internacional. Lista reaproveita exatamente os países já usados
# e testados ao vivo no endpoint do LinkedIn em config_intl.py
# (LOCATIONS_INTL) — evita arriscar nome de país nunca testado (grafia
# errada ou região que o LinkedIn não resolve como location de verdade,
# como já visto com "LATAM"/"Latin America").
#
# CORRIGIDO (2026-08-20): esta lista dizia reaproveitar LOCATIONS_INTL, mas
# "México" e "Colômbia" tinham sido traduzidos pro português — e o LinkedIn
# não resolve nenhum dos dois. Medido ao vivo, mesmo termo:
#     "México"   -> 10 vagas,  0 no México  |  "Mexico"   -> 10, 10 no México
#     "Colômbia" ->  0 vagas               |  "Colombia" -> 10, 10 na Colômbia
# E no banco: o perfil internacional (LOCATIONS_INTL, em inglês) tinha 110
# vagas do México e 48 da Colômbia; o perfil BR, zero de cada.
#
# "Espanha" FICA como está: foi medido e resolve (9 de 10 na Espanha, 215
# vagas no histórico). Argentina/Chile/Portugal se escrevem igual nos dois
# idiomas. Ou seja: só muda o que está comprovadamente quebrado.
LOCATIONS_LINKEDIN_REMOTO_APENAS = []

# MEDIDO: a passada nacional acima (location="Brazil") varre o país inteiro
# e só sobra o que bate em CIDADES depois do filtro — pra termo concorrido
# em SP/RJ/MG (a maioria), as 3 páginas (30 resultados) nunca chegam numa
# vaga de cidade menor do Nordeste, porque o volume dos polos maiores
# ocupa tudo antes. Testado ao vivo: página 1 de "analista de dados" em
# Brasil inteiro veio 100% São Paulo/Curitiba/Brasília, nenhuma do
# Nordeste. Busca ESPECÍFICA por cidade não depende de volume nacional —
# o próprio location= do LinkedIn já restringe o resultado à cidade, então
# funciona mesmo quando SP/RJ dominam o termo. "Remoto" (item de CIDADES)
# não é local de busca de verdade — sai da lista, já coberto pela passada
# remoto=True de LOCATIONS_LINKEDIN acima.
LOCATIONS_LINKEDIN_CIDADES_PRESENCIAL = [c for c in CIDADES if c != "Remoto"]

# Mercado que a vaga remota precisa aceitar pra contar, quando o texto de
# local DECLARA um escopo geográfico ("Remote — US only", "Remote — India").
# Ver Job.escopo_remoto/RegrasFiltro.mercados_remoto_aceitos em job.py — sem
# isso, uma vaga remota só pra outro país passava igual a uma remota de
# verdade pro Brasil. Vaga remota SEM escopo declarado no texto (a grande
# maioria) continua batendo normalmente, isso só filtra quando a fonte
# EXPLICITA um mercado incompatível.
#
# MEDIDO: Argentina/Chile/México/Colômbia ENTRAM nominalmente agora — a
# suposição de que "LATAM" cobria os quatro como guarda-chuva só valia
# enquanto extrair_escopo_remoto resolvia o texto pra "LATAM" literal.
# Depois que passou a reconhecer cidade (Buenos Aires/Santiago/Cidade do
# México/Bogotá — ver _CIDADES_MERCADO em job.py), o escopo passou a
# resolver pro PAÍS específico, não mais pro guarda-chuva — e o país
# específico nunca esteve nessa lista. Resultado: LOCATIONS_LINKEDIN_
# REMOTO_APENAS pagava o custo de buscar nesses 4 países e o filtro
# descartava tudo que a busca trazia de lá. "LATAM" continua na lista pra
# quando o texto disser isso literalmente (guarda-chuva de verdade, não
# substituto de nome de país). Portugal e Espanha entraram nominalmente
# pelo mesmo motivo, desde antes.
MERCADOS_REMOTO_ACEITOS = ["Brasil"]

INTERVALO_MINUTOS = int(os.getenv("INTERVALO_MINUTOS", 180))

# Digest ranqueado (item 08): vaga com Job.pontuar_relevancia() >= este
# limiar notifica na hora (como sempre foi); abaixo disso, fica na fila do
# digest diário — ver _enviar_digest_diario em main.py.
#
# MEDIDO: rodei o score contra as ~305 vagas do jobs.db real que ainda
# batem as regras atuais. Distribuição: score 4 (2%), 5 (24%), 6 (67%),
# 7 (5%), 8 (2%) — nada em 9-10 na amostra (exige acertar praticamente
# todo sinal ao mesmo tempo: cargo forte + ferramenta + senioridade alvo +
# mercado confirmado). Limiar 7 deixa ~7% imediata e ~93% no digest — bate
# com o pedido ("vaga de score alto na hora, resto agrupado"); 6 deixava
# 74% imediata (pouca redução de ruído); 8 deixava só 2% (digest com
# praticamente tudo, quase nenhuma vaga "excelente" se destacando na hora).
LIMIAR_RELEVANCIA_MINIMA = 7
LIMIAR_DIGEST_IMEDIATO = 7

# Hora UTC a partir da qual o digest diário pode sair (uma vez por perfil,
# por dia — ver _enviar_digest_diario em main.py). A regra é "ainda não
# enviei hoje E já passou desta hora", então o digest sai no PRIMEIRO ciclo
# do dia UTC que TERMINAR depois dela — não numa janela exata de 1 hora,
# que era o que impedia o disparo de acontecer (o ciclo dura ~80 min e
# nunca terminava dentro da janela).
#
# 9 UTC: o ciclo que começa às 09:00 UTC termina por volta das 10:20 UTC =
# 07:20 em Brasília (UTC-3). Escolhido pela usuária: chega de manhã, com a
# lista do dia anterior pronta pra revisar, em vez de de madrugada.
#
# Era 0 (= ~22h20 de Brasília), mas esse valor nunca foi uma escolha de
# verdade — ficou assim desde que o recurso foi escrito e nunca chegou a
# funcionar, então nunca houve como perceber que horário dava na prática.
#
# Se o ciclo das 09:00 falhar num dia, o das 12:00 (13:20 UTC) manda — a
# regra é "já passou de 9", não "é exatamente 9", então qualquer ciclo
# seguinte do mesmo dia UTC serve de recuperação.
DIGEST_HORA_UTC = 9

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Caminho ancorado na RAIZ do projeto, não na pasta deste arquivo.
#
# MEDIDO: o commit b8227b0 ("Reorganiza raiz: ... -> core/") moveu este
# config.py da raiz pra core/. Como DB_PATH era relativo a __file__, o
# banco se mudou junto, em silêncio: data/jobs.db virou core/data/jobs.db.
# Efeito real, confirmado em disco e no jobradar.log:
#   - data/jobs.db (1.080 vagas, versionado) ficou órfão;
#   - core/data/jobs.db nasceu vazio, então iniciar_db() passou a abortar
#     por BancoVazioSuspeito em toda execução local;
#   - no GitHub Actions a pasta core/data/ não existe no repositório, então
#     o banco era recriado do zero a cada run — toda vaga virava "nova"
#     (renotificação a cada 3h), o rodízio de termos travava no offset 0
#     (só os 10 primeiros de 44 termos eram buscados), a fila do digest era
#     descartada e o heartbeat saía a cada ciclo em vez de 1x/dia;
#   - o passo "git add data/jobs.db" do workflow não via mudança nenhuma
#     ("Nada novo pra commitar"), então o estado nunca mais persistiu.
#
# _RAIZ_PROJETO sobe um nível a partir de core/, então o caminho deixa de
# depender de onde este arquivo mora — mover config.py de novo não move
# mais o banco junto. Coberto por tests/test_db_path.py, pra uma
# reorganização futura quebrar o teste em vez da produção.
#
# JOBRADAR_DB_PATH existe pra apontar um banco descartável em teste/
# experimento sem risco de escrever no banco real.
_RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.getenv("JOBRADAR_DB_PATH") or os.path.join(_RAIZ_PROJETO, "data", "jobs.db")