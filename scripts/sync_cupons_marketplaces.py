#!/usr/bin/env python3
"""SOL GARIMPA - catálogo informativo de cupons de seis marketplaces.

Fontes: Pelando, Cuponomia, Meliuz e Workers proprios ja existentes.
Extrai apenas dados factuais publicamente anunciados; nao contorna bloqueios,
nao copia links de afiliados alheios, nao afirma que foi testado no checkout.
"""
import concurrent.futures
import datetime as dt
import json
import re
import sys
import unicodedata
from pathlib import Path

import requests
from bs4 import BeautifulSoup

UTC = dt.timezone.utc
NOW = dt.datetime.now(UTC)
STAMP = NOW.isoformat(timespec="seconds")
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "central"
BASE_WORKER = "https://sol-garimpa-cupons.contato-solgarimpa.workers.dev/?loja="
SHEIN_WORKER = "https://sol-garimpa-shein-cupons.contato-solgarimpa.workers.dev/?loja=Shein"
HEADERS = {
    "User-Agent": "SolGarimpaCouponMonitor/1.1 (+https://www.ofertaspravc.com.br)",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
}
MARKETS = {
    "mercado-livre": {
        "name": "Mercado Livre", "worker": "Mercado Livre",
        "pelando": "mercado-livre", "cuponomia": "mercado-livre",
        "meliuz": "cupom-desconto-mercado-livre",
    },
    "shopee": {
        "name": "Shopee", "worker": "Shopee",
        "pelando": "shopee", "cuponomia": "shopee", "meliuz": "cupom-shopee",
    },
    "magalu": {
        "name": "Magalu", "worker": "Magalu",
        "pelando": "magalu", "cuponomia": "magalu",
        "meliuz": "cupom-magazine-luiza",
    },
    "aliexpress": {
        "name": "AliExpress", "worker": "AliExpress",
        "pelando": "aliexpress", "cuponomia": "aliexpress",
        "meliuz": "cupom-aliexpress",
    },
    "shein": {
        "name": "SHEIN", "worker": "Shein",
        "pelando": "shein", "cuponomia": "shein", "meliuz": "cupom-shein",
    },
    "amazon": {
        "name": "Amazon", "worker": "Amazon",
        "pelando": "amazon", "cuponomia": "amazon",
        "meliuz": "cupom-desconto-amazon",
    },
}
EXCLUDE = re.compile(
    r"perguntas frequentes|principais duvidas|todos os cupons|confira todos|"
    r"como (usar|conseguir|funciona|ganhar)|por que meu|resumo de|"
    r"onde encontrar|a loja e confiavel|avalie |pessoas que|"
    r"cadastre-se|instale a extensao|teste descontos|"
    r"descubra os melhores|regras e excecoes|"
    r"o cupom expira|tem como acumular|"
    r"compra segura|programa de afiliados|"
    r"voce ainda pode ganhar cashback",
    re.I,
)
EXCLUSIVE = re.compile(
    r"exclusivo (?:para quem vem|no site|na plataforma|do|da|de|pelo|pela) "
    r"(?:meliuz|cuponomia|pelando)|"
    r"exclusivo meliuz|cashback exclusivo (?:da|do) (?:meliuz|cuponomia)",
    re.I,
)


def plain(value):
    return re.sub(r"\s+", " ", BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)).strip()


def norm(value):
    return "".join(c for c in unicodedata.normalize("NFKD", str(value or "")) if not unicodedata.combining(c)).casefold()


def percentage_or_amount(title):
    title = plain(title)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", title)
    if m:
        return m.group(1) + "% OFF"
    m = re.search(r"R\$\s*(\d+(?:[.,]\d{1,2})?)", title)
    if m and re.search(r"off|cupom|desconto|economiz|ganh|garant|abatimento", norm(title)):
        return "R$ " + m.group(1) + " OFF"
    if re.search(r"frete gr[aá]tis", title, re.I):
        return "FRETE GRÁTIS"
    return "OFERTA"


def actual_code(block):
    # Nunca interpretar "CUPOMNOLINK" ou "GANHECUPOM" como codigo.
    for pat in (
        r"(?:Pegar|Ver|Usar)\s+cupom\s+([A-Z0-9][A-Z0-9_-]{3,34})",
        r"\b([A-Z0-9][A-Z0-9_-]{3,34})\s+Copiar\b",
    ):
        m = re.search(pat, block, re.I)
        if m:
            cod = m.group(1).upper()
            if cod not in {
                "CUPOM", "CUPOMAQUI", "CUPOMNOLINK", "GANHECUPOM",
                "GARANTADESCONTO", "GANHEDESCONTO", "RESGATECUPONS",
                "DESCONTONOLINK", "DESCONTOAQUI", "SHOPEE", "COPIAR"
            }:
                return cod
    return ""


