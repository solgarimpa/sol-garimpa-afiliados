
#!/usr/bin/env python3
"""SOL GARIMPA - Sincronização oficial Lomadee."""
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
TARGET = (
    Path(__file__).resolve().parents[1]
    / "docs" / "lomadee" / "ofertas.json"
)
KEY = os.getenv("LOMADEE_API_TOKEN", "").strip()
CHANNEL_ID = os.getenv("LOMADEE_CHANNEL_ID", "").strip()
CHANNEL_NAME = os.getenv(
    "LOMADEE_CHANNEL_NAME", "Sol Garimpa"
).strip()

MAX_BRANDS_PAGES = 25
MAX_CAMPAIGN_PAGES = 15
MAX_PRODUCT_PAGES = 2
MAX_GENERATED_LINKS = 40
MAX_CARDS = 160

NOW = dt.datetime.now(dt.timezone.utc)
NEXT_REQUEST = 0.0
GENERATED = 0


def log(*items):
    print(*items, flush=True)


def https_url(raw):
    if not isinstance(raw, str):
        return ""
    try:
        p = urllib.parse.urlsplit(raw.strip())
        if (
            p.scheme != "https"
            or not p.netloc
            or p.username
            or p.password
        ):
            return ""
        return p.geturl()
    except ValueError:
        return ""


def timestamp(raw):
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        t = dt.datetime.fromisoformat(
            raw.strip().replace("Z", "+00:00")
        )
        if t.tzinfo is None:
            return t.replace(tzinfo=dt.timezone.utc)
        return t.astimezone(dt.timezone.utc)
    except ValueError:
        return None


def valid_campaign(c):
    if c.get("status") != "onTime":
        return False
    period = c.get("period") or {}
    start = timestamp(period.get("startAt"))
    end = timestamp(period.get("endAt"))
    return (
        (not start or start <= NOW)
        and (not end or end >= NOW)
    )


def request(path, params=None, payload=None):
    global NEXT_REQUEST

    if not KEY:
        raise RuntimeError(
            "Secret LOMADEE_API_TOKEN ausente"
        )

    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)

    body = (
        json.dumps(payload).encode("utf-8")
        if payload is not None else None
    )

    headers = {
        "x-api-key": KEY,
        "Accept": "application/json",
        "User-Agent": "SolGarimpa/1.0",
    }

    if body is not None:
        headers["Content-Type"] = "application/json"

    for attempt in range(3):
        gap = NEXT_REQUEST - time.monotonic()
        if gap > 0:
            time.sleep(gap)

        NEXT_REQUEST = time.monotonic() + 1.15

        req = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method="POST" if body is not None else "GET",
        )

        try:
            with urllib.request.urlopen(
                req, timeout=35
            ) as response:
                raw = response.read(4 * 1024 * 1024 + 1)

            if len(raw) > 4 * 1024 * 1024:
                raise RuntimeError(
                    "Resposta excedeu o limite"
                )

            data = json.loads(raw)

            if (
                isinstance(data, dict)
                and data.get("success") is False
            ):
                raise RuntimeError(
                    "API retornou success=false em " + path
                )

            return data

        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                retry = e.headers.get("Retry-After", "")
                wait = (
                    int(retry) if retry.isdecimal()
                    else 2 ** (attempt + 2)
                )
                time.sleep(max(1, min(65, wait)))
                continue

            raise RuntimeError(
                f"Erro HTTP {e.code} em {path}"
            ) from None

        except (TimeoutError, urllib.error.URLError) as e:
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(
                f"Erro de rede: {type(e).__name__}"
            ) from None

        except json.JSONDecodeError:
            raise RuntimeError(
                "Resposta não é JSON: " + path
            ) from None

    raise RuntimeError("Tentativas esgotadas")


def extract_rows(response):
    data = (
        response.get("data", [])
        if isinstance(response, dict)
        else response
    )

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        if isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data.get("data"), list):
            return data["data"]
        if "id" in data:
            return [data]

    raise RuntimeError(
        "Formato inesperado na resposta da API"
    )


def page_all(path, max_pages, limit, params=None,
             pagination_key="meta"):
    out = []

    for page in range(1, max_pages + 1):
        query = {"page": page, "limit": limit}
        query.update(params or {})

        response = request(path, query)
        rows = extract_rows(response)
        out.extend(
            row for row in rows
            if isinstance(row, dict)
        )

        meta = (
            response.get(pagination_key, {})
            if isinstance(response, dict) else {}
        )

        total_pages = (
            meta.get("totalPages")
            if isinstance(meta, dict) else None
        )

        if total_pages is not None:
            try:
                if page >= int(total_pages):
                    break
            except (ValueError, TypeError):
                pass

        if len(rows) < limit:
            break

    return out


