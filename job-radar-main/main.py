
import argparse
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

from core.config import (
    DIAS_MAXIMOS_PUBLICACAO,
    DIGEST_HORA_UTC,
    INTERVALO_MINUTOS,
    LIMIAR_DIGEST_IMEDIATO,
    LIMIAR_RELEVANCIA_MINIMA,
)
from database.database import (
    BancoVazioSuspeito,
    definir_metadado,
    iniciar_db,
    ja_vista,
    marcar_digest_enviado,
    obter_metadado,
    obter_vagas_pendentes_digest,
    salvar_vaga,
)
from notifier.telegram import (
    enviar_digest,
    enviar_mensagem,
    notificar_vaga,
    notificar_vaga_exploratoria,
    processar_feedback_pendente,
)
from core.perfis import FREQUENCIA_ALTA, FREQUENCIA_BAIXA, PERFIS, Perfil
from utils.filtro import filtrar_publicadas_recentemente, filtrar_vagas
from core.logger import get_logger
from core.auditoria import AuditoriaCiclo
from core.compatibilidade import (
    LIMIAR_COMPATIBILIDADE_MINIMA,
    pontuar_compatibilidade,
)
from core.descricao import analisar_secoes, extrair_descricao, normalizar_texto

logger = get_logger()


def _enriquecer_e_pontuar(vaga, cache_descricoes: dict[str, dict]) -> None:
    """Completa a descrição uma vez por URL e anexa score/justificativas."""
    descricao_atual = (getattr(vaga, "descricao", "") or "").strip()
    if len(descricao_atual) < 180:
        chave = (vaga.link or "").split("#", 1)[0]
        resultado = cache_descricoes.get(chave)
        if resultado is None:
            resultado = extrair_descricao(vaga.link)
            cache_descricoes[chave] = resultado
        descricao_extraida = resultado.get("descricao", "")
        if len(descricao_extraida) > len(descricao_atual):
            descricao_atual = descricao_extraida
            vaga.origem_descricao = resultado.get("origem_descricao", "")
            vaga.status_extracao = resultado.get("status_extracao", "indisponivel")
            vaga.erro_extracao = resultado.get("erro_extracao", "")
        elif not descricao_atual:
            vaga.erro_extracao = resultado.get("erro_extracao", "")
            vaga.status_extracao = resultado.get("status_extracao", "indisponivel")
    if descricao_atual:
        vaga.descricao = normalizar_texto(descricao_atual)
        if len(vaga.descricao) >= 180:
            vaga.status_extracao = "completa"
        elif vaga.status_extracao not in ("incompleta", "indisponivel"):
            vaga.status_extracao = "incompleta"
        secoes = analisar_secoes(vaga.descricao)
        vaga.responsabilidades = secoes["responsabilidades"]
        vaga.requisitos_obrigatorios = secoes["requisitos_obrigatorios"]
        vaga.requisitos_desejaveis = secoes["requisitos_desejaveis"]
    else:
        vaga.descricao = ""
        vaga.status_extracao = vaga.status_extracao or "indisponivel"
        vaga.responsabilidades = []
        vaga.requisitos_obrigatorios = []
        vaga.requisitos_desejaveis = []

    resultado_score = pontuar_compatibilidade(vaga)
    vaga.compatibilidade_score = resultado_score["score"]
    vaga.compatibilidade_criterios = resultado_score["criterios_positivos"]
    vaga.compatibilidade_lacunas = resultado_score["lacunas"]
    vaga.compatibilidade_requisitos_nao_atendidos = resultado_score["requisitos_obrigatorios_nao_atendidos"]
    vaga.compatibilidade_justificativa = resultado_score["justificativa"]
    vaga.compatibilidade_informacoes_insuficientes = resultado_score["informacoes_insuficientes"]


def _chave_fonte_baixa_frequencia(perfil: Perfil, nome_scraper: str) -> str:
    """Estado diário por fonte, para uma falha não bloquear as outras."""
    return f"baixa_frequencia_ultimo_dia_{perfil.chave}_{nome_scraper}"


def _construir_scrapers(perfil: Perfil, termos_busca: list[str]):
    """Inclui fontes de baixa frequência até cada uma concluir uma coleta.

    O estado é por scraper: uma fonte que falha não fica marcada como feita
    apenas porque o ciclo começou, e as fontes que funcionaram não repetem
    trabalho desnecessário nos ciclos seguintes do mesmo dia.
    """
    hoje = date.today().isoformat()
    scrapers = []
    for definicao in perfil.definicao_scrapers:
        if definicao.frequencia == FREQUENCIA_ALTA:
            scrapers.append(
                definicao.classe(termos_busca=termos_busca, **definicao.kwargs_extras)
            )
            continue

        chave = _chave_fonte_baixa_frequencia(perfil, definicao.classe.__name__)
        if obter_metadado(chave) == hoje:
            continue
        scrapers.append(
            definicao.classe(termos_busca=termos_busca, **definicao.kwargs_extras)
        )

    return scrapers


def _marcar_fonte_baixa_frequencia_concluida(perfil: Perfil, scraper) -> None:
    """Marca só após a fonte devolver resultados sem exceção."""
    nome = scraper.__class__.__name__
    definicao = next(
        (d for d in perfil.definicao_scrapers
         if d.classe.__name__ == nome and d.frequencia == FREQUENCIA_BAIXA),
        None,
    )
    if definicao is None:
        return
    chave = _chave_fonte_baixa_frequencia(perfil, nome)
    definir_metadado(chave, date.today().isoformat())

