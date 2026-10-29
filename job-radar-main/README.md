<div align="center">

# 📡 JobRadar
### Monitor de vagas remotas de CRM e áreas adjacentes

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-Scraping-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Banco%20versionado-07405E?style=for-the-badge&logo=sqlite&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Cron-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)
![Tests](https://img.shields.io/badge/testes-automatizados-informational?style=for-the-badge)
![Status](https://img.shields.io/badge/status-em%20revis%C3%A3o-informational?style=for-the-badge)

**Autora:** Liliam Kezia Oliveira Souza

</div>

---

## 💎 Proposta de valor

> Em cidade pequena, vaga boa de Dados/BI aparece pouco e some rápido — quem checa o board duas vezes por dia perde para quem checou na primeira hora. **JobRadar** substitui essa checagem manual: varre **9 fontes** a cada **3 horas**, filtra por cargo, cidade, mercado e idioma em três níveis de confiança, pontua cada vaga por relevância e notifica no Telegram — de graça, sem servidor próprio, 24 horas por dia.

## 📄 Resumo executivo

Entre 07 e 29 de agosto de 2026, o sistema processou **2.285 vagas únicas** sem intervenção manual.

| Indicador | Número |
|---|---|
| 📊 Vagas processadas (deduplicadas) | **2.285** |
| 🧪 Testes automatizados (CI a cada push) | **481** |
| 🌎 Fontes monitoradas | **9** |
| 🏙️ Cidades-alvo + remoto | **9 + remoto** |
| ⏱️ Frequência de checagem | **a cada 3h** |
| 🔗 Concentração numa única fonte (LinkedIn) | **93,8%** ⚠️ |
| 💰 Custo de infraestrutura | **R$ 0** |

A concentração em LinkedIn está documentada como **risco**, não como conquista: o endpoint usado não é oficial, e o sistema perde quase todo o alcance se ele mudar ou bloquear. Ver [Limites conhecidos](#-limites-conhecidos).

---

## 🔬 Como as decisões são tomadas

Esta é a parte do projeto que mais me interessa como analista: **nenhuma mudança de comportamento entra sem medição antes.** Não porque seja elegante, mas porque a alternativa falhou de forma cara — e a maior parte dos defeitos encontrados aqui era invisível no log.

O padrão que se repetiu: o robô parecia saudável, o GitHub Actions ficava verde, vagas chegavam normalmente — e mesmo assim faltava vaga. Cada caso só apareceu quando alguém desconfiou de um **número**, não de uma mensagem de erro.

**Dois exemplos, com o antes e depois medidos:**

O LinkedIn não reconhece `location=Brasil`. Ele não devolve erro — devolve um resultado genérico dos Estados Unidos, indistinguível de uma busca bem-sucedida. A busca nacional brasileira nunca funcionou, e ninguém tinha como notar.

| LinkedIn (perfil Brasil) | Vagas | Do Brasil | Dos EUA |
|---|---|---|---|
| Antes (`location=Brasil`) | 910 | **19 (2,1%)** | 268 |
| Depois (`location=Brazil`) | 813 | **354 (43,5%)** | **0** |

O card do LinkedIn traz a data de publicação em inglês (`"4 months ago"`), mas a extração procurava padrões em português. O campo vinha vazio, então vaga de quatro meses era notificada como se fosse nova.

| Data de publicação preenchida | Antes | Depois |
|---|---|---|
| Vagas do LinkedIn com data | 231/1.639 (14,1%) | **504/504 (100%)** |

**Três hipóteses minhas foram derrubadas pelos próprios dados** — e é isso que a medição serve para fazer:

- *"Esses avisos de vaga perdida são alarme falso"* — eram, em três fontes. Na quarta, não: as buscas devolviam 10 resultados quando rodadas isoladas. O aviso estava certo e vaga estava sendo perdida.
- *"O perfil internacional só precisa das keywords que o Brasil já tem"* — alinhar as listas ganhou **zero** vaga. O que ganhou 7 foi um mecanismo que aquele perfil não tinha.
- *"Cidade pequena com ferramenta de nicho não tem vaga mesmo"* — tinha 10.

Quando a medição não é possível, isso fica escrito no código em vez de escondido. A correção de rate-limit do LinkedIn, por exemplo, só se manifesta no IP de datacenter do GitHub Actions e não reproduz localmente — então foi desenhada para ser **segura por construção**: ajuda se o diagnóstico estiver certo, e não piora nada se estiver errado.

---

## 📸 Como chega para você

Vaga de alta relevância chega na hora, com nível, data de publicação e link. O resto entra num resumo diário ranqueado — sem virar spam. Vaga com mais de 30 dias ganha aviso de "pode já estar preenchida" e sai do alerta imediato, mas nunca é descartada.

---

## 🗂️ Sumário

- [Como as decisões são tomadas](#-como-as-decisões-são-tomadas)
- [Como funciona (pipeline)](#-como-funciona-pipeline)
- [Arquitetura técnica](#%EF%B8%8F-arquitetura-técnica)
- [Regras de negócio](#-regras-de-negócio)
- [Estrutura do repositório](#-estrutura-do-repositório)
- [Como rodar](#-como-rodar)
- [Testes](#-testes)
- [Limites conhecidos](#-limites-conhecidos)

---

## 🧭 Como funciona (pipeline)

| Etapa | O que faz |
|---|---|
| **Busca** | Varre as fontes em paralelo, com rodízio de termos para controlar custo por ciclo |
| **Filtra** | Cargo (forte / ambíguo + qualificador / ferramenta + cargo), cidade ou mercado remoto, idioma |
| **Pontua** | Compatibilidade 0–100 baseada na descrição e no perfil; score histórico 0–10 permanece apenas para ordenação visual e encaminhamento ao digest |
| **Deduplica** | Por link e por empresa+título, para pegar a mesma vaga republicada em fonte diferente |
| **Notifica** | Alta relevância na hora; o resto num resumo diário ranqueado, melhor vaga no topo |
| **Aprende** | Botão 👍/👎 em cada notificação — feedback vira dado para medir precisão por fonte e por semana |

## 🏗️ Arquitetura técnica

- **Filtro em 3 níveis de confiança:** cargo inequívoco passa sozinho; cargo ambíguo (ex: `Analyst`) só conta com um qualificador de dados junto no título; ferramenta (ex: `Power BI`) só conta com palavra de cargo junto. Nada aprova por palavra solta — é o que segura `Financial Analyst` e `HR Analyst` fora do radar.
- **Compatibilidade explicável (0–100):** combina família profissional, experiência operacional transferível, ferramentas comprovadas, alinhamento CRM/HubSpot, senioridade e remoto. Pesos ficam em `core/compatibilidade.py`; SQL e outras ferramentas em desenvolvimento são registradas como lacunas, não como experiência comprovada.
- **Zero infraestrutura:** GitHub Actions como motor de cron, SQLite como banco versionado no próprio Git. O histórico de vagas já vistas *é* o commit.
- **Resiliente:** nunca marca vaga como vista sem confirmar que a notificação saiu; alerta se a maioria das fontes falhar num ciclo; heartbeat diário confirmando que o robô está de pé; segunda tentativa quando uma busca volta vazia.
- **Testes automatizados em CI:** a suíte cobre filtros, scrapers, datas, extração de descrições, scoring, persistência, auditoria e notificações simuladas; os resultados atuais devem ser conferidos na execução do GitHub Actions vinculada à PR.

## 📋 Regras de negócio

O filtro existe para uma busca específica, e as regras estão explícitas em `core/config.py`:

- **Brasil remoto:** somente vagas explicitamente remotas e com escopo de contratação no Brasil.
- **Recência:** no perfil Brasil, a data original deve ser verificável e ter no máximo 5 dias; data de coleta nunca substitui data de publicação.
- **Híbrido e presencial:** sempre rejeitados, inclusive em Belo Horizonte.
- **Internacional:** o workflow não executa o perfil internacional; vagas com escopo explícito fora do Brasil ou sem escopo confirmado são rejeitadas.
- **Taxonomia de carreira (Brasil):** grupos A — CRM/CRM Operations/CS Ops (40%), B — Business Operations/Sales Ops/RevOps/implantação/onboarding (40%) e C — Marketing Operations/automação/suporte SaaS (20%). Os pesos são uma proposta de priorização, não probabilidades de contratação.
- **Compatibilidade:** CRM/CRM Operations é prioridade; CS Ops e operações adjacentes entram por títulos específicos. Vagas abaixo de 55/100 de compatibilidade são descartadas; o score histórico 0–10 não é o filtro eliminatório.

Cidade homônima é tratada: `Campina Grande do Sul, Paraná` e `Fortaleza de Minas, Minas Gerais` são barradas pela conferência de UF, que entende tanto a sigla quanto o estado por extenso.

## 📁 Estrutura do repositório

```
JobRadar/
├── main.py                      ← motor único: um ciclo de busca por perfil
├── relatorio_precisao.py        ← aprovadas/notificadas por fonte e por semana
├── core/
│   ├── perfis.py                ← Brasil vs Internacional (dado, não lógica duplicada)
│   ├── config.py                ← cargos, cidades, termos, pesos (perfil Brasil)
│   ├── config_intl.py           ← o mesmo para o perfil internacional
│   ├── job.py                   ← Job, filtro, score de relevância
│   └── logger.py
├── database/
│   └── database.py              ← SQLite: dedup, fila do digest, metadados
├── notifier/
│   └── telegram.py              ← notificação individual, digest, botão 👍/👎
├── scrapers/                    ← um módulo por fonte
├── tests/                       ← 481 casos, roda em CI a cada push
├── data/
│   └── jobs.db                  ← banco versionado (histórico de dedup)
└── .github/workflows/
    ├── jobradar.yml             ← cron de produção (a cada 3h)
    └── testes.yml               ← CI
```

## 💻 Como rodar

```bash
git clone <repo>
cd JobRadar
python -m venv venv && venv\Scripts\activate   # Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

Criar `.env` na raiz com `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` (via [@BotFather](https://t.me/BotFather)), depois:

```bash
python main.py --perfil brasil internacional --once   # um ciclo e encerra
python main.py --perfil brasil                        # contínuo, a cada 3h
```

Para testar sem tocar no banco de produção:

```bash
JOBRADAR_DB_PATH=data/teste.db python main.py --perfil brasil --once
```

## 🧪 Testes

```bash
pytest tests/ -v
```

A suíte cobre filtros, regras de negócio, paginação das fontes, datas de publicação, extração de descrições, compatibilidade 0–100, persistência e notificações simuladas — todos rodando a cada push via GitHub Actions.

Os testes seguem uma convenção: **cada arquivo começa explicando o bug real que o motivou**, com o número medido. Um teste que só afirma que `2 + 2 = 4` não conta; o que conta é o que quebrou de verdade e como se descobriu.

## ⚠️ Limites conhecidos

Registrados de propósito — problema documentado é problema que alguém pode consertar.

| Limite | Situação |
|---|---|
| **93,8% das vagas vêm do LinkedIn** | Endpoint não oficial. Se mudar ou bloquear, o sistema perde quase todo o alcance. |
| **Rate-limit em IP de datacenter** | Buscas voltam vazias no GitHub Actions e não reproduzem em rede residencial. Mitigado com segunda tentativa; a verificação vem dos logs de produção. |
| **Fontes secundárias rendem pouco** | Catho, GeekHunter e 99Jobs somam menos de 3% das vagas. Funcionam — só não têm volume no nicho buscado. Mantidas porque o critério de remoção é estar quebrada, não render pouco. |
| **Descrição indisponível ou bloqueada** | A extração tenta dados estruturados, metadados, HTML visível e fallback com Playwright. Se a descrição continuar ausente/incompleta, a avaliação fica marcada como insuficiente e o score é limitado; o sistema não inventa requisitos. |
| **Ruído aceito conscientemente** | `Data Center Operations Analyst` passa, porque "data center" casa o qualificador "data". Não apareceu nas amostras medidas; está fixado em teste para quando incomodar. |

---

<div align="center">

*Case de portfólio em automação de dados — Python, Playwright, SQLite, GitHub Actions e engenharia de filtro sem ML.*

</div>

## Expansão de famílias profissionais (perfil Brasil)

O pool de títulos do perfil Brasil também cobre agora:

- **Suporte e operações de TI:** analista de TI/suporte técnico/service desk júnior, operações de TI, suporte a sistemas e implantação de sistemas.
- **Operações, processos e projetos:** operações e processos júnior, operações de negócio, analista/assistente de projetos, PMO, implantação e requisitos.
- **Customer Success/CX:** operações de clientes, onboarding, implantação de clientes, CX júnior e qualidade de atendimento.
- **Dados e indicadores:** analista de indicadores, dados/BI júnior, assistente de BI, relatórios, performance operacional e dados de clientes.
- **Variações em inglês:** títulos equivalentes como *Junior IT Support Analyst*, *Junior Operations Analyst*, *Junior Data Analyst* e *Reporting Analyst*.

Os títulos são específicos; palavras isoladas como “analista”, “suporte” ou “dados” não aprovam uma vaga por si só. O perfil Brasil continua exigindo remoto confirmado, escopo de contratação compatível com o Brasil e publicação verificável nos últimos `DIAS_MAXIMOS_PUBLICACAO` dias. A expansão de taxonomia não altera a janela de cinco dias nem os filtros de modalidade.

**Estado atual da classificação:** o modelo `Job` já armazena descrição, origem/estado da extração, responsabilidades e requisitos identificados, além do score de compatibilidade 0–100 e suas justificativas. A escala histórica 0–10 permanece apenas para a lógica visual/roteamento legada; o corte eliminatório usa 55/100. Nem toda fonte publica o corpo completo, por isso resumos de SEO e páginas bloqueadas são marcados como incompletos/indisponíveis e não são tratados como descrição completa.



## Extração, compatibilidade e auditoria do funil

- **Descrição:** Gupy e Sólides usam o texto já disponível no payload quando existe. Para demais anúncios, o extrator tenta JSON-LD `JobPosting`, metadados de descrição, texto HTML visível e, como fallback, conteúdo renderizado via Playwright. Redirecionamentos são seguidos; HTTP, timeout e estrutura sem descrição ficam registrados como erro/estado de extração.
- **Estado explícito:** `completa` exige pelo menos 180 caracteres de conteúdo; textos curtos são `incompleta`; páginas sem texto útil são `indisponivel`. Responsabilidades e requisitos são separados quando os cabeçalhos podem ser reconhecidos; ferramentas citadas e senioridade explícita também são extraídas. A modalidade declarada na descrição pode corrigir um card contraditório. O texto original normalizado é preservado para avaliação.
- **Segunda chance por conteúdo:** vagas do perfil Brasil que são explicitamente remotas e passam a localização, mas não passam pelo título, podem ser avaliadas pela descrição. Só são recuperadas com descrição completa, evidência de família profissional e score acima do limiar.
- **Escopo Brasil:** o perfil Brasil descarta modalidade que não esteja confirmada como `Remoto`; cidade ou nome da empresa não substituem confirmação de trabalho 100% remoto. A janela de publicação verificável continua em cinco dias.
- **Score:** `core/compatibilidade.py` usa pesos configuráveis e produz pontuação 0–100, critérios positivos, lacunas, requisitos obrigatórios sinalizados e aviso de informação insuficiente. O limiar inicial é 55/100; não é uma probabilidade de contratação.
- **Auditoria por vaga/ciclo:** `core/auditoria.py` registra ID, URL original, fonte, etapa e motivo em `data/audit/ciclos.jsonl`. O workflow publica esse arquivo como artifact por 30 dias. O SQLite também persiste score, status de descrição e justificativa para vagas registradas.
- **Telegram:** respostas HTTP 429/5xx têm tentativas limitadas; timeouts sem resposta não são repetidos imediatamente porque o servidor pode ter aceitado a mensagem. A vaga não é marcada como vista quando o envio falha, permitindo nova tentativa no ciclo seguinte.
- **Validação real:** os testes automatizados simulam a API Telegram. Um envio real só pode ser declarado validado quando uma execução de produção comprovar a entrega usando os segredos do repositório; os testes nunca enviam mensagens reais.
