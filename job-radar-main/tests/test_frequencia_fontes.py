"""Regressões para não pular fontes após falhas de coleta."""

import main
from core.perfis import PERFIL_BR, FREQUENCIA_BAIXA


def test_fontes_baixa_frequencia_ficam_independentes(monkeypatch):
    metadados = {}
    monkeypatch.setattr(main, "obter_metadado", lambda chave: metadados.get(chave))
    monkeypatch.setattr(
        main, "definir_metadado",
        lambda chave, valor: metadados.__setitem__(chave, valor),
    )

    primeira = main._construir_scrapers(PERFIL_BR, ["analista de crm"])
    baixas = {
        d.classe.__name__ for d in PERFIL_BR.definicao_scrapers
        if d.frequencia == FREQUENCIA_BAIXA
    }
    assert baixas
    assert baixas.issubset({s.__class__.__name__ for s in primeira})

    # Simula apenas uma fonte de baixa frequência concluindo com resultado.
    concluida = next(s for s in primeira if s.__class__.__name__ in baixas)
    main._marcar_fonte_baixa_frequencia_concluida(PERFIL_BR, concluida)

    segunda = main._construir_scrapers(PERFIL_BR, ["analista de crm"])
    nomes_segunda = {s.__class__.__name__ for s in segunda}
    assert concluida.__class__.__name__ not in nomes_segunda
    assert (baixas - {concluida.__class__.__name__}).issubset(nomes_segunda)


def test_fonte_com_resultado_vazio_nao_e_marcada_como_concluida(monkeypatch):
    metadados = {}
    monkeypatch.setattr(main, "obter_metadado", lambda chave: metadados.get(chave))
    monkeypatch.setattr(
        main, "definir_metadado",
        lambda chave, valor: metadados.__setitem__(chave, valor),
    )

    # A marcação só é chamada pelo pipeline depois de resultado não vazio.
    fonte = next(
        d.classe(termos_busca=["analista de crm"])
        for d in PERFIL_BR.definicao_scrapers
        if d.frequencia == FREQUENCIA_BAIXA
    )
    assert metadados == {}
    # Sem chamar _marcar..., a fonte permanece elegível para o próximo ciclo.
    novamente = main._construir_scrapers(PERFIL_BR, ["analista de crm"])
    assert fonte.__class__.__name__ in {s.__class__.__name__ for s in novamente}


def test_fonte_alta_frequencia_nao_grava_metadado_diario(monkeypatch):
    metadados = {}
    monkeypatch.setattr(main, "obter_metadado", lambda chave: metadados.get(chave))
    monkeypatch.setattr(
        main, "definir_metadado",
        lambda chave, valor: metadados.__setitem__(chave, valor),
    )

    scraper = next(
        d.classe(termos_busca=["analista de crm"])
        for d in PERFIL_BR.definicao_scrapers
        if d.frequencia != FREQUENCIA_BAIXA
    )
    main._marcar_fonte_baixa_frequencia_concluida(PERFIL_BR, scraper)
    assert metadados == {}