def _proximo_bloco_termos(perfil: Perfil) -> list[str]:
    """Termos deste ciclo: os PRIORITÁRIOS (todo ciclo, fora do rodízio) mais
    um BLOCO fixo (perfil.termos_por_ciclo) do resto, começando de onde o
    ciclo anterior parou e avançando
    — volta pro início quando chega no fim da lista. A posição fica salva
    no jobs.db (tabela metadados, chave com sufixo do perfil — dois perfis
    rotacionam de forma independente), então sobrevive entre execuções do
    GitHub Actions (cada run é uma máquina nova).

    Isso é o que desacopla custo por ciclo do tamanho da lista de termos:
    lista grande leva mais ciclos pra cobrir tudo, mas cada ciclo individual
    continua custando o mesmo. Sem isso, dobrar a lista de termos dobrava o
    tempo de TODO ciclo.
    """
    # MEDIDO: uma vaga real ("Analista de Dados", JCPM Shoppings, Recife)
    # nunca foi notificada — e nao por causa do filtro: o titulo bate a
    # keyword mais forte da lista e Recife e uma das 8 cidades. Ela nunca
    # chegou a ser BUSCADA. Com 44 termos e 10 por ciclo, uma volta completa
    # leva 13 horas, e o rodizio e alfabetico: "analista de dados" disputa vez
    # de igual pra igual com "bigquery" e "looker".
    #
    # perfil.termos_prioritarios sai do rodizio e entra em TODO ciclo. Os
    # demais continuam rodando como antes, so que num conjunto menor.
    prioritarios = [t for t in perfil.termos_prioritarios if t in perfil.termos_busca]
    rodizio = [t for t in perfil.termos_busca if t not in prioritarios]

    total = len(rodizio)
    if total == 0:
        return list(prioritarios)

    tamanho_bloco = min(perfil.termos_por_ciclo, total)

    chave_offset = f"termos_offset_{perfil.chave}"
    offset_salvo = obter_metadado(chave_offset)
    # % total protege contra a lista ter encolhido desde o último ciclo
    # (termo removido do config.py) — sem isso, um offset salvo maior que o
    # tamanho atual da lista quebraria o acesso por índice abaixo.
    offset = int(offset_salvo) % total if offset_salvo else 0

    bloco = [rodizio[(offset + i) % total] for i in range(tamanho_bloco)]

    definir_metadado(chave_offset, str((offset + tamanho_bloco) % total))

    return list(prioritarios) + bloco


def _enviar_heartbeat_diario(
    perfil: Perfil, total_novas: int, scrapers_com_problema: list[str], total_fontes: int,
    auditoria: AuditoriaCiclo | None = None,
):
    """No máximo 1 mensagem por dia (por perfil) confirmando que o ciclo
    rodou.

    O alerta de saúde só dispara quando ≥50% das fontes falha — mas se o
    workflow parar de rodar por completo (cron desabilitado pelo GitHub
    Actions por inatividade do repositório, erro de config, etc.), não
    existe ALERTA NENHUM disso: silêncio no Telegram fica idêntico a "rodou
    e não achou vaga nova". O heartbeat fecha essa lacuna — se ele parar de
    chegar um dia, o problema é o workflow não estar rodando, não a busca
    não ter achado nada. Por perfil: silêncio só do perfil Internacional
    (por exemplo) fica visível mesmo com o perfil Brasil rodando normal.

    A data do último envio fica salva no próprio jobs.db (tabela
    metadados), então sobrevive entre execuções do GitHub Actions (cada
    run é uma máquina nova) e não manda duplicado se o workflow rodar mais
    de uma vez no mesmo dia (cron normal ou workflow_dispatch manual).
    """
    chave = f"heartbeat_ultimo_dia_{perfil.chave}"
    hoje = date.today().isoformat()
    if obter_metadado(chave) == hoje:
        return

    hora_brasilia = datetime.now(timezone.utc).strftime("%H:%M UTC")
    if scrapers_com_problema:
        status = f"{len(scrapers_com_problema)}/{total_fontes} fonte(s) com problema"
    else:
        status = "todas as fontes ok"

    enviado = enviar_mensagem(
        f"💓 <b>JobRadar {perfil.nome} ativo</b>\n\n"
        f"Confirmação diária: o ciclo rodou agora ({hora_brasilia}, {status}). "
        f"{total_novas} vaga(s) nova(s) neste ciclo.\n\n"
        "Se essa mensagem parar de chegar, o workflow parou de rodar — "
        "não que faltou vaga."
    )
    if enviado:
        definir_metadado(chave, hoje)
        if auditoria:
            auditoria.contar("mensagens_sistema_enviadas")
    else:
        if auditoria:
            auditoria.contar("mensagens_sistema_falhas")
        # Não registrar uma tentativa como envio: se o Telegram falhar
        # transitoriamente, o próximo ciclo precisa tentar novamente.
        logger.warning(
            f"[{perfil.nome}] Falha ao enviar heartbeat diário; "
            "nova tentativa será feita no próximo ciclo."
        )