def choose_channel(channels):
    possible = [
        x for x in (channels or [])
        if isinstance(x, dict)
        and any(
            https_url(y)
            for y in (x.get("shortUrls") or [])
        )
    ]

    if CHANNEL_ID:
        possible = [
            x for x in possible
            if str(x.get("id")) == CHANNEL_ID
        ]

    elif CHANNEL_NAME:
        matched = [
            x for x in possible
            if CHANNEL_NAME.casefold()
            in str(x.get("name", "")).casefold()
        ]
        if len(matched) == 1:
            possible = matched
        elif len(possible) > 1:
            possible = []

    elif len(possible) > 1:
        possible = []

    if len(possible) != 1:
        return ""

    return next(
        (
            https_url(u)
            for u in possible[0].get("shortUrls", [])
            if https_url(u)
        ),
        "",
    )


def build_shortlink(
    brand_id, link_type,
    feature_id="", merchant_url=""
):
    global GENERATED

    if GENERATED >= MAX_GENERATED_LINKS:
        return ""

    if not brand_id:
        return ""

    body = {
        "organizationId": brand_id,
        "type": link_type,
    }

    if link_type in ("Coupon", "Offer"):
        if not feature_id:
            return ""
        body["featureId"] = feature_id

    elif link_type == "Custom":
        url = https_url(merchant_url)
        if not url:
            return ""
        body["url"] = url

    else:
        return ""

    GENERATED += 1

    try:
        response = request(
            "/affiliate/shortener/url",
            payload=body,
        )
        return choose_channel(response)

    except RuntimeError as e:
        log("Falha ao gerar link:", str(e))
        if "403" in str(e):
            GENERATED = MAX_GENERATED_LINKS
        return ""


def ident(prefix, *values):
    content = "|".join(map(str, values))
    code = hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()[:20]
    return prefix + code


def clean_text(value, size=400):
    if not isinstance(value, str):
        return ""
    return re.sub(
        r"<[^>]*>", " ", value
    ).replace("\x00", "").strip()[:size]


def campaign_card(c, brand):
    if not valid_campaign(c) or not brand:
        return None

    kind = c.get("type")
    if kind not in ("GenericCoupon", "Offer"):
        return None

    brand_id = str(c.get("organizationId") or "")
    name = clean_text(c.get("name"), 180)

    if not brand_id or not name:
        return None

    link = choose_channel(c.get("channels") or [])

    if not link:
        link = build_shortlink(
            brand_id,
            "Coupon" if kind == "GenericCoupon" else "Offer",
            str(c.get("id") or ""),
        )

    if not link:
        return None

    banners = (
        (c.get("mediaKit") or {}).get("banners") or []
    )
    image = next(
        (
            https_url(u)
            for u in banners
            if https_url(u)
        ),
        "",
    )

    return {
        "id": ident("lc-", c.get("id"), brand_id),
        "loja": brand["name"],
        "dominio_loja": brand.get("site", ""),
        "logo_url": brand.get("logo", ""),
        "tipo": (
            "cupom" if kind == "GenericCoupon"
            else "promocao"
        ),
        "titulo": name,
        "imagem": image,
        "preco": None,
        "preco_anterior": None,
        "cupom": (
            clean_text(c.get("code"), 80)
            if kind == "GenericCoupon" else None
        ),
        "validade": (
            (c.get("period") or {}).get("endAt")
        ),
        "descricao": clean_text(
            c.get("description"), 250
        ),
        "link": link,
        "origem": "Lomadee",
    }


def as_money_cents(value):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value <= 0
    ):
        return None
    return round(value / 100, 2)


