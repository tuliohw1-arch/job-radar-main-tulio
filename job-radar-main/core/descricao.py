"""Extração defensiva de descrição de vagas, sem inventar campos ausentes.

Tenta primeiro dados estruturados/metadados e depois texto visível da página.
Uma descrição só é considerada suficiente quando há conteúdo real (>=180 chars).
"""
from __future__ import annotations

from html.parser import HTMLParser
import json
import re
from typing import Any

import requests


TIMEOUT_DESCRICAO = 12
MIN_CHARS_DESCRICAO = 180
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}


class _TextoHTML(HTMLParser):
    """Extrai texto visível e ignora scripts, estilos e navegação técnica."""

    IGNORAR = {"script", "style", "noscript", "svg", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self._ignorar = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.IGNORAR:
            self._ignorar += 1
        elif tag.lower() in {"p", "br", "li", "div", "section", "h1", "h2", "h3"}:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag.lower() in self.IGNORAR and self._ignorar:
            self._ignorar -= 1
        elif tag.lower() in {"p", "li", "div", "section", "h1", "h2", "h3"}:
            self.partes.append("\n")

    def handle_data(self, data):
        if not self._ignorar and data.strip():
            self.partes.append(data.strip())


def normalizar_texto(texto: str) -> str:
    texto = (texto or "").replace("\xa0", " ")
    if re.search(r"<[a-zA-Z][^>]*>", texto):
        parser = _TextoHTML()
        parser.feed(texto)
        texto = "\n".join(parser.partes)
    texto = re.sub(r"[ \t\f\v]+", " ", texto)
    texto = re.sub(r" *\n *", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def _descricoes_jsonld(valor: Any) -> list[str]:
    saida: list[str] = []
    if isinstance(valor, dict):
        tipo = valor.get("@type", "")
        tipos = tipo if isinstance(tipo, list) else [tipo]
        if any(str(t).lower() in {"jobposting", "job"} for t in tipos):
            desc = valor.get("description")
            if isinstance(desc, str) and desc.strip():
                parser = _TextoHTML()
                parser.feed(desc)
                saida.append(normalizar_texto(" ".join(parser.partes)))
        for v in valor.values():
            saida.extend(_descricoes_jsonld(v))
    elif isinstance(valor, list):
        for item in valor:
            saida.extend(_descricoes_jsonld(item))
    return saida


def _extrair_meta_e_jsonld(html: str) -> tuple[str, str]:
    # Parser mínimo para metadados, sem depender de BeautifulSoup.
    class MetaParser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.meta: dict[str, str] = {}
            self.jsonld: list[str] = []
            self._jsonld = False
            self._script = ""

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag.lower() == "meta":
                chave = (attrs.get("property") or attrs.get("name") or "").lower()
                conteudo = attrs.get("content", "")
                if chave and conteudo:
                    self.meta[chave] = conteudo
            elif tag.lower() == "script" and "ld+json" in (attrs.get("type") or "").lower():
                self._jsonld = True
                self._script = ""

        def handle_data(self, data):
            if self._jsonld:
                self._script += data

        def handle_endtag(self, tag):
            if tag.lower() == "script" and self._jsonld:
                self.jsonld.append(self._script)
                self._jsonld = False
                self._script = ""

    parser = MetaParser()
    parser.feed(html)
    for bruto in parser.jsonld:
        try:
            for descricao in _descricoes_jsonld(json.loads(bruto)):
                if descricao.strip():
                    return descricao, "jsonld"
        except (ValueError, TypeError):
            continue

    for chave in ("og:description", "description", "twitter:description"):
        valor = parser.meta.get(chave, "")
        if normalizar_texto(valor):
            return normalizar_texto(valor), "meta"
    return "", ""


def analisar_secoes(descricao: str) -> dict[str, list[str]]:
    """Separa seções por cabeçalhos; preserva o texto integral em descricao."""
    secoes = {
        "responsabilidades": [],
        "requisitos_obrigatorios": [],
        "requisitos_desejaveis": [],
    }
    atual = None
    for linha in normalizar_texto(descricao).splitlines():
        limpa = linha.strip(" •-*\t:")
        if not limpa:
            continue
        normal = limpa.casefold()
        if re.search(r"responsabil|atividades|o que você fará|what you.ll do|your role", normal):
            atual = "responsabilidades"
            continue
        if re.search(r"requisitos obrigatórios|requisitos necessarios|must have|required qualifications|requirements", normal):
            atual = "requisitos_obrigatorios"
            continue
        if re.search(r"desej|diferencial|nice to have|preferred qualifications|bonus points", normal):
            atual = "requisitos_desejaveis"
            continue
        if atual:
            secoes[atual].append(limpa)
    return secoes


def extrair_descricao(url: str, session=None, renderizar_dinamico: bool = True) -> dict[str, Any]:
    """Retorna estado e metadados da extração. Erros não incluem URL/token em logs."""
    resultado = {
        "descricao": "",
        "status_extracao": "indisponivel",
        "origem_descricao": "",
        "erro_extracao": "",
        "url_final": url or "",
    }
    if not url:
        resultado["erro_extracao"] = "url_ausente"
        return resultado
    cliente = session or requests
    try:
        resposta = cliente.get(url, headers=HEADERS, timeout=TIMEOUT)
        resultado["url_final"] = getattr(resposta, "url", url) or url
        resposta.raise_for_status()
        content_type = (getattr(resposta, "headers", {}) or {}).get("Content-Type", "")
        if "html" not in content_type.lower() and content_type:
            resultado["erro_extracao"] = "content_type_nao_html"
            return resultado
        html = getattr(resposta, "text", "") or ""
        descricao, origem = _extrair_meta_e_jsonld(html)
        if not descricao:
            parser = _TextoHTML()
            parser.feed(html)
            texto = normalizar_texto("\n".join(parser.partes))
            # Retira boilerplate muito comum sem presumir que ele seja descrição.
            linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
            texto = normalizar_texto("\n".join(linhas))
            # Só aceita corpo longo quando há sinais de conteúdo de vaga.
            sinais = re.search(
                r"responsabil|requisit|qualifica|experi[eê]ncia|benef[ií]cios|"
                r"responsibilit|qualification|experience|about the role|"
                r"descri[cç][aã]o da vaga",
                texto,
                re.IGNORECASE,
            )
            if sinais and len(texto) >= 40:
                descricao, origem = texto, "html_visivel"
        if descricao:
            resultado["descricao"] = normalizar_texto(descricao)
            resultado["origem_descricao"] = origem
            resultado["status_extracao"] = (
                "completa" if len(resultado["descricao"]) >= MIN_CHARS_DESCRICAO else "incompleta"
            )
        else:
            resultado["erro_extracao"] = "descricao_nao_encontrada_ou_curta"
    except requests.HTTPError as erro:
        status = getattr(getattr(erro, "response", None), "status_code", None)
        resultado["erro_extracao"] = f"http_{status}" if status else "http_error"
    except requests.Timeout:
        resultado["erro_extracao"] = "timeout"
    except requests.RequestException as erro:
        resultado["erro_extracao"] = type(erro).__name__
    except (ValueError, TypeError):
        resultado["erro_extracao"] = "html_ou_dados_invalidos"
    except Exception as erro:  # proteção contra HTMLParser/estrutura inesperada
        resultado["erro_extracao"] = f"erro_{type(erro).__name__}"

    if not resultado["descricao"] and renderizar_dinamico:
        # Fallback para boards que preenchem o corpo via JavaScript. É lazy:
        # só abre Chromium quando a resposta HTTP não forneceu descrição útil.
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=10000)
                    try:
                        texto_renderizado = page.locator("body").inner_text(timeout=5000)
                    except Exception:
                        texto_renderizado = ""
                    texto_renderizado = normalizar_texto(texto_renderizado)
                    tem_sinais_vaga = re.search(
                        r"responsabil|requisit|qualifica|experi[eê]ncia|benef[ií]cios|"
                        r"responsibilit|qualification|experience|about the role|"
                        r"descri[cç][aã]o da vaga",
                        texto_renderizado,
                        re.IGNORECASE,
                    )
                    if tem_sinais_vaga and len(texto_renderizado) >= 40:
                        resultado["descricao"] = texto_renderizado
                        resultado["origem_descricao"] = "playwright_visivel"
                        resultado["url_final"] = page.url or resultado["url_final"]
                        resultado["status_extracao"] = (
                            "completa" if len(texto_renderizado) >= MIN_CHARS_DESCRICAO else "incompleta"
                        )
                        resultado["erro_extracao"] = ""
                finally:
                    browser.close()
        except Exception as erro:
            # Nunca registrar mensagem da exceção: pode incluir URL com query/token.
            if not resultado["descricao"]:
                resultado["erro_extracao"] = f"renderizacao_{type(erro).__name__}"

    if resultado["descricao"]:
        resultado.update(analisar_secoes(resultado["descricao"]))
    else:
        resultado.update({
            "responsabilidades": [],
            "requisitos_obrigatorios": [],
            "requisitos_desejaveis": [],
        })
    return resultado