def _enviar_digest_diario(perfil: Perfil, auditoria: AuditoriaCiclo | None = None):
    """No máximo 1 digest por dia (por perfil) — ver item 08. Junta tudo
    que ficou digest_pendente=1 desde o último envio (pode ser de vários
    ciclos de 3h) e manda ranqueado, melhor primeiro.

    Disparo: no ciclo cujo horário UTC bate com DIGEST_HORA_UTC (0 =
    meia-noite UTC = 21h em Brasília) — o cron já passa por essa hora
    exata todo dia, não precisa de agendamento à parte. Mesma lógica de
    "só uma vez por dia" do heartbeat (data salva em metadados), mas com
    um reforço: se por qualquer motivo o ciclo exato de DIGEST_HORA_UTC
    falhar/pular um dia inteiro, manda no primeiro ciclo depois de 24h
    sem envio — não deixa a fila crescer indefinidamente esperando um
    horário exato que pode não voltar a bater certo (ex: workflow atrasado
    pelo GitHub Actions naquele dia).
    """
    chave = f"digest_ultimo_dia_{perfil.chave}"
    agora = datetime.now(timezone.utc)
    # Dia em UTC, não date.today() (que é o dia LOCAL da máquina). A hora
    # comparada logo abaixo é UTC; misturar os dois dava resultado
    # diferente rodando no GitHub Actions (UTC) e na máquina da usuária
    # (UTC-3) — no Brasil, entre 21h e meia-noite o "hoje" local já é o
    # dia anterior ao "hoje" UTC.
    hoje = agora.date()

    if obter_metadado(chave) == hoje.isoformat():
        return

    # MEDIDO em produção: o digest NUNCA foi enviado. Prova direta — a
    # tabela metadados do jobs.db de produção tem heartbeat_ultimo_dia_*
    # (das duas chaves, atualizadas), e nenhum digest_ultimo_dia_*. O
    # heartbeat é disparado na linha ANTERIOR a esta função, no mesmo
    # ciclo: se ele chega e o digest não, a diferença é a condição de
    # horário. Resultado: 408 vagas presas na fila, acumulando desde que o
    # recurso existe, sem nunca chegar no Telegram.
    #
    # Eram duas causas somadas:
    #
    # 1. "agora.hour == DIGEST_HORA_UTC" exige que o ciclo TERMINE dentro
    #    de uma janela de 1 hora. Mas o cron só COMEÇA às 00:00 UTC e o
    #    ciclo dura ~80 min (medido pelos commits do robô: a execução das
    #    00:00 commitou às 02:14). Quando esta função roda, já é 1h ou 2h
    #    — a janela nunca está aberta.
    #
    # 2. A rede de segurança para o caso acima ("se pular um dia, manda no
    #    ciclo seguinte") exigia ultimo_envio_str is not None, ou seja, um
    #    envio anterior registrado. Como nunca houve o primeiro, ela nunca
    #    ligava: dependia exatamente daquilo que deveria consertar.
    #
    # A regra agora é "ainda não enviei hoje E já passou da hora
    # configurada" em vez de "a hora é exatamente X". Isso cobre os dois
    # casos de uma vez, sem precisar da rede de segurança separada: o
    # digest sai no PRIMEIRO ciclo do dia UTC que terminar depois de
    # DIGEST_HORA_UTC, independente de quanto o ciclo demorou ou de o
    # GitHub Actions ter atrasado o agendamento. Com DIGEST_HORA_UTC = 0,
    # é o primeiro ciclo de cada dia UTC (~22h de Brasília).
    #
    # Continua no máximo 1 por dia: o metadado só é gravado depois do
    # envio confirmado, e a checagem acima corta o resto do dia.
    if agora.hour < DIGEST_HORA_UTC:
        return

    vagas_pendentes = obter_vagas_pendentes_digest(perfil.chave)
    if not vagas_pendentes:
        # Marca mesmo sem vaga nenhuma — senão o "atrasado" acima dispara
        # todo ciclo seguinte até aparecer alguma vaga pendente de novo.
        definir_metadado(chave, hoje.isoformat())
        return

    if enviar_digest(vagas_pendentes, perfil.nome):
        if auditoria:
            auditoria.contar("lotes_digest_enviados")
            auditoria.contar("vagas_digest_enviadas", len(vagas_pendentes))
        marcar_digest_enviado(perfil.chave)
        definir_metadado(chave, hoje.isoformat())
        logger.info(f"[{perfil.nome}] Digest diário enviado: {len(vagas_pendentes)} vaga(s).")
    else:
        # Não marca metadado nem limpa a fila — tenta de novo no próximo
        # ciclo (ver enviar_digest/marcar_digest_enviado: preferir duplicar
        # a perder vaga).
        logger.warning(
            f"[{perfil.nome}] Falha ao enviar digest diário ({len(vagas_pendentes)} vaga(s) "
            "pendentes) - tenta de novo no próximo ciclo."
        )