def product_card(p, brand):
    if not brand or p.get("available") is False:
        return None

    brand_id = str(p.get("organizationId") or "")
    name = clean_text(p.get("name"), 180)
    product_url = https_url(p.get("url"))

    if not (brand_id and name and product_url):
        return None

    options = p.get("options") or []
    active = [
        o for o in options
        if isinstance(o, dict)
        and o.get("available") is not False
    ]

    if options and not active:
        return None

    price = None
    old = None

    image = next(
        (
            https_url(x.get("url"))
            for x in (p.get("images") or [])
            if isinstance(x, dict)
            and https_url(x.get("url"))
        ),
        "",
    )

    for option in active:
        if not image:
            image = next(
                (
                    https_url(x.get("url"))
                    for x in (option.get("images") or [])
                    if isinstance(x, dict)
                    and https_url(x.get("url"))
                ),
                "",
            )

        for pricing in option.get("pricing") or []:
            if not isinstance(pricing, dict):
                continue

            new = as_money_cents(
                pricing.get("price")
            )
            if new is None:
                continue

            before = as_money_cents(
                pricing.get("listPrice")
            )

            if price is None or new < price:
                price = new
                old = (
                    before if before and before > new
                    else None
                )

    link = build_shortlink(
        brand_id,
        "Custom",
        merchant_url=product_url,
    )

    if not link:
        return None

    return {
        "id": ident("lp-", p.get("id"), brand_id),
        "loja": brand["name"],
        "dominio_loja": brand.get("site", ""),
        "logo_url": brand.get("logo", ""),
        "tipo": "produto",
        "titulo": name,
        "imagem": image,
        "preco": price,
        "preco_anterior": old,
        "cupom": None,
        "validade": None,
        "descricao": clean_text(
            p.get("description"), 220
        ),
        "link": link,
        "origem": "Lomadee",
    }


def round_robin(cards):
    groups = defaultdict(list)

    for c in cards:
        groups[c["loja"]].append(c)

    names = sorted(groups, key=str.casefold)
    output = []

    while (
        any(groups.values())
        and len(output) < MAX_CARDS
    ):
        for name in names:
            if (
                groups[name]
                and len(output) < MAX_CARDS
            ):
                output.append(
                    groups[name].pop(0)
                )

    return output


def main():
    if not KEY:
        raise RuntimeError(
            "Configure LOMADEE_API_TOKEN "
            "nos Secrets do GitHub."
        )

    brands = page_all(
        "/affiliate/brands",
        MAX_BRANDS_PAGES,
        20,
        pagination_key="pagination",
    )

    brand_by_id = {}

    for brand in brands:
        brand_id = str(brand.get("id") or "")
        network = brand.get("network") or {}

        if (
            brand_id
            and brand.get("name")
            and network.get("active", True)
        ):
            brand_by_id[brand_id] = brand

    log("Marcas ativas:", len(brand_by_id))

    campaigns = page_all(
        "/affiliate/campaigns",
        MAX_CAMPAIGN_PAGES,
        20,
        params={
            "status": "onTime",
            "types": "GenericCoupon,Offer",
        },
    )

    log("Campanhas encontradas:", len(campaigns))

    cards = []

    for campaign in campaigns:
        brand = brand_by_id.get(
            str(campaign.get("organizationId"))
        )
        result = campaign_card(
            campaign, brand
        )
        if result:
            cards.append(result)

    if MAX_PRODUCT_PAGES:
        try:
            products = page_all(
                "/affiliate/products",
                MAX_PRODUCT_PAGES,
                100,
                params={"isAvailable": "true"},
                pagination_key="count",
            )
        except RuntimeError as e:
            log("Produtos indisponíveis:", str(e))
            products = []

        log("Produtos encontrados:", len(products))

        for product in products:
            if GENERATED >= MAX_GENERATED_LINKS:
                break

            brand = brand_by_id.get(
                str(product.get("organizationId"))
            )

            result = product_card(
                product, brand
            )

            if result:
                cards.append(result)

    unique = {}
    for c in cards:
        unique[c["id"]] = c

    cards = round_robin(list(unique.values()))

    partners = [
        {
            "id": b["id"],
            "loja": b["name"],
            "dominio_loja": b.get("site", ""),
            "logo_url": https_url(
                b.get("logo")
            ),
        }
        for b in sorted(
            brand_by_id.values(),
            key=lambda x: x["name"].casefold(),
        )
    ]

    data = {
        "fonte": "Lomadee",
        "atualizado_em": NOW.isoformat(
            timespec="seconds"
        ),
        "parceiros": partners,
        "cards": cards,
        "status": {
            "integracao": "api_oficial",
            "com_ofertas": len(cards),
            "campanhas_recebidas": len(campaigns),
            "marcas_ativas": len(brand_by_id),
            "links_gerados": GENERATED,
        },
    }

    TARGET.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp = TARGET.with_suffix(
        ".json.tmp"
    )

    temp.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    temp.replace(TARGET)

    log(
        "Lomadee atualizada:",
        len(cards),
        "ofertas;",
        len(partners),
        "marcas;",
        GENERATED,
        "links solicitados.",
    )

    if not cards:
        log(
            "Sem ofertas elegíveis ou links "
            "rastreados para o canal selecionado."
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            "ERRO LOMADEE:", str(exc),
            file=sys.stderr,
        )
        sys.exit(1)