def summary(text):
    text = plain(text)[:350]
    text = re.sub(r"\+?\s*at[eé]?\s*\d+(?:[,.]\d+)?%\s*(?:de\s*)?cashback", "", text, flags=re.I)
    text = re.sub(r"cashback\s+(?:de\s+)?\d+(?:[,.]\d+)?%", "", text, flags=re.I)
    return text.strip(" ;.-")[:190]


def as_time(val):
    if not val:
        return None
    try:
        d = dt.datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=UTC)).astimezone(UTC)
    except (ValueError, TypeError):
        return None


def record(title, code, desc, source, url, published=None, expiry=None):
    title = plain(title)[:175]
    desc = summary(desc)
    normalized = norm(title)
    if len(title) < 10 or "?" in title or EXCLUDE.search(normalized):
        return None
    if EXCLUSIVE.search(norm(title + " " + desc)):
        return None
    if not re.search(
        r"cupom|off|desconto|oferta|frete gratis|voucher|economiz|ganh|garant|"
        r"promoc|reais|r\$|%|relampago|codigo|sele[cç]|eletro",
        normalized,
    ):
        return None
    expires = as_time(expiry)
    if expiry and not expires:
        return None
    if expires and expires <= NOW:
        return None
    code = plain(code).replace(" ", "").upper()[:50]
    if code and not re.fullmatch(r"[A-Z0-9_-]{4,50}", code):
        code = ""
    return {
        "title": title,
        "couponCode": code,
        "discountText": percentage_or_amount(title),
        "description": desc or "Confira os produtos participantes e as condições na loja.",
        "sources": [source],
        "sourceUrl": url,
        "publishedAt": published if as_time(published) else None,
        "expiresAt": expires.isoformat() if expires else None,
        "observedAt": STAMP,
        "status": "listed",
    }


def get(url, json_mode=False):
    r = requests.get(url, headers=HEADERS, timeout=18)
    r.raise_for_status()
    if json_mode:
        return r.json()
    if "html" not in r.headers.get("Content-Type", "text/html").lower():
        raise RuntimeError("resposta nao HTML")
    if len(r.text) < 700 or any(s in r.text.lower() for s in ("access denied", "just a moment", "captcha required")):
        raise RuntimeError("site bloqueou ou nao retornou conteudo")
    return BeautifulSoup(r.text, "html.parser")


def source_url(conf, source):
    if source == "Pelando":
        return "https://www.pelando.com.br/cupons-de-descontos/" + conf["pelando"]
    if source == "Cuponomia":
        return "https://www.cuponomia.com.br/desconto/" + conf["cuponomia"]
    return "https://www.meliuz.com.br/desconto/" + conf["meliuz"]


def block_of_heading(h):
    cur = h
    for _ in range(6):
        if cur.parent is None:
            break
        cur = cur.parent
        txt = cur.get_text(" ", strip=True)
        count = len(cur.find_all(["h2", "h3"], recursive=True))
        if 50 <= len(txt) <= 1600 and count <= 2:
            return cur
    return h.parent or h


def parse_site(conf, source):
    url = source_url(conf, source)
    doc = get(url)
    out = []
    if source == "Cuponomia":
        for li in doc.select("li"):
            h = li.find("h3")
            if not h:
                continue
            title = h.get_text(" ", strip=True)
            all_text = li.get_text(" ", strip=True)
            if len(all_text) > 3500:
                continue
            p = [x.get_text(" ", strip=True) for x in li.find_all("p")]
            desc = next((x for x in p if 25 <= len(x) <= 250 and re.search(r"pedido|compra|desconto|valido|sele|carrinho|regulamento|oferta", norm(x))), "")
            r = record(title, actual_code(all_text), desc, source, url)
            if r:
                out.append(r)
    else:
        expired_section = False
        for h in doc.find_all(["h2", "h3"]):
            title = h.get_text(" ", strip=True)
            n = norm(title)
            if re.search(r"cupons (?:expirados|vencidos)", n):
                expired_section = True
                continue
            if expired_section:
                continue
            if source == "Pelando" and not re.search(r"cupom|r\$|off|%|frete|desconto|voucher", n):
                continue
            block = block_of_heading(h)
            full_text = block.get_text(" ", strip=True)
            if "Expirado" in full_text[:90] or "Expirada" in full_text[:90]:
                continue
            ps = [p.get_text(" ", strip=True) for p in block.find_all("p")]
            desc = next((p for p in ps if 24 <= len(p) <= 250 and p != title and not re.search(r"cashback", norm(p))), "")
            r = record(title, actual_code(full_text), desc, source, url)
            if r:
                out.append(r)
    if len(out) < 2:
        raise ValueError("extraidos menos de 2 cupons: pagina bloqueada ou seletor alterado")
    return out