def _deve_alertar_saude(com_problema: int, total: int) -> bool:
    """A maioria ESTRITA das fontes falhou neste ciclo?

    MEDIDO: a regra era ">= metade", o que com 2 fontes significa que UMA
    sozinha ja dispara o alerta. Isso passou a importar quando o Indeed foi
    desligado e o perfil Internacional ficou com 2 fontes: o WeWorkRemotely e
    pequeno (5 vagas no ciclo medido, vazio em 9 dos 10 termos), entao um dia
    mais fraco viraria "JobRadar com problema" sem haver problema nenhum.

    Alerta que dispara sem motivo e pior que alerta que nao existe: depois de
    duas ou tres vezes, ele deixa de ser lido -- e ai nao serve mais nem
    quando o problema e real.

    Maioria ESTRITA (">" em vez de ">=") resolve sem enfraquecer o resto:

        2 fontes -> exige 2 (antes 1)  <- o caso que motivou a mudanca
        3 fontes -> exige 2 (igual)
        7 fontes -> exige 4 (igual)
        8 fontes -> exige 5 (antes 4)

    Ou seja: com 2 fontes o alerta passa a significar "as duas cairam", que e
    o que "com problema" deveria querer dizer.
    """
    if total <= 0:
        return False
    return com_problema > total / 2

