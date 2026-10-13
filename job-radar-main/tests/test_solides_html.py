import json
from pathlib import Path

from scrapers.solides import extrair_vagas_html, montar_job, url_busca_publica


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


def test_extrai_vagas_do_html_real_da_solides():
    fixture = Path(__file__).parent / "fixtures" / "solides_busca_real.html"
    vagas = extrair_vagas_html(fixture.read_text(encoding="utf-8"))

    # A captura pública fornecida contém nove registros reconhecíveis;
    # a modalidade é filtrada pela lógica existente depois de montar_job.
    assert len(vagas) == 9
    assert all(vaga.get("redirectLink") for vaga in vagas)
    assert all(vaga.get("title") for vaga in vagas)


def test_deduplica_vagas_com_mesmo_id():
    vaga = {
        "id": 123,
        "title": "Analista de CRM",
        "redirectLink": "https://empresa.solides.jobs/vacancies/123",
        "jobType": "remoto",
    }
    item = json.dumps(vaga, ensure_ascii=False)
    html = _html_com_payload('1:{"data":[' + item + "," + item + "]}")

    vagas = extrair_vagas_html(html)

    assert len(vagas) == 1
    assert vagas[0]["id"] == 123


def test_fallback_html_quando_api_retorna_403(monkeypatch):
    import scrapers.solides as solides

    vaga = {
        "id": 321,
        "title": "Analista de CRM",
        "companyName": "Empresa Teste",
        "redirectLink": "https://empresa.solides.jobs/vacancies/321",
        "jobType": "remoto",
        "homeOffice": True,
        "createdAt": "2026-10-09",
        "city": {"name": "Brasil"},
        "state": {"code": "BR"},
    }
    html = _html_com_payload('1:{"data":[' + json.dumps(vaga) + "]}")

    class Resposta:
        def __init__(self, status_code, text="", url="https://example.test"):
            self.status_code = status_code
            self.text = text
            self.url = url

    class SessaoFalsa:
        def __init__(self):
            self.respostas = [
                Resposta(403, "bloqueado", solides.URL_API),
                Resposta(200, html, "https://vagas.solides.com.br/vagas/analista-de-crm"),
            ]

        def get(self, *args, **kwargs):
            return self.respostas.pop(0)

    monkeypatch.setattr(solides.requests, "Session", SessaoFalsa)
    scraper = solides.SolidesScraper(["Analista de CRM"])
    scraper._sessao_inicializada = True

    vagas = scraper._buscar_termo("Analista de CRM")

    assert len(vagas) == 1
    assert vagas[0].titulo == "Analista de CRM"
    assert vagas[0].site == "Solides"



def test_montar_job_descarta_link_com_dominio_incompleto():
    vaga = {
        "id": 987,
        "title": "Analista de CRM",
        "companyName": "Empresa Teste",
        "redirectLink": "https://empresa./vacancies/987?origem=portal",
        "jobType": "remoto",
        "homeOffice": True,
        "createdAt": "2026-10-09",
    }

    assert montar_job(vaga) is None


def test_montar_job_aceita_link_https_valido():
    vaga = {
        "id": 988,
        "title": "Analista de CRM",
        "companyName": "Empresa Teste",
        "redirectLink": "https://empresa.com.br/vacancies/988",
        "jobType": "remoto",
        "homeOffice": True,
        "createdAt": "2026-10-09",
    }

    job = montar_job(vaga)

    assert job is not None
    assert job.link == "https://empresa.com.br/vacancies/988"
