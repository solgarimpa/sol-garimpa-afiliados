#!/usr/bin/env python3
"""SOL GARIMPA: reunir cupons Shopee anunciados em fontes publicas.

Recolhe dados factuais (codigo, desconto, regras resumidas) e nao copia
links afiliados de terceiros. Fonte pode estar desatualizada ou bloqueada.
"""
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

SAIDA = Path("docs/central/shopee-cupons.json")
AGORA = datetime.now(timezone.utc).isoformat(timespec="seconds")
HEADERS = {
    "User-Agent": "SolGarimpaCouponMonitor/1.0 (+https://www.ofertaspravc.com.br)",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
}
FONTES = {
    "Pelando": "https://www.pelando.com.br/cupons-de-descontos/shopee",
    "Cuponomia": "https://www.cuponomia.com.br/desconto/shopee",
    "Meliuz": "https://www.meliuz.com.br/desconto/cupom-shopee",
}
WORKER = "https://sol-garimpa-cupons.contato-solgarimpa.workers.dev/?loja=Shopee"
SESSAO = requests.Session()
SESSAO.headers.update(HEADERS)


def limpar(s):
    return re.sub(r"\s+", " ", BeautifulSoup(str(s or ""), "html.parser").get_text(" ", strip=True)).strip()


def padrao(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.combining(c)).casefold()


def desconto(s):
    s = limpar(s)
    for exp in (r"(\d+(?:[.,]\d+)?)\s*%\s*OFF", r"(R\$\s*\d+(?:[.,]\d{1,2})?)\s*OFF"):
        m = re.search(exp, s, re.I)
        if m:
            return (m.group(1) + ("% OFF" if exp.startswith("(") and "%" in exp else " OFF")).replace("R$  ", "R$ ")
    if re.search(r"frete\s+gr[aá]tis", s, re.I):
        return "FRETE GRÁTIS"
    return "OFERTA"


def candidato_codigo(s):
    s = limpar(s)
    # Apenas tokens apresentados expressamente como codigos de cupom.
    for expr in (
        r"Ver\s+cupom\s+([A-Z0-9][A-Z0-9_-]{4,35})",
        r"Pegar\s+cupom\s+([A-Z0-9][A-Z0-9_-]{4,35})",
        r"([A-Z0-9][A-Z0-9_-]{4,35})\s+Copiar\b",
    ):
        m = re.search(expr, s, re.I)
        if m:
            cod = m.group(1).upper()
            if cod not in {"CUPOM", "COPIAR", "SHOPEE", "VERCUPOM"}:
                return cod
    return ""


def registro(titulo, codigo, fonte, descricao="", publicado=None, vencimento=None):
    titulo = limpar(titulo)[:170]
    if not titulo or not re.search(r"shopee|cupom|desconto|off|frete|oferta|voucher", padrao(titulo)):
        return None
    codigo = limpar(codigo).upper().replace(" ", "")[:55]
    if codigo and not re.fullmatch(r"[A-Z0-9_-]{4,55}", codigo):
        codigo = ""
    descricao = limpar(descricao)[:170]
    if "cashback" in padrao(descricao):
        # Cashback anunciado por terceiros nao e oferta de cashback Sol Garimpa.
        descricao = re.sub(r"\+?\s*at[eé]\s*\d+(?:[,.]\d+)?%\s*(?:de\s*)?cashback", "", descricao, flags=re.I).strip()
    return {
        "title": titulo,
        "couponCode": codigo,
        "discountText": desconto(titulo),
        "description": descricao or "Consulte pedido minimo, condicoes e produtos elegiveis na Shopee.",
        "sources": [fonte],
        "sourceUrl": FONTES.get(fonte, ""),
        "publishedAt": publicado,
        "expiresAt": vencimento,
        "observedAt": AGORA,
        "status": "listed",
    }


def buscar_html(fonte):
    r = SESSAO.get(FONTES[fonte], timeout=25)
    r.raise_for_status()
    if "text/html" not in r.headers.get("Content-Type", "text/html"):
        raise ValueError("Resposta nao e HTML")
    if len(r.text) < 800 or "Just a moment" in r.text or "Access Denied" in r.text:
        raise ValueError("Pagina indisponivel ou protecao antibot")
    return BeautifulSoup(r.text, "html.parser")


def conteiner_heading(h):
    """Tentar achar o cartao individual sem capturar a pagina inteira."""
    parent = h
    for _ in range(7):
        if parent.parent is None:
            break
        parent = parent.parent
        texto = parent.get_text(" ", strip=True)
        titulos = len(parent.find_all(["h2", "h3"], recursive=True))
        if 60 <= len(texto) <= 2500 and titulos <= 2:
            if re.search(r"Ver\s+cupom|Pegar\s+cupom|Copiar|[Uu]sados?\s+hoje|Verificado", texto):
                return parent
    return h.parent if h.parent else h