def ciclo_de_busca(perfil: Perfil):
    auditoria = AuditoriaCiclo(perfil.chave)
    cache_descricoes: dict[str, dict] = {}
    total_novas = 0
    total_brutas = 0
    total_filtradas = 0
    scrapers_com_problema = []
    descartes_escopo_ciclo: Counter = Counter()
    # Diagnóstico (ver Job.rejeitada_so_pelo_cargo): vaga numa das cidades
    # aceitas que só não passou porque o título não bate keyword nenhuma.
    # Existe pra medir se vale abrir a descrição dessas vagas — hoje o filtro
    # lê só o título, e vaga de BI com nome comercial escapa.
    titulo_barrou_em_cidade: list[str] = []

    termos_do_ciclo = _proximo_bloco_termos(perfil)
    logger.info(
        f"[{perfil.nome}] Bloco de termos deste ciclo: {len(termos_do_ciclo)}/"
        f"{len(perfil.termos_busca)} — {', '.join(termos_do_ciclo)}"
    )
    scrapers = _construir_scrapers(perfil, termos_do_ciclo)

    # A parte lenta (abrir navegador, navegar, esperar seletor) roda em
    # paralelo aqui. Tudo que segue (filtrar, checar dedup, notificar,
    # salvar) continua rodando só na thread principal, um scraper de cada
    # vez, conforme a future dele termina — nunca duas threads escrevendo
    # no SQLite ou chamando o Telegram ao mesmo tempo. Cada scraper já é
    # auto-contido (cria e fecha seu(s) próprio(s) browser(s) Playwright
    # dentro de buscar_vagas()), então dá pra rodar vários ao mesmo tempo em
    # threads sem risco — nenhum compartilha Browser/Page com outro.
    with ThreadPoolExecutor(max_workers=perfil.max_scrapers_concorrentes) as executor:
        futures = {executor.submit(scraper.buscar_vagas): scraper for scraper in scrapers}

        for future in as_completed(futures):
            scraper = futures[future]
            nome = scraper.__class__.__name__

            try:
                vagas = future.result()
            except Exception as e:
                logger.error(f"[{perfil.nome}] Erro no scraper {nome}: {e}")
                scrapers_com_problema.append(nome)
                continue

            # Cada scraper trata timeout por termo internamente (só loga e
            # segue pro próximo termo), então um site totalmente bloqueado
            # não lança exceção pra cá — só devolve lista vazia. Por isso
            # também contamos "0 vaga bruta nessa fonte" como problema, não
            # só exceção.
            if not vagas:
                logger.warning(f"[{perfil.nome}] {nome} não retornou nenhuma vaga bruta neste ciclo.")
                scrapers_com_problema.append(nome)
                continue

            _marcar_fonte_baixa_frequencia_concluida(perfil, scraper)
            auditoria.contar("coletadas", len(vagas))
            for job_coletado in vagas:
                auditoria.registrar(job_coletado, "coletada")
            total_brutas += len(vagas)
            # No perfil Brasil, só notificamos vagas com data verificável dos
            # últimos 5 dias. Fontes sem data ou com formato ambíguo não podem
            # ser tratadas como recentes por suposição. O perfil internacional
            # preserva sua regra de recência atual.
            vagas_para_avaliar = vagas
            if perfil.chave == "brasil":
                vagas_para_avaliar, descartadas_recencia = filtrar_publicadas_recentemente(
                    vagas, dias_maximos=DIAS_MAXIMOS_PUBLICACAO
                )
                if descartadas_recencia:
                    auditoria.contar("descartadas_data", descartadas_recencia)
                    ids_recentes = {v.id for v in vagas_para_avaliar}
                    for job_descartado in vagas:
                        if job_descartado.id not in ids_recentes:
                            auditoria.registrar(job_descartado, "rejeitada_data", "data ausente, ambígua, futura ou fora da janela de 5 dias")
                    logger.info(
                        f"[{perfil.nome}] {descartadas_recencia} vaga(s) descartada(s) "
                        "por data ausente, ambígua, futura ou anterior aos últimos 5 dias."
                    )
            # O perfil Brasil é estritamente remoto: cidade de contratação
            # por si só não torna uma vaga elegível para este radar.
            if perfil.chave == "brasil":
                remotas_confirmadas = []
                for vaga_modalidade in vagas_para_avaliar:
                    if (vaga_modalidade.modalidade or "").strip().casefold() == "remoto":
                        remotas_confirmadas.append(vaga_modalidade)
                    else:
                        auditoria.contar("descartadas_modalidade_local")
                        auditoria.registrar(
                            vaga_modalidade, "rejeitada_modalidade",
                            "modalidade não confirmada como 100% remota"
                        )
                vagas_para_avaliar = remotas_confirmadas

            vagas_filtradas, descartes = filtrar_vagas(vagas_para_avaliar, perfil.regras)
            auditoria.contar(f"brutas_fonte_{nome}", len(vagas))
            auditoria.contar("avaliadas_filtro", len(vagas_para_avaliar))
            ids_aceitas_filtro = {v.id for v in vagas_filtradas}
            for job_candidato in vagas_para_avaliar:
                if job_candidato.id not in ids_aceitas_filtro:
                    avaliacao = job_candidato._avaliar(perfil.regras)
                    if not avaliacao.bate_cidade:
                        motivo_rejeicao = "modalidade_ou_localizacao"
                        auditoria.contar("descartadas_modalidade_local")
                    else:
                        motivo_rejeicao = "cargo_ou_taxonomia"
                        auditoria.contar("descartadas_cargo")
                    auditoria.registrar(job_candidato, "rejeitada_filtro", motivo_rejeicao)
            descartes_escopo_ciclo.update(descartes)

            ids_aprovadas = {v.id for v in vagas_filtradas}
            candidatas_descricao = [
                v for v in vagas_para_avaliar
                if v.id not in ids_aprovadas and v.rejeitada_so_pelo_cargo(perfil.regras)
            ]
            titulo_barrou_em_cidade.extend(
                f"{v.titulo} — {v.empresa} ({v.local})"
                for v in candidatas_descricao
            )

            # Segunda chance baseada no conteúdo: só abre a página de anúncios
            # remotos no escopo elegível que falharam exclusivamente pelo título.
            # Exige descrição completa, score suficiente e evidência textual da
            # família profissional; isso evita aceitar vagas por palavras vagas.
            vagas_recuperadas_descricao = []
            for vaga_por_descricao in candidatas_descricao:
                _enriquecer_e_pontuar(vaga_por_descricao, cache_descricoes)
                auditoria.contar("avaliadas_compatibilidade")
                if vaga_por_descricao.status_extracao == "completa":
                    auditoria.contar("descricao_completa")
                else:
                    auditoria.contar("descricao_insuficiente")
                auditoria.registrar(
                    vaga_por_descricao, "avaliada_compatibilidade_titulo_rejeitado",
                    vaga_por_descricao.compatibilidade_justificativa
                )
                familia_comprovada = any(
                    str(criterio).startswith("Família de cargo alinhada")
                    for criterio in (vaga_por_descricao.compatibilidade_criterios or [])
                )
                if (
                    vaga_por_descricao.status_extracao == "completa"
                    and familia_comprovada
                    and vaga_por_descricao.compatibilidade_score >= LIMIAR_COMPATIBILIDADE_MINIMA
                ):
                    vaga_por_descricao.relevancia = max(
                        vaga_por_descricao.pontuar_relevancia(perfil.regras), 7
                    )
                    vaga_por_descricao.motivo = "Descrição alinhada às áreas-alvo"
                    vagas_filtradas.append(vaga_por_descricao)
                    auditoria.contar("recuperadas_por_descricao")
                    auditoria.registrar(
                        vaga_por_descricao, "aprovada_por_descricao",
                        vaga_por_descricao.compatibilidade_justificativa
                    )
                else:
                    auditoria.contar("rejeitadas_por_descricao")
                    auditoria.registrar(
                        vaga_por_descricao, "rejeitada_por_descricao",
                        "descrição insuficiente, sem família alinhada ou score abaixo do limiar"
                    )

            # A descrição é enriquecida para vagas que passaram no título e para
            # candidatas recuperadas pelo conteúdo, limitando requisições extras.
            # Sem descrição suficiente, o score é limitado e a incerteza fica explícita.
            ids_recuperadas_por_descricao = {v.id for v in vagas_recuperadas_descricao}
            for vaga_avaliada in vagas_filtradas:
                if vaga_avaliada.id not in ids_recuperadas_por_descricao:
                    _enriquecer_e_pontuar(vaga_avaliada, cache_descricoes)
                    auditoria.contar("avaliadas_compatibilidade")
                    if vaga_avaliada.status_extracao == "completa":
                        auditoria.contar("descricao_completa")
                    else:
                        auditoria.contar("descricao_insuficiente")
                    auditoria.registrar(
                        vaga_avaliada, "avaliada_compatibilidade",
                        vaga_avaliada.compatibilidade_justificativa
                    )
                logger.info(
                    f"[{perfil.nome}] Compatibilidade {vaga_avaliada.compatibilidade_score}/100 "
                    f"({vaga_avaliada.status_extracao}) — {vaga_avaliada.titulo} | "
                    f"lacunas: {'; '.join(vaga_avaliada.compatibilidade_lacunas or []) or 'nenhuma'}"
                )
            rejeitadas_score = [
                v for v in vagas_filtradas
                if v.compatibilidade_score < LIMIAR_COMPATIBILIDADE_MINIMA
            ]
            auditoria.contar("reprovadas_score", len(rejeitadas_score))
            for vaga_reprovada in rejeitadas_score:
                auditoria.registrar(
                    vaga_reprovada, "rejeitada_score",
                    f"{vaga_reprovada.compatibilidade_score}/100 < {LIMIAR_COMPATIBILIDADE_MINIMA}/100"
                )
            vagas_filtradas = [
                v for v in vagas_filtradas
                if v.compatibilidade_score >= LIMIAR_COMPATIBILIDADE_MINIMA
            ]
            auditoria.contar("aprovadas_score", len(vagas_filtradas))

            # Eixo secundário (Ibéria, quando ligado): mesma regra de cargo,
            # cidade diferente — sem duplicar o que já bateu na regra
            # primária.
            vagas_secundarias = []
            if perfil.eixo_secundario_ativo and perfil.regras_eixo_secundario is not None:
                ids_filtradas = {v.id for v in vagas_filtradas}
                candidatas, descartes_secundario = filtrar_vagas(vagas_para_avaliar, perfil.regras_eixo_secundario)
                descartes_escopo_ciclo.update(descartes_secundario)
                candidatas = [v for v in candidatas if v.id not in ids_filtradas]
                for vaga_secundaria in candidatas:
                    _enriquecer_e_pontuar(vaga_secundaria, cache_descricoes)
                    auditoria.contar("avaliadas_compatibilidade")
                    auditoria.registrar(vaga_secundaria, "avaliada_compatibilidade_secundaria", vaga_secundaria.compatibilidade_justificativa)
                vagas_secundarias = [
                    v for v in candidatas
                    if v.compatibilidade_score >= LIMIAR_COMPATIBILIDADE_MINIMA
                ]
                auditoria.contar("aprovadas_score_secundaria", len(vagas_secundarias))
                auditoria.contar("reprovadas_score_secundaria", len(candidatas) - len(vagas_secundarias))

            total_filtradas += len(vagas_filtradas) + len(vagas_secundarias)

            novas_da_fonte = 0
            for vaga in vagas_filtradas:
                auditoria.contar("elegiveis_notificacao")
                if ja_vista(vaga):
                    auditoria.contar("descartadas_duplicidade")
                    auditoria.registrar(vaga, "rejeitada_duplicidade", "já registrada no banco")
                    continue

                # Item 08: só notifica na hora quando a relevância passa do
                # limiar (ver LIMIAR_DIGEST_IMEDIATO em config.py) — abaixo
                # disso, vai pra fila do digest diário sem mensagem
                # individual (ver _enviar_digest_diario). Fila é salvar com
                # digest_pendente=True: não tem "notificação que pode
                # falhar" nesse caminho (a mensagem só sai no digest, depois),
                # então salvar direto não arrisca perder a vaga do jeito que
                # salvar ANTES de notificar arriscava no caminho imediato.
                #
                # MEDIDO: vaga com Job.publicacao_antiga (publicado_em "há X
                # meses/anos" — ver job.py) nunca vai pra notificação
                # imediata, mesmo com relevância alta — score mede "bate com
                # o que você procura", não "é recente". Site com pouco
                # volume pra um termo deixa vaga de meses atrás na página
                # visível (confirmado ao vivo: Sólides ordena por data, mas
                # sem volume novo suficiente a antiga não sai da 1ª página).
                # Não é descartada (mesma vaga ainda pode estar aberta) — só
                # sai do caminho "🚨 urgente" e vai pro digest em lote.
                if vaga.relevancia >= LIMIAR_DIGEST_IMEDIATO and not vaga.publicacao_antiga:
                    # Notifica ANTES de salvar. Se salvasse primeiro e o
                    # Telegram falhasse, a vaga ficava marcada como "vista"
                    # pra sempre — o próximo ciclo pulava ela em ja_vista()
                    # e a vaga se perdia sem nunca ter sido notificada de
                    # verdade.
                    if not notificar_vaga(vaga):
                        auditoria.contar("notificacoes_falhas")
                        auditoria.registrar(vaga, "falha_notificacao", "Telegram retornou falha; vaga não marcada como vista")
                        logger.warning(
                            f"[{perfil.nome}] Falha ao notificar '{vaga.titulo}' - não marcada "
                            "como vista, tenta de novo no próximo ciclo."
                        )
                        continue
                    auditoria.contar("notificacoes_enviadas")
                    auditoria.registrar(vaga, "notificacao_enviada", "Telegram confirmou envio")
                    salvar_vaga(vaga, perfil_chave=perfil.chave)
                    logger.info(f"[{perfil.nome}] Nova vaga: {vaga.titulo} - {vaga.empresa}")
                else:
                    motivo_digest = "vaga antiga" if vaga.publicacao_antiga else f"relevância {vaga.relevancia}/10"
                    auditoria.contar("vagas_enfileiradas_digest")
                    auditoria.registrar(vaga, "enfileirada_digest", motivo_digest)
                    salvar_vaga(vaga, perfil_chave=perfil.chave, digest_pendente=True)
                    logger.info(
                        f"[{perfil.nome}] Nova vaga (digest, {motivo_digest}): "
                        f"{vaga.titulo} - {vaga.empresa}"
                    )

                total_novas += 1
                novas_da_fonte += 1

            for vaga in vagas_secundarias:
                auditoria.contar("elegiveis_notificacao")
                if ja_vista(vaga):
                    auditoria.contar("descartadas_duplicidade")
                    auditoria.registrar(vaga, "rejeitada_duplicidade", "já registrada no banco")
                    continue

                # Mesma regra de vaga antiga do loop acima.
                if vaga.relevancia >= LIMIAR_DIGEST_IMEDIATO and not vaga.publicacao_antiga:
                    if not notificar_vaga_exploratoria(vaga):
                        auditoria.contar("notificacoes_falhas")
                        auditoria.registrar(vaga, "falha_notificacao_exploratoria", "Telegram retornou falha; vaga não marcada como vista")
                        logger.warning(
                            f"[{perfil.nome}] Falha ao notificar '{vaga.titulo}' (exploratória) - "
                            "não marcada como vista, tenta de novo no próximo ciclo."
                        )
                        continue
                    auditoria.contar("notificacoes_enviadas")
                    auditoria.registrar(vaga, "notificacao_enviada_exploratoria", "Telegram confirmou envio")
                    salvar_vaga(vaga, perfil_chave=perfil.chave)
                    logger.info(
                        f"[{perfil.nome}] Nova vaga exploratória ({perfil.eixo_secundario_rotulo}): "
                        f"{vaga.titulo} - {vaga.empresa}"
                    )
                else:
                    motivo_digest = "vaga antiga" if vaga.publicacao_antiga else f"relevância {vaga.relevancia}/10"
                    auditoria.contar("vagas_enfileiradas_digest")
                    auditoria.registrar(vaga, "enfileirada_digest_exploratoria", motivo_digest)
                    salvar_vaga(vaga, perfil_chave=perfil.chave, digest_pendente=True, exploratoria=True)
                    logger.info(
                        f"[{perfil.nome}] Nova vaga exploratória (digest, {motivo_digest}): "
                        f"{vaga.titulo} - {vaga.empresa}"
                    )

                total_novas += 1
                novas_da_fonte += 1

            # Funil por fonte: sem isso só dava pra ver bruta (por fonte) e
            # nova (só o total do ciclo) — o meio (quanto o filtro de
            # cargo/cidade descarta, fonte por fonte) ficava invisível.
            logger.info(
                f"[{perfil.nome}][{nome}] Funil: {len(vagas)} brutas → "
                f"{len(vagas_filtradas) + len(vagas_secundarias)} filtradas → {novas_da_fonte} novas"
            )

    logger.info(
        f"[{perfil.nome}] Ciclo concluído: {total_brutas} brutas → {total_filtradas} filtradas → "
        f"{total_novas} nova(s)."
    )

    # MEDIDO: descarte por escopo era invisível no log — o funil mostra
    # bruta → filtrada → nova, mas nunca QUAL escopo derrubou vaga nem
    # QUANTAS. Um escopo mal reconhecido (texto cru tipo "lagos nigeria",
    # não mapeado em _MERCADOS_REMOTO) barra do jeito certo, mas some sem
    # rastro — foi assim que um bug real (escopo virando allowlist) passou
    # despercebido até virar relato explícito. Loga só quando há descarte
    # (a maioria dos ciclos não tem nenhum), ordenado do que mais derrubou
    # vaga pro que menos derrubou.
    if descartes_escopo_ciclo:
        detalhe = "; ".join(
            f"{escopo} ({n})" for escopo, n in descartes_escopo_ciclo.most_common()
        )
        logger.info(f"[{perfil.nome}] Descarte por escopo: {detalhe}")

    # MEDIDO: uma vaga real ("Analista Comercial JR", Lactalis, Recife) não
    # foi notificada — local aceito, título sem nenhuma das 36 keywords, mas a
    # descrição com 5 dos 11 qualificadores de dados. Este contador mede
    # quantas vagas por ciclo caem nesse caso, pra decidir por número (e não
    # por palpite) se vale abrir a descrição delas. Mostra até 10 exemplos —
    # o suficiente pra julgar se são vagas de verdade ou ruído.
    if titulo_barrou_em_cidade:
        logger.info(
            f"[{perfil.nome}] Em cidade aceita, barradas só pelo título: "
            f"{len(titulo_barrou_em_cidade)}"
        )
        for exemplo in titulo_barrou_em_cidade[:10]:
            logger.info(f"[{perfil.nome}]   · {exemplo}")

    # Alerta de saúde: se a maioria das fontes falhou/voltou vazia, avisa no
    # Telegram. Sem isso, um bloqueio geral ou mudança de layout passaria
    # despercebido — o workflow do GitHub Actions continuaria "verde" mesmo
    # com tudo quebrado.
    if _deve_alertar_saude(len(scrapers_com_problema), len(scrapers)):
        enviar_mensagem(
            f"⚠️ <b>JobRadar {perfil.nome} com problema</b>\n\n"
            f"{len(scrapers_com_problema)}/{len(scrapers)} fontes falharam ou voltaram "
            f"vazias neste ciclo: {', '.join(scrapers_com_problema)}.\n\n"
            "Vale checar o log do GitHub Actions."
        )

    auditoria.contar("novas_registradas", total_novas)
    _enviar_heartbeat_diario(
        perfil, total_novas, scrapers_com_problema, len(scrapers), auditoria=auditoria
    )
    _enviar_digest_diario(perfil, auditoria=auditoria)
    auditoria.finalizar()
    logger.info(
        f"[{perfil.nome}] Auditoria do funil: coletadas={auditoria.contadores.get('coletadas', 0)}, "
        f"fontes_brutas={sum(v for k, v in auditoria.contadores.items() if k.startswith('brutas_fonte_'))}, "
        f"descartadas_data={auditoria.contadores.get('descartadas_data', 0)}, "
        f"descartadas_modalidade_local={auditoria.contadores.get('descartadas_modalidade_local', 0)}, "
        f"descartadas_cargo={auditoria.contadores.get('descartadas_cargo', 0)}, "
        f"descartadas_duplicidade={auditoria.contadores.get('descartadas_duplicidade', 0)}, "
        f"descricao_completa={auditoria.contadores.get('descricao_completa', 0)}, "
        f"descricao_insuficiente={auditoria.contadores.get('descricao_insuficiente', 0)}, "
        f"avaliadas={auditoria.contadores.get('avaliadas_compatibilidade', 0)}, "
        f"aprovadas_score={auditoria.contadores.get('aprovadas_score', 0)}, "
        f"reprovadas_score={auditoria.contadores.get('reprovadas_score', 0)}, "
        f"recuperadas_por_descricao={auditoria.contadores.get('recuperadas_por_descricao', 0)}, "
        f"enfileiradas_digest={auditoria.contadores.get('vagas_enfileiradas_digest', 0)}, "
        f"elegiveis_notificacao={auditoria.contadores.get('elegiveis_notificacao', 0)}, "
        f"notificacoes_enviadas={auditoria.contadores.get('notificacoes_enviadas', 0)}, "
        f"notificacoes_falhas={auditoria.contadores.get('notificacoes_falhas', 0)}, "
        f"vagas_digest_enviadas={auditoria.contadores.get('vagas_digest_enviadas', 0)}, "
        f"lotes_digest_falhos={auditoria.contadores.get('lotes_digest_falhos', 0)}, "
        f"mensagens_sistema_falhas={auditoria.contadores.get('mensagens_sistema_falhas', 0)}; "
        f"arquivo=data/audit/ciclos.jsonl"
    )


