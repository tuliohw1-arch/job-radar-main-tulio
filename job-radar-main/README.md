# JobRadar — projeto de estudo baseado em referência

> **Origem e atribuição:** este projeto foi modelado a partir do [JobRadar de Liliam Kezia Oliveira Souza](https://github.com/liliamkezia-star/job-radar), apresentado também [nesta publicação no LinkedIn](https://pt.linkedin.com/posts/liliamkezia_python-dados-bi-activity-7494394777455542272-4tfh). Esta versão não é apresentada como criação inteiramente original. A autoria da referência é reconhecida; este repositório documenta uma versão de estudo/adaptação.

## Objetivo

Automatizar a busca, filtragem e organização de oportunidades de trabalho segundo critérios configurados, usando Python. O projeto explora coleta de dados, regras de negócio, deduplicação, persistência local e notificações.

## Tecnologias e componentes

Conforme a estrutura atual do repositório:

- **Python** para a aplicação e as regras de filtragem.
- **Playwright** e `requests` para consultar fontes de vagas.
- **SQLite** para manter o histórico e evitar notificações duplicadas.
- **GitHub Actions** para automação de execução e integração contínua.
- **pytest** para os testes automatizados.
- **Telegram** para notificações.

Os critérios e fontes são específicos desta versão e podem mudar. O ranqueamento é feito por regras explícitas; não é um sistema de inteligência artificial ou aprendizado de máquina.

## Como funciona

1. Consulta fontes configuradas.
2. Normaliza as vagas e aplica critérios de cargo, localização, modalidade e recência.
3. Calcula relevância com regras explícitas e remove duplicatas.
4. Registra o estado no SQLite.
5. Envia notificações pelo Telegram e executa verificações automatizadas no GitHub Actions.

## Execução local

Requisitos: Python 3.11 ou superior.

```bash
git clone https://github.com/tuliohw1-arch/job-radar-main-tulio.git
cd job-radar-main-tulio/job-radar-main
python -m venv .venv
```

Ative o ambiente virtual e instale as dependências:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
python -m playwright install chromium
```

Configure `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` no ambiente local antes de executar. Não compartilhe esses valores nem os salve no repositório.

```bash
python main.py --perfil brasil --once
pytest tests/ -v
```

## Limitações

- As fontes externas e seus formatos podem mudar, interrompendo a coleta.
- A disponibilidade e a cobertura das vagas dependem das fontes consultadas.
- Os critérios de filtragem podem deixar passar oportunidades ou descartar vagas relevantes.
- A automação não envia candidaturas; as oportunidades devem ser avaliadas manualmente.

## Créditos e licença

A referência original é de **Liliam Kezia Oliveira Souza**: [JobRadar original](https://github.com/liliamkezia-star/job-radar). Este trabalho reconhece essa origem e se apresenta como estudo baseado em uma solução existente.

O arquivo `LICENSE` deste repositório foi preservado. Consulte-o para os termos aplicáveis; este README não concede permissões adicionais nem substitui esses termos.