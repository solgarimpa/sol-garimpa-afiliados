#!/usr/bin/env python3
"""Sincroniza SOMENTE cupons e promocoes ativos da Awin para Sol Garimpa.

Requer AWIN_PUBLISHER_TOKEN definido em GitHub Actions Secrets.
Nao publica o token nem substitui dados anteriores em caso de erro da API.
"""
import datetime as dt
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

PUBLISHER_ID = 3110826
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "cupons" / "ofertas.json"
ENDPOINT = f"https://api.awin.com/publisher/{PUBLISHER_ID}/promotions"
UTC = dt.timezone.utc
MAX_PAGES = 50
PAGE_SIZE = 200


def clean(value, max_length=500):
    return " ".join(str(value or "").split())[:max_length]


def as_datetime(value):
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    except (TypeError, ValueError):
        return None


def safe_tracking_url(value):
    url = clean(value, 3500)
    try:
        p = urllib.parse.urlsplit(url)
        if p.scheme.lower() != "https" or not p.hostname or p.username or p.password:
            return ""
        if p.hostname.lower() in ("localhost", "127.0.0.1") or p.hostname.endswith(".local"):
            return ""
        return url
    except ValueError:
        return ""


def unpack(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("promotions", "offers", "results", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                for k in ("promotions", "offers", "results", "items"):
                    if isinstance(value.get(k), list):
                        return value[k]
    raise ValueError("Formato inesperado de resposta da API da Awin")


def normalize(row, now):
    if not isinstance(row, dict):
        return None
    adv = row.get("advertiser") or {}
    if not isinstance(adv, dict) or adv.get("joined") is not True:
        return None
    link = safe_tracking_url(row.get("urlTracking"))
    title = clean(row.get("title"), 260)
    brand = clean(adv.get("name"), 100)
    if not link or not title or not brand:
        return None
    ends = as_datetime(row.get("endDate"))
    starts = as_datetime(row.get("startDate"))
    if (ends and ends <= now) or (starts and starts > now):
        return None
    voucher = row.get("voucher") if isinstance(row.get("voucher"), dict) else {}
    item_type = "cupom" if row.get("type") == "voucher" else "promocao"
    code = clean(voucher.get("code"), 90) if item_type == "cupom" else ""
    # Awin pode omitir o codigo quando nao ha adesao; nao inventa cupons.
    return {
        "id": clean(row.get("promotionId") or f"{adv.get('id')}:{title}", 180),
        "loja": brand,
        "tipo": item_type,
        "titulo": title,
        "descricao": clean(row.get("description"), 700),
        "termos": clean(row.get("terms"), 1200),
        "cupom": code,
        "validade": ends.isoformat().replace("+00:00", "Z") if ends else None,
        "link": link,
    }


def fetch_page(token, page):
    request_body = {
        "filters": {
            "membership": "joined",
            "regionCodes": ["BR"],
            "status": "active",
            "type": "all",
        },
        "pagination": {"page": page, "pageSize": PAGE_SIZE},
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "SolGarimpaCupons/1.0",
        },
        method="POST",
    )
    # Erros temporarios da API nao devem invalidar a rotina inteira imediatamente.
    # Nao repetir erros de autenticacao (401/403) ou respostas invalidas.
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                return unpack(json.load(response))
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
            delay = min(30, 2 ** attempt * 3)
            print(f"Awin temporariamente indisponivel (HTTP {exc.code}); tentativa {attempt + 2}/4 em {delay}s.")
            time.sleep(delay)
        except (TimeoutError, urllib.error.URLError) as exc:
            if attempt == 3:
                raise
            delay = min(30, 2 ** attempt * 3)
            print(f"Awin indisponivel ({type(exc).__name__}); tentativa {attempt + 2}/4 em {delay}s.")
            time.sleep(delay)


def main():
    token = os.environ.get("AWIN_PUBLISHER_TOKEN", "").strip()
    if not token:
        raise SystemExit("AWIN_PUBLISHER_TOKEN ausente: arquivo atual preservado.")
    now = dt.datetime.now(UTC)
    items = {}
    for page in range(1, MAX_PAGES + 1):
        records = fetch_page(token, page)
        for raw in records:
            item = normalize(raw, now)
            if item:
                items[item["id"]] = item
        if len(records) < PAGE_SIZE:
            break
    else:
        raise RuntimeError("Limite de paginas atingido; nao publicar dados incompletos.")
    values = sorted(items.values(), key=lambda x: (x["validade"] or "9999", x["loja"].casefold()))
    payload = {
        "fonte": "Awin Offers API",
        "publisher_id": PUBLISHER_ID,
        "atualizado_em": now.isoformat().replace("+00:00", "Z"),
        "total": len(values),
        "ofertas": values,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUTPUT.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(OUTPUT)
    print(f"Ofertas e cupons ativos Awin publicados: {len(values)}")


if __name__ == "__main__":
    main()
