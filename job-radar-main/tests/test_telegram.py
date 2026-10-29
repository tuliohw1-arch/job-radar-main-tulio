"""Testes da camada de notificação (notifier/telegram.py) que não dependem
de rede — parsing de callback_data e montagem de teclado inline, a parte
nova do fluxo de feedback 👍/👎 (ver processar_feedback_pendente).

Chamada de rede de verdade (sendMessage/getUpdates/answerCallbackQuery)
não é testável aqui: o sandbox não alcança api.telegram.org (proxy do
ambiente bloqueia, já diagnosticado nesta sessão). O que é função pura —
_parsear_callback_data e _teclado_feedback — é testado isolado, sem mock
nenhum.
"""

import pytest

from notifier.telegram import _parsear_callback_data, _teclado_feedback

_ID_EXEMPLO = "d41d8cd98f00b204e9800998ecf8427e"  # md5 de exemplo, 32 chars

CASOS_PARSE_CALLBACK = [
    ("positivo-formato-valido", f"fb|1|{_ID_EXEMPLO}", (_ID_EXEMPLO, "positivo")),
    ("negativo-formato-valido", f"fb|0|{_ID_EXEMPLO}", (_ID_EXEMPLO, "negativo")),
    # Botão de confirmação (substitui o teclado original depois de
    # registrado) não deve ser reprocessado como voto novo.
    ("botao-confirmacao-nao-e-voto", "fb|ok|-", None),
    # Direção fora de 1/0.
    ("direcao-invalida", f"fb|2|{_ID_EXEMPLO}", None),
    # Prefixo errado (callback_data de outro bot/projeto, teoricamente).
    ("prefixo-errado", f"xx|1|{_ID_EXEMPLO}", None),
    # Formato sem as 3 partes esperadas.
    ("sem_partes_suficientes", "fb|1", None),
    ("partes_demais", f"fb|1|{_ID_EXEMPLO}|extra", None),
    ("string_vazia", "", None),
]


@pytest.mark.parametrize(
    "nome,data,esperado",
    CASOS_PARSE_CALLBACK,
    ids=[c[0] for c in CASOS_PARSE_CALLBACK],
)
def test_parsear_callback_data(nome, data, esperado):
    assert _parsear_callback_data(data) == esperado


def test_teclado_feedback_estrutura():
    teclado = _teclado_feedback(_ID_EXEMPLO)
    linha = teclado["inline_keyboard"][0]
    assert len(linha) == 2
    assert linha[0]["callback_data"] == f"fb|1|{_ID_EXEMPLO}"
    assert linha[1]["callback_data"] == f"fb|0|{_ID_EXEMPLO}"


def test_teclado_feedback_callback_data_dentro_do_limite_do_telegram():
    # Limite real da API: callback_data <= 64 bytes.
    teclado = _teclado_feedback(_ID_EXEMPLO)
    for botao in teclado["inline_keyboard"][0]:
        assert len(botao["callback_data"].encode("utf-8")) <= 64


def test_ida_e_volta_teclado_para_parser():
    # O que _teclado_feedback gera, _parsear_callback_data tem que
    # entender de volta — as duas funções são as duas pontas do mesmo
    # contrato (callback_data), então uma mudar sem a outra é exatamente o
    # tipo de bug que só aparece em produção sem esse teste.
    teclado = _teclado_feedback(_ID_EXEMPLO)
    botao_positivo, botao_negativo = teclado["inline_keyboard"][0]

    assert _parsear_callback_data(botao_positivo["callback_data"]) == (_ID_EXEMPLO, "positivo")
    assert _parsear_callback_data(botao_negativo["callback_data"]) == (_ID_EXEMPLO, "negativo")



class _RespostaTelegramFake:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code = status
        self.reason = "simulated"
        self.headers = headers or {}
        self._body = body or {"ok": True}

    def raise_for_status(self):
        if self.status_code >= 400:
            erro = __import__("requests").HTTPError("simulated")
            erro.response = self
            raise erro

    def json(self):
        return self._body


def test_enviar_mensagem_telegram_simulado_com_sucesso(monkeypatch):
    import notifier.telegram as telegram

    chamadas = []
    monkeypatch.setattr(telegram, "TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(telegram, "TELEGRAM_CHAT_ID", "fake-chat")
    monkeypatch.setattr(telegram.requests, "post", lambda *a, **k: (chamadas.append((a, k)) or _RespostaTelegramFake()))
    assert telegram.enviar_mensagem("mensagem de teste simulada") is True
    assert len(chamadas) == 1
    assert "fake-token" in chamadas[0][0][0]  # token apenas na URL enviada, nunca no log


def test_enviar_mensagem_re tenta_apos_rate_limit_e_respeita_resposta(monkeypatch):
    import notifier.telegram as telegram

    respostas = iter([
        _RespostaTelegramFake(429, {"ok": False}, {"Retry-After": "1"}),
        _RespostaTelegramFake(200, {"ok": True}),
    ])
    chamadas = []
    monkeypatch.setattr(telegram, "TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(telegram, "TELEGRAM_CHAT_ID", "fake-chat")
    monkeypatch.setattr(telegram.requests, "post", lambda *a, **k: (chamadas.append(1) or next(respostas)))
    monkeypatch.setattr(telegram.time, "sleep", lambda *_: None)
    assert telegram.enviar_mensagem("mensagem de teste simulada") is True
    assert len(chamadas) == 2


def test_enviar_mensagem_timeout_nao_repete_envio_ambiguo(monkeypatch):
    import requests
    import notifier.telegram as telegram

    chamadas = []
    def falha(*args, **kwargs):
        chamadas.append(1)
        raise requests.Timeout()
    monkeypatch.setattr(telegram, "TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(telegram, "TELEGRAM_CHAT_ID", "fake-chat")
    monkeypatch.setattr(telegram.requests, "post", falha)
    assert telegram.enviar_mensagem("mensagem de teste simulada") is False
    assert len(chamadas) == 1


def test_notificacao_inclui_score_0_a_100_e_status_da_descricao(monkeypatch):
    import notifier.telegram as telegram
    from core.job import Job

    mensagens = []
    monkeypatch.setattr(telegram, "enviar_mensagem", lambda texto, reply_markup=None: (mensagens.append(texto) or True))
    job = Job(
        titulo="Analista de CRM Júnior",
        empresa="Empresa Teste",
        local="Brasil",
        link="https://example.com/job",
        site="Gupy",
        modalidade="Remoto",
        publicado_em="2026-10-28",
        relevancia=8,
        motivo="Cargo forte",
        compatibilidade_score=82,
        compatibilidade_justificativa="CRM e operações alinhados",
        status_extracao="completa",
    )
    assert telegram.notificar_vaga(job) is True
    assert "Compatibilidade:</b> 82/100" in mensagens[0]
    assert "Descrição:</b> completa" in mensagens[0]