def coletar_site(fonte):
    soup = buscar_html(fonte)
    saida = []
    if fonte == "Cuponomia":
        # Cada cupom aparece em um <li> com titulo <h3>.
        for li in soup.select("li"):
            h = li.find("h3")
            if not h:
                continue
            titulo = h.get_text(" ", strip=True)
            bloco = li.get_text(" ", strip=True)
            if len(bloco) > 4000:
                continue
            # Remover propagandas, extensoes e cadastro de cashback.
            if re.search(r"extens[aã]o|cadastre-se|baixe o app", padrao(titulo)):
                continue
            cod = candidato_codigo(bloco)
            parags = [p.get_text(" ", strip=True) for p in li.find_all("p")]
            desc = next((p for p in parags if re.search(r"compras|pedidos|desconto|regulamento|selec", padrao(p)) and len(p) > 32), "")
            item = registro(titulo, cod, fonte, desc)
            if item:
                saida.append(item)
    else:
        # Pelando e Meliuz usam titulos de cupons h2/h3.
        for h in soup.find_all(["h2", "h3"]):
            titulo = h.get_text(" ", strip=True)
            n = padrao(titulo)
            if fonte == "Pelando" and "shopee" not in n:
                continue
            if fonte == "Meliuz" and not any(s in n for s in ["shopee", "cupom", "desconto", "frete", "off", "econom", "pedidos", "codigo", "voucher", "oferta"]):
                continue
            if re.search(r"todos os cupons|confira todos|como funciona|principais duvidas|termos|aplicador|extensao|cashback", n):
                continue
            parent = conteiner_heading(h)
            bloco = parent.get_text(" ", strip=True)
            if fonte == "Pelando" and re.search(r"\bExpirada\b|\bExpirado\b", bloco, re.I):
                continue
            cod = candidato_codigo(bloco)
            ps = [p.get_text(" ", strip=True) for p in parent.find_all("p", recursive=True)]
            desc = next((p for p in ps if 22 < len(p) < 260 and p != titulo and not "cashback" in padrao(p)), "")
            item = registro(titulo, cod, fonte, desc)
            if item:
                saida.append(item)
    return saida


def encontrar_worker(obj, nivel=0):
    if nivel > 7 or not isinstance(obj, (list, dict)):
        return []
    if isinstance(obj, list):
        return [y for x in obj[:1000] for y in encontrar_worker(x, nivel + 1)]
    if isinstance(obj.get("title"), str) and ("couponCode" in obj or "solGarimpaSource" in obj):
        return [obj]
    resultado = []
    for chave in ("data", "stores", "coupons", "cupons", "items", "result", "results"):
        if chave in obj:
            resultado += encontrar_worker(obj[chave], nivel + 1)
    return resultado


def coletar_worker():
    r = SESSAO.get(WORKER, timeout=25)
    r.raise_for_status()
    dados = r.json()
    saida = []
    for c in encontrar_worker(dados):
        if str(c.get("status", "active")).lower() not in ("active", "ativo"):
            continue
        v = c.get("expiresAt") or c.get("validUntil") or c.get("endDate")
        if v:
            try:
                if datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp() < datetime.now(timezone.utc).timestamp():
                    continue
            except (ValueError, TypeError):
                continue
        origem = limpar(c.get("solGarimpaSource") or "Pelando")
        fonte = "Meliuz" if "meliuz" in padrao(origem) else "Pelando"
        reg = registro(c.get("title"), c.get("couponCode"), fonte, c.get("description"), c.get("createdAt"), v)
        if reg:
            reg["sourceUrl"] = FONTES[fonte]
            saida.append(reg)
    return saida


def unir(itens):
    resultado = {}
    for c in itens:
        codigo = c.get("couponCode") or ""
        # Codigos iguais: um registro com todas as fontes.
        chave = "c:" + codigo if codigo else "t:" + re.sub(r"[^a-z0-9]+", "", padrao(c["title"]))
        if chave in resultado:
            velho = resultado[chave]
            for fonte in c["sources"]:
                if fonte not in velho["sources"]:
                    velho["sources"].append(fonte)
            if not velho["couponCode"] and c["couponCode"]:
                velho["couponCode"] = c["couponCode"]
            if velho["description"].startswith("Consulte") and not c["description"].startswith("Consulte"):
                velho["description"] = c["description"]
        else:
            resultado[chave] = c
    return list(resultado.values())


def main():
    coletados = []
    status = {}
    for fonte in FONTES:
        try:
            cupons = coletar_site(fonte)
            if len(cupons) < 3:
                raise ValueError("Menos de 3 cupons extraidos; layout possivelmente mudou")
            coletados.extend(cupons)
            status[fonte] = {"ok": True, "quantidade": len(cupons)}
            print(f"{fonte}: {len(cupons)} itens", flush=True)
        except Exception as e:
            status[fonte] = {"ok": False, "quantidade": 0, "erro": str(e)[:130]}
            print(f"AVISO {fonte}: {e}", flush=True)
    try:
        existentes = coletar_worker()
        coletados.extend(existentes)
        status["WorkerExistente"] = {"ok": True, "quantidade": len(existentes)}
    except Exception as e:
        status["WorkerExistente"] = {"ok": False, "quantidade": 0, "erro": str(e)[:130]}
        print(f"AVISO Worker: {e}", flush=True)
    unicos = unir(coletados)
    # Nao publicar catalogo vazio como se fosse atualizado.
    if not unicos:
        print("ERRO: Nenhum cupom acessivel. Catalogo anterior preservado.", file=sys.stderr)
        return 1
    # Ordenar: cupons com codigo primeiro, depois fonte.
    unicos.sort(key=lambda x: (not bool(x["couponCode"]), x["title"].casefold()))
    payload = {
        "generatedAt": AGORA,
        "refreshMinutes": 30,
        "note": "Listado pelas fontes; validade e uso devem ser conferidos na Shopee. Links afiliados de terceiros nao sao reutilizados.",
        "sources": status,
        "count": len(unicos),
        "coupons": unicos,
    }
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Salvos {len(unicos)} registros unicos em {SAIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