def _rodar_um_ciclo_de_cada(perfis: list[Perfil]):
    # Uma vez por execução, não por perfil: o offset do getUpdates (ver
    # processar_feedback_pendente) é global — feedback de vaga não tem
    # perfil, e rodar duas vezes na mesma execução só gastaria uma chamada
    # de API à toa (a segunda sempre veria "nada novo desde a última vez").
    processar_feedback_pendente()

    for perfil in perfis:
        print(f"\n{'=' * 50}")
        print(f"PERFIL: {perfil.nome.upper()}")
        print("=" * 50)

        print("\nPalavras monitoradas:")
        for palavra in perfil.palavras_monitoradas:
            print(f"• {palavra}")

        if perfil.paises_pesquisados:
            print("\nPaíses pesquisados:")
            for pais in perfil.paises_pesquisados:
                print(f"• {pais}")

        ciclo_de_busca(perfil)


def main():
    parser = argparse.ArgumentParser(description="JobRadar - monitor de vagas")
    parser.add_argument(
        "--perfil",
        required=True,
        nargs="+",
        choices=sorted(PERFIS.keys()),
        help=(
            "Qual(is) mercado(s) rodar nesta execução — 'brasil', 'internacional', "
            "ou os dois (--perfil brasil internacional)."
        ),
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Roda um único ciclo de busca (de cada perfil selecionado) e encerra "
             "(usado no GitHub Actions, que já dispara o script periodicamente via cron).",
    )
    args = parser.parse_args()

    perfis_selecionados = [PERFIS[chave] for chave in args.perfil]

    if not args.once:
        print(f"\nIntervalo de checagem: {INTERVALO_MINUTOS} min\n")

    # Chamado UMA VEZ só, antes de qualquer perfil rodar — não por perfil.
    # A checagem de "banco suspeito" (ver database.py) compara se o arquivo
    # já existia ANTES desta execução; se cada perfil chamasse iniciar_db()
    # separadamente na mesma execução, o segundo perfil veria o arquivo que
    # o primeiro acabou de criar/popular momentos atrás e podia disparar
    # falso positivo (arquivo "já existia" só porque o perfil anterior já
    # rodou nesta mesma execução, não porque é run antigo de verdade).
    try:
        iniciar_db()
    except BancoVazioSuspeito as e:
        logger.error(str(e))
        nomes = ", ".join(p.nome for p in perfis_selecionados)
        enviar_mensagem(f"🛑 <b>JobRadar abortado</b>\n\nPerfis desta execução: {nomes}\n\n{e}")
        sys.exit(1)

    if args.once:
        _rodar_um_ciclo_de_cada(perfis_selecionados)
        return

    while True:
        _rodar_um_ciclo_de_cada(perfis_selecionados)
        logger.info(f"Aguardando {INTERVALO_MINUTOS} minutos até a próxima checagem...")
        time.sleep(INTERVALO_MINUTOS * 60)


if __name__ == "__main__":
    main()