def deep_coupons(value, depth=0):
    if depth > 7:
        return []
    if isinstance(value, list):
        return [r for item in value[:1200] for r in deep_coupons(item, depth + 1)]
    if not isinstance(value, dict):
        return []
    if isinstance(value.get("title"), str) and (
        "couponCode" in value or "solGarimpaSource" in value
        or "code" in value or "discountPercentage" in value
    ):
        return [value]
    return [
        r for key in ("data", "stores", "coupons", "cupons", "items", "result", "results", "offers", "vouchers")
        if key in value for r in deep_coupons(value[key], depth + 1)
    ]


def parse_worker(market, conf):
    url = (SHEIN_WORKER if market == "shein" else BASE_WORKER + requests.utils.quote(conf["worker"]))
    obj = get(url, json_mode=True)
    out = []
    for c in deep_coupons(obj):
        if norm(c.get("status", "active")) not in ("active", "ativo", "listed"):
            continue
        source_text = norm(c.get("solGarimpaSource", ""))
        src = "Pelando" if "pelando" in source_text else (
            "Meliuz" if "meliuz" in source_text else "Worker existente"
        )
        r = record(
            c.get("title"), c.get("couponCode") or c.get("code"),
            c.get("description") or c.get("rulesDescription"),
            src, url, c.get("createdAt") or c.get("publishedAt"),
            c.get("expiresAt") or c.get("validUntil") or c.get("endDate")
        )
        if r:
            out.append(r)
    if not out:
        raise ValueError("Worker sem cupons no formato esperado")
    return out


def combine(items):
    merged = {}
    for c in items:
        key_code = norm(c["couponCode"])
        key_title = re.sub(r"[^a-z0-9]+", "", norm(c["title"]))
        # Deduplicacao por codigo, ou por titulo quando nao tem codigo.
        key = ("code:" + key_code) if key_code else ("title:" + key_title)
        old = merged.get(key)
        if not old:
            merged[key] = c
            continue
        for s in c["sources"]:
            if s not in old["sources"]:
                old["sources"].append(s)
        if len(c.get("description", "")) > len(old.get("description", "")) and len(c["description"]) < 180:
            old["description"] = c["description"]
        if c.get("publishedAt") and not old.get("publishedAt"):
            old["publishedAt"] = c["publishedAt"]
    values = list(merged.values())
    values.sort(key=lambda c: (
        -int(bool(c["couponCode"])),
        -len(c["sources"]),
        -(as_time(c.get("publishedAt")) or dt.datetime(1970,1,1,tzinfo=UTC)).timestamp(),
        norm(c["title"]),
    ))
    return values[:250]


def process(market, conf):
    all_items, statuses = [], {}
    tasks = [(name, source_url(conf, name)) for name in ("Pelando", "Cuponomia", "Meliuz")]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(parse_site, conf, name): name for name, _ in tasks}
        futures[pool.submit(parse_worker, market, conf)] = "WorkerExistente"
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                items = future.result()
                all_items.extend(items)
                statuses[name] = {"ok": True, "quantidade": len(items)}
            except Exception as e:
                statuses[name] = {"ok": False, "quantidade": 0, "erro": str(e)[:140]}
    records = combine(all_items)
    if not records:
        print("ERRO", market, "sem dados; arquivo anterior preservado", statuses, flush=True)
        return False
    output = OUTPUT / (market + "-cupons.json")
    current_source_health = {name: statuses[name] for name in sorted(statuses)}
    payload = {
        "market": market,
        "name": conf["name"],
        "generatedAt": STAMP,
        "refreshMinutes": 30,
        "count": len(records),
        "sources": current_source_health,
        "note": "Cupons listados nas fontes, nao testados no checkout. Cashback exclusivo de outros sites nao e oferecido pela Sol Garimpa.",
        "coupons": records,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OK", market, len(records), "codigos", sum(bool(r["couponCode"]) for r in records), current_source_health, flush=True)
    return True


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    successes = sum(process(k, v) for k, v in MARKETS.items())
    print("Mercados gerados", successes, "/", len(MARKETS), flush=True)
    return 0 if successes > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
