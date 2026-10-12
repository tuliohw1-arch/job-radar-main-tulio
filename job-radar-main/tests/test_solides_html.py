import json

from scrapers.solides import extrair_vagas_html, url_busca_publica


def _html_com_payload(payload: str) -> str:
    return "<script>self.__next_f.push([1, " + json.dumps(payload) + "])</script>"


def test_extrai_vaga_do_payload_flight_nextjs():
    vaga = {
        "id": 123,
        "title": "Analista de CRM",
        "companyName": "Empresa Teste",
        "redirectLink": "https://empresa.solides.jobs/vacancies/123",
        "jobType": "remoto",
        "homeOffice": True,
        "createdAt": "2026-10-09",
        "city": {"name": "Brasil"},
        "state": {"code": "BR"},
    }
    html = _html_com_payload('1:{"data":[' + json.dumps(vaga, ensure_ascii=False) + "]}")

    vagas = extrair_vagas_html(html)

    assert len(vagas) == 1
    assert vagas[0]["id"] == 123
    assert vagas[0]["title"] == "Analista de CRM"
    assert vagas[0]["jobType"] == "remoto"


def test_ignora_payload_sem_vagas():
    assert extrair_vagas_html(_html_com_payload('1:{"data":[]}')) == []


def test_descarta_objeto_sem_link_de_candidatura():
    vaga = {"id": 1, "title": "Analista CRM", "jobType": "remoto"}
    html = _html_com_payload('1:' + json.dumps(vaga))
    assert extrair_vagas_html(html) == []


def test_slug_da_busca_publica():
    assert url_busca_publica("Analista de CRM") == "https://vagas.solides.com.br/vagas/analista-de-crm"
    assert url_busca_publica("Customer Success / CX") == "https://vagas.solides.com.br/vagas/customer-success-cx"
