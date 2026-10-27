
#!/usr/bin/env python3
"""SOL GARIMPA: coleta Lomadee, sem publicar links sem rastreamento."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

API = "https://api.lomadee.com.br"
TARGET = Path(__file__).resolve().parents[1] / "docs" / "lomadee" / "ofertas.json"
KEY = os.getenv("LOMADEE_API_TOKEN", "").strip()
CHANNEL_ID = os.getenv("LOMADEE_CHANNEL_ID", "").strip()
CHANNEL_NAME = os.getenv("LOMADEE_CHANNEL_NAME", "Sol Garimpa").strip()

MAX_LINKS = 45
MAX_CARDS = 160
NOW = dt.datetime.now(dt.timezone.utc)
next_request_at = 0.0
links_generated = 0


def safe_url(value):
    if not isinstance(value, str):
        return ""
    try:
        u = urllib.parse.urlsplit(value.strip())
        if u.scheme == "https" and u.netloc and not u.username and not u.password:
            return u.geturl()
    except ValueError:
        pass
    return ""


def date(value):
    if not value or not isinstance(value, str):
        return None
    try:
        x = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return x.replace(tzinfo=dt.timezone.utc) if not x.tzinfo else x.astimezone(dt.timezone.utc)
    except ValueError:
        return None


def text(value, n=200):
    if not isinstance(value, str):
        return ""
    return re.sub(r"<[^>]*>", " ", value).replace("\x00", "").strip()[:n]


def request(path, params=None, payload=None):
    global next_request_at
    query = "?" + urllib.parse.urlencode(params) if params else ""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {
        "x-api-key": KEY,
        "Accept": "application/json",
        "User-Agent": "SolGarimpa/1.1"
    }

    if body is not None:
        headers["Content-Type"] = "application/json"

    for attempt in range(3):
        wait = next_request_at - time.monotonic()
        if wait > 0:
            time.sleep(wait)

        next_request_at = time.monotonic() + 1.1
        req = urllib.request.Request(
            API + path + query,
            headers=headers,
            data=body,
            method="POST" if body is not None else "GET"
        )

        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                raw = response.read(5_000_001)

            if len(raw) > 5_000_000:
                raise RuntimeError(f"Resposta excessiva em {path}")

            data = json.loads(raw)

            if isinstance(data, dict) and data.get("success") is False:
                raise RuntimeError(f"API retornou success=false em {path}")

            return data

        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                retry_after = exc.headers.get("Retry-After", "")
                delay = int(retry_after) if retry_after.isdecimal() else 3 * (2 ** attempt)
                time.sleep(min(max(delay, 2), 65))
                continue
            raise RuntimeError(f"HTTP {exc.code} em {path}") from None

        except (urllib.error.URLError, TimeoutError):
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            raise RuntimeError(f"Sem resposta da rede em {path}") from None

        except (ValueError, UnicodeError):
            raise RuntimeError(f"Resposta JSON inválida em {path}") from None

    raise RuntimeError(f"Falha persistente em {path}")


def rows(response):
    data = response.get("data", []) if isinstance(response, dict) else response

    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]

    if isinstance(data, dict):
        if isinstance(data.get("items"), list):
            return [x for x in data["items"] if isinstance(x, dict)]
        if "id" in data:
            return [data]

    raise RuntimeError("Formato de resposta desconhecido")


def paginate(path, limit, max_pages, params=None, meta_key="meta"):
    result = []

    for page in range(1, max_pages + 1):
        args = {"page": page, "limit": limit, **(params or {})}
        response = request(path, args)
        batch = rows(response)
        result.extend(batch)

        pagination = response.get(meta_key) or {} if isinstance(response, dict) else {}
        total_pages = pagination.get("totalPages") if isinstance(pagination, dict) else None

        if not batch or len(batch) < limit:
            break

        if total_pages is not None and page >= int(total_pages):
            break

        if meta_key == "count" and isinstance(response.get("count"), int):
            if page * limit >= response["count"]:
                break

    return result


def fetch_campaigns():
    # Caso ocorra HTTP 500, tentar filtros mais simples.
    attempts = [
        {"status": "onTime", "types": "GenericCoupon,Offer"},
        {"types": "GenericCoupon"},
        {"types": "Offer"},
        {}
    ]

    failures = []

    for filters in attempts:
        try:
            result = paginate("/affiliate/campaigns", 10, 12, filters)
            print(
                f"Campanhas: consulta {filters or 'sem filtros'} retornou {len(result)} registros",
                flush=True
            )
            return result, "ok"
        except RuntimeError as e:
            failures.append(str(e))
            print(
                f"Campanhas: tentativa {filters or 'sem filtros'} falhou: {e}",
                flush=True
            )

    print("Campanhas indisponíveis nesta execução.", flush=True)
    return [], "falha: " + "; ".join(failures[:2])


def select_link(channels):
    # A API de encurtamento retorna uma lista de canais.
    if isinstance(channels, dict):
        channels = channels.get("data") or channels.get("channels") or []

    if not isinstance(channels, list):
        return ""

    valid = [
        c for c in channels
        if isinstance(c, dict)
        and any(safe_url(u) for u in (c.get("shortUrls") or []))
    ]

    if CHANNEL_ID:
        valid = [
            c for c in valid
            if str(c.get("id")) == CHANNEL_ID
        ]
    elif CHANNEL_NAME and len(valid) > 1:
        matches = [
            c for c in valid
            if CHANNEL_NAME.casefold() in str(c.get("name") or "").casefold()
        ]
        valid = matches if len(matches) == 1 else []

    if len(valid) != 1:
        return ""

    return next(
        (safe_url(u) for u in valid[0].get("shortUrls", []) if safe_url(u)),
        ""
    )


def shortlink(organization_id, kind, feature_id=None, url=None):
    global links_generated

    if links_generated >= MAX_LINKS or not organization_id:
        return ""

    payload = {
        "organizationId": str(organization_id),
        "type": kind
    }

    if kind in ("Coupon", "Offer"):
        if not feature_id:
            return ""
        payload["featureId"] = str(feature_id)

    elif kind == "Custom":
        if not safe_url(url):
            return ""
        payload["url"] = safe_url(url)

    else:
        return ""

    links_generated += 1

    try:
        return select_link(
            request("/affiliate/shortener/url", payload=payload)
        )
    except RuntimeError as e:
        print("Falha ao gerar link:", e, flush=True)
        return ""


def ident(prefix, *args):
    content = "|".join(map(str, args))
    return prefix + hashlib.sha256(
        content.encode()
    ).hexdigest()[:20]


def active_campaign(c):
    period = c.get("period") if isinstance(c.get("period"), dict) else {}
    start = date(period.get("startAt"))
    end = date(period.get("endAt"))

    return (
        c.get("status") == "onTime"
        and (not start or start <= NOW)
        and (not end or end >= NOW)
    )


def campaign_card(c, brand):
    kind = c.get("type")

    if not brand or kind not in ("GenericCoupon", "Offer") or not active_campaign(c):
        return None

    bid = str(c.get("organizationId") or "")
    title = text(c.get("name"), 180)

    if not bid or not title:
        return None

    link = select_link(c.get("channels"))

    if not link:
        link = shortlink(
            bid,
            "Coupon" if kind == "GenericCoupon" else "Offer",
            c.get("id")
        )

    if not link:
        return None

    banners = (c.get("mediaKit") or {}).get("banners") or []
    image = next(
        (safe_url(x) for x in banners if safe_url(x)),
        ""
    )

    return {
        "id": ident("lc-", bid, c.get("id")),
        "loja": brand["name"],
        "tipo": "cupom" if kind == "GenericCoupon" else "promocao",
        "titulo": title,
        "imagem": image,
        "link": link,
        "preco": None,
        "preco_anterior": None,
        "cupom": text(c.get("code"), 80) or None,
        "validade": (c.get("period") or {}).get("endAt"),
        "descricao": text(c.get("description"), 240),
        "origem": "Lomadee"
    }


def cents(x):
    if isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0:
        return round(x / 100, 2)
    return None


def product_card(p, brand):
    if not brand or p.get("available") is False:
        return None

    bid = str(p.get("organizationId") or "")
    url = safe_url(p.get("url"))

    if not bid or not url or not text(p.get("name")):
        return None

    options = [
        o for o in (p.get("options") or [])
        if isinstance(o, dict) and o.get("available") is not False
    ]

    price = None
    old = None

    image = next(
        (
            safe_url(x.get("url"))
            for x in (p.get("images") or [])
            if isinstance(x, dict) and safe_url(x.get("url"))
        ),
        ""
    )

    for option in options:
        if not image:
            image = next(
                (
                    safe_url(x.get("url"))
                    for x in (option.get("images") or [])
                    if isinstance(x, dict) and safe_url(x.get("url"))
                ),
                ""
            )

        for pricing in option.get("pricing") or []:
            if not isinstance(pricing, dict):
                continue

            new = cents(pricing.get("price"))

            if new is not None and (price is None or new < price):
                price = new
                before = cents(pricing.get("listPrice"))
                old = before if before and before > new else None

    link = shortlink(bid, "Custom", url=url)

    if not link:
        return None

    return {
        "id": ident("lp-", bid, p.get("id")),
        "loja": brand["name"],
        "tipo": "produto",
        "titulo": text(p.get("name"), 180),
        "imagem": image,
        "link": link,
        "preco": price,
        "preco_anterior": old,
        "cupom": None,
        "validade": None,
        "descricao": text(p.get("description"), 220),
        "origem": "Lomadee"
    }


def ordered(cards):
    by_store = defaultdict(list)

    for card in cards:
        by_store[card["loja"]].append(card)

    output = []

    while len(output) < MAX_CARDS and any(by_store.values()):
        for store in sorted(by_store, key=str.casefold):
            if by_store[store] and len(output) < MAX_CARDS:
                output.append(by_store[store].pop(0))

    return output


def main():
    if not KEY:
        raise RuntimeError("GitHub Secret LOMADEE_API_TOKEN ausente")

    if not KEY.isascii() or "•" in KEY or "…" in KEY:
        raise RuntimeError("Chave mascarada ou inválida no GitHub Secret")

    brands = paginate(
        "/affiliate/brands",
        20,
        25,
        meta_key="pagination"
    )

    brands_by_id = {
        str(b["id"]): b
        for b in brands
        if b.get("id") and b.get("name")
    }

    print("Marcas encontradas:", len(brands_by_id), flush=True)

    campaigns, camp_status = fetch_campaigns()

    cards = []

    for c in campaigns:
        obj = campaign_card(
            c,
            brands_by_id.get(str(c.get("organizationId")))
        )
        if obj:
            cards.append(obj)

    try:
        products = paginate(
            "/affiliate/products",
            20,
            3,
            {"isAvailable": "true"},
            "count"
        )
        product_status = "ok"

    except RuntimeError as e:
        print("Produtos indisponíveis:", e, flush=True)
        products = []
        product_status = "falha: " + str(e)

    print("Produtos recebidos:", len(products), flush=True)

    for p in products:
        if links_generated >= MAX_LINKS:
            break

        obj = product_card(
            p,
            brands_by_id.get(str(p.get("organizationId")))
        )

        if obj:
            cards.append(obj)

    if camp_status != "ok" and product_status != "ok":
        raise RuntimeError(
            "Campanhas e produtos falharam; catálogo anterior mantido."
        )

    unique = {c["id"]: c for c in cards}
    ordered_cards = ordered(list(unique.values()))

    catalog = {
        "fonte": "Lomadee",
        "atualizado_em": NOW.isoformat(timespec="seconds"),
        "parceiros": [
            {"id": k, "loja": v["name"]}
            for k, v in brands_by_id.items()
        ],
        "cards": ordered_cards,
        "status": {
            "integracao": "api_oficial",
            "com_ofertas": len(ordered_cards),
            "marcas": len(brands_by_id),
            "campanhas": len(campaigns),
            "produtos": len(products),
            "links_solicitados": links_generated,
            "consulta_campanhas": camp_status,
            "consulta_produtos": product_status
        }
    }

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    temp = TARGET.with_suffix(".tmp")

    temp.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    temp.replace(TARGET)

    print(
        "Catálogo Lomadee salvo:",
        len(ordered_cards),
        "ofertas rastreáveis",
        flush=True
    )

    if not ordered_cards:
        print(
            "Nenhuma oferta com link rastreável foi confirmada; "
            "não são criadas ofertas fictícias.",
            flush=True
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERRO LOMADEE:", str(e), file=sys.stderr)
        sys.exit(1)
