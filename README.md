# JobRadar

> Projeto de estudo e adaptação modelado a partir do [JobRadar de Liliam Kezia Oliveira Souza](https://github.com/liliamkezia-star/job-radar). A referência é reconhecida; este repositório não apresenta o trabalho como criação totalmente original.

Automação para buscar, filtrar e organizar vagas com critérios configuráveis. O projeto explora coleta de dados, regras de negócio explicáveis, deduplicação, persistência em SQLite e notificações.

## Tecnologias

Python · Playwright · requests · SQLite · pytest · GitHub Actions · Telegram

## Fluxo

1. Consulta fontes de vagas configuradas.
2. Normaliza os resultados e aplica critérios de cargo, localidade, modalidade e data.
3. Calcula relevância com regras explícitas e elimina duplicatas.
4. Persiste o estado em SQLite e envia notificações pelo Telegram.
5. Executa verificações automatizadas no GitHub Actions.

Este projeto usa regras determinísticas; não utiliza modelos de IA ou aprendizado de máquina para classificar vagas.

## Executar localmente

Requer Python 3.11 ou superior.

```bash
git clone https://github.com/tuliohw1-arch/job-radar-main-tulio.git
cd job-radar-main-tulio/job-radar-main
python -m venv .venv
```

Ative o ambiente virtual e instale as dependências:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

Configure `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` no ambiente local. Nunca coloque credenciais em arquivos versionados.

```bash
python main.py --perfil brasil --once
pytest tests/ -q
```

## Estrutura

O código, testes e documentação ficam em [`job-radar-main/`](job-radar-main/). Consulte o [README detalhado](job-radar-main/README.md) para configuração, execução e limitações.

## Créditos e licença

A ideia e o projeto de referência são de [Liliam Kezia Oliveira Souza](https://github.com/liliamkezia-star/job-radar). Esta versão é um estudo modelado a partir desse trabalho. O arquivo [`LICENSE`](job-radar-main/LICENSE) foi mantido; consulte seus termos antes de reutilizar ou distribuir o código.