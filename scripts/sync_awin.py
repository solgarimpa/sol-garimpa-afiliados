
#!/usr/bin/env python3
"""SOL GARIMPA - Sincronizacao automatica Awin.

Consulta programas aprovados, produtos, cupons e promocoes.
Gera o catalogo para GitHub Pages e as filas do WhatsApp.
Utiliza credenciais armazenadas nos GitHub Secrets.
"""

import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse, urlsplit, urlunsplit

PUBLISHER_ID = 3110826
UTC = dt.timezone.utc

PRODUCTS_PER_STORE = 40
OFFERS_PER_STORE = 5

TARGET = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "ofertas.json"
)

SITE_URL = "https://www.ofertaspravc.com.br"

# Nomes alternativos usados nos feeds.
# Somente funcionam se a loja estiver aprovada na API.

ALIASES = {
    "kabum": "Kabum BR",
    "kabumbr": "Kabum BR",
    "kabumcombr": "Kabum BR",
    "nike": "Nike BR",
    "nikebr": "Nike BR",
    "cloviscalcados": "Clovis Calçados BR",
    "farmaciasindiana": "Farmácias Indiana BR",
    "sharkninja": "Shark-Ninja BR",
    "earfun": "Earfun, Inc",
    "galiciaeducacao": "Afiliados Galícia Educação",
    "afiliadosgaliciaeducacao": "Afiliados Galícia Educação",
    "eotica": "Eotica BR",
    "eurorelogios": "Eurorelogios BR",
    "futfanatics": "Fut Fanatics BR",
    "havaianas": "Havaianas BR",
    "lg": "LG BR",
    "lego": "Lego BR",
    "mizuno": "Mizuno BR",
    "polishop": "Polishop BR",
    "posthaus": "Posthaus BR",
    "samsclub": "Sam's Club BR",
    "soldiersnutrition": "Soldiers Nutrition BR",
    "stanley": "Stanley BR",
    "technos": "Technos BR",
    "tiasonia": "Tia Sônia BR",
    "underarmour": "Under Armour BR",
}

STORES = []
by_slug = {}


def compact(value):
    value = unicodedata.normalize(
        "NFKD", str(value or "")
    )
    value = "".join(
        x for x in value
        if not unicodedata.combining(x)
    )
    return re.sub(
        r"[^a-z0-9]+",
        "",
        value.lower().replace("&", "and")
    )


def identify(name):
    slug = compact(name)

    if slug in by_slug:
        return by_slug[slug]

    if slug.endswith("br") and slug[:-2] in by_slug:
        return by_slug[slug[:-2]]

    if slug + "br" in by_slug:
        return by_slug[slug + "br"]

    return None


def safe_url(value, tracking=False):
    try:
        url = urlparse(str(value or "").strip())

        if (
            url.scheme != "https"
            or not url.netloc
            or url.username
            or url.password
        ):
            return ""

        if tracking and (
            url.hostname or ""
        ).lower() not in (
            "awin1.com",
            "www.awin1.com",
            "awin.com",
            "www.awin.com",
        ):
            return ""

        return url.geturl()

    except (ValueError, TypeError):
        return ""


def logo_https(value):
    try:
        raw = str(value or "").strip()
        url = urlsplit(raw)

        if url.scheme not in ("https", "http"):
            return ""

        if not url.hostname:
            return ""

        if url.username or url.password:
            return ""

        return urlunsplit((
            "https",
            url.netloc,
            url.path,
            url.query,
            ""
        ))

    except (ValueError, TypeError):
        return ""


def loja_dominio(programme):
    urls = [programme.get("displayUrl") or ""]

    for item in programme.get("validDomains") or []:
        if isinstance(item, dict):
            urls.append(item.get("domain") or "")
        elif isinstance(item, str):
            urls.append(item)

    for raw in urls:
        try:
            value = str(raw).strip()
            url = urlsplit(
                value if "://" in value
                else "https://" + value
            )

            host = (
                (url.hostname or "")
                .lower()
                .removeprefix("www.")
            )

            if (
                host
                and "." in host
                and all(
                    c.isalnum() or c in ".-"
                    for c in host
                )
            ):
                if not host.endswith((
                    "awin.com",
                    "awin1.com"
                )):
                    return host

        except ValueError:
            continue

    return ""


def money(raw):
    if raw is None:
        return None

    value = (
        str(raw)
        .strip()
        .replace("R$", "")
        .replace(" ", "")
    )

    if not value:
        return None

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = (
                value.replace(".", "")
                .replace(",", ".")
            )
        else:
            value = value.replace(",", "")

    elif "," in value:
        value = value.replace(",", ".")

    try:
        number = Decimal(value)

        if not number.is_finite() or number <= 0:
            return None

        return float(
            number.quantize(Decimal("0.01"))
        )

    except InvalidOperation:
        return None


def request(
    url,
    method="GET",
    token=None,
    body=None,
    timeout=45
):
    headers = {
        "User-Agent": "SolGarimpaPublisherFeed/1.0",
        "Accept": "application/json,text/csv,*/*",
    }

    if token:
        headers["Authorization"] = "Bearer " + token

    if body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method
    )

    return urllib.request.urlopen(
        req,
        timeout=timeout
    )


def read_csv_stream(url, max_rows=None):
    with request(url, timeout=120) as response:
        buffered = io.BufferedReader(response)

        if buffered.peek(2)[:2] == b"\x1f\x8b":
            fileobj = gzip.GzipFile(
                fileobj=buffered
            )
        else:
            fileobj = buffered

        txt = io.TextIOWrapper(
            fileobj,
            encoding="utf-8-sig",
            errors="replace",
            newline=""
        )

        reader = csv.DictReader(txt)

        if not reader.fieldnames:
            return

        for index, row in enumerate(reader):
            if (
                max_rows is not None
                and index >= max_rows
            ):
                break

            yield {
                re.sub(
                    r"[^a-z0-9]+",
                    "_",
                    str(key).strip().lower()
                ).strip("_"): (val or "")
                for key, val in row.items()
                if key is not None
            }


# ==========================================
# PARCEIROS APROVADOS AUTOMATICAMENTE
# ==========================================

def get_branding(token):
    """Busca os programas aderidos na API oficial Awin.

    Apenas relationship=joined.
    Não inclui inscrições pendentes ou rejeitadas.
    Em caso de falha, preserva o catálogo anterior.
    """

    url = (
        f"https://api.awin.com/publishers/"
        f"{PUBLISHER_ID}/programmes"
        f"?relationship=joined"
    )

    with request(
        url,
        token=token,
        timeout=35
    ) as response:
        programmes = json.load(response)

    if isinstance(programmes, dict):
        programmes = (
            programmes.get("programmes")
            or programmes.get("results")
            or programmes.get("data")
            or []
        )

    if not isinstance(programmes, list):
        raise RuntimeError(
            "Lista de programas Awin em formato inesperado"
        )

    metadata = {}

    for programme in programmes:
        if not isinstance(programme, dict):
            continue

        name = str(
            programme.get("name") or ""
        ).strip()

        if not name:
            continue

        status = str(
            programme.get("status") or ""
        ).strip().lower()

        if status in (
            "inactive",
            "disabled",
            "terminated",
            "closed",
            "suspended"
        ):
            continue

        metadata[name] = {
            "logo_url": logo_https(
                programme.get("logoUrl")
            ),
            "dominio_loja": loja_dominio(
                programme
            ),
            "advertiser_id": (
                programme.get("id")
                or programme.get("advertiserId")
            ),
        }

    if not metadata:
        raise RuntimeError(
            "Awin não retornou programas aderidos; "
            "catálogo anterior preservado"
        )

    print(
        f"Awin: {len(metadata)} programas "
        f"aderidos reconhecidos"
    )

    return metadata


def configurar_lojas_aprovadas(branding):
    """Inclui dinamicamente todos os parceiros aprovados."""

    global STORES, by_slug

    STORES = [
        (name, True)
        for name in sorted(
            branding,
            key=str.casefold
        )
    ]

    by_slug = {
        compact(name): name
        for name, _ in STORES
    }

    for alias, nome in ALIASES.items():
        if nome in branding:
            by_slug[alias] = nome

    print(
        f"Awin: {len(STORES)} parceiros "
        f"aprovados habilitados no catálogo"
    )


# ==========================================
# PRODUTOS E DISPONIBILIDADE
# ==========================================

def latest_is_valid(row):
    for field in (
        "in_stock",
        "is_for_sale",
        "stock_status"
    ):
        status = str(
            row.get(field) or ""
        ).strip().lower()

        if status in (
            "false",
            "no",
            "não",
            "nao",
            "0",
            "out of stock",
            "outofstock",
            "unavailable",
            "esgotado"
        ):
            return False

    end_text = str(
        row.get("valid_to") or ""
    ).strip()

    if end_text:
        try:
            end = dt.datetime.fromisoformat(
                end_text.replace(
                    "Z", "+00:00"
                )
            )

            if end.tzinfo is None:
                end = end.replace(tzinfo=UTC)

            if end < dt.datetime.now(UTC):
                return False

        except ValueError:
            pass

    return True


def product_candidate(row, store):
    currency = str(
        row.get("currency") or ""
    ).strip().upper()

    if currency != "BRL":
        return None

    if not latest_is_valid(row):
        return None

    title = str(
        row.get("product_name")
        or row.get("title")
        or ""
    ).strip()

    image = safe_url(
        row.get("aw_image_url")
        or row.get("merchant_image_url")
        or row.get("large_image")
        or row.get("merchant_thumb_url")
    )

    link = safe_url(
        row.get("aw_deep_link"),
        tracking=True
    )

    price = money(
        row.get("search_price")
    )

    if not (
        title
        and image
        and link
        and price
    ):
        return None

    old = money(
        row.get("product_price_old")
        or row.get("rrp_price")
        or row.get("store_price")
    )

    if old is not None and old <= price:
        old = None

    discount = (
        int(round(
            100 * (old - price) / old
        ))
        if old else 0
    )

    return {
        "id": "p-" + compact(
            row.get("aw_product_id")
            or row.get("merchant_product_id")
            or link
        )[-100:],
        "loja": store,
        "tipo": "produto",
        "titulo": title[:180],
        "imagem": image,
        "preco": price,
        "preco_anterior": old,
        "desconto_pct": discount,
        "link": link,
        "cupom": None,
        "validade": None,
        "descricao": "",
        "termos": ""
    }


def product_feeds(api_key):
    """Obtém os feeds oficiais sem divulgar as credenciais."""

    urls = [
        (
            "https://ui.awin.com/"
            "productdata-darwin-download/"
            f"publisher/{PUBLISHER_ID}/"
            f"{api_key}/1/feedList"
        ),
        (
            "https://productdata.awin.com/"
            f"datafeed/list/apikey/{api_key}"
        )
    ]

    for index, url in enumerate(urls, 1):
        result = defaultdict(list)

        try:
            valid_csv = False

            for row in read_csv_stream(
                url,
                max_rows=5000
            ):
                if not valid_csv:
                    if not (
                        row.get("advertiser_name")
                        or row.get("advertisername")
                    ):
                        raise ValueError(
                            "Cabeçalho do Feed List inválido"
                        )

                    valid_csv = True

                store = identify(
                    row.get("advertiser_name")
                    or row.get("advertisername")
                )

                if not store:
                    continue

                status = compact(
                    row.get("membership_status")
                    or row.get("membershipstatus")
                )

                if (
                    status
                    and status not in (
                        "joined",
                        "approved",
                        "active"
                    )
                ):
                    continue

                feed_url = safe_url(
                    row.get("url")
                    or row.get("download_url")
                    or row.get("downloadurl")
                )

                parsed = urlparse(feed_url)
                host = (
                    parsed.hostname or ""
                ).lower()

                allowed = (
                    host in (
                        "datafeed.api.productserve.com",
                        "productdata.awin.com"
                    )
                    or (
                        host == "ui.awin.com"
                        and parsed.path.startswith(
                            "/productdata-darwin-download/"
                        )
                    )
                )

                if (
                    allowed
                    and feed_url not in result[store]
                ):
                    result[store].append(
                        feed_url
                    )

            if not valid_csv:
                raise ValueError(
                    "Feed List vazio ou inválido"
                )

            print(
                f"Awin: fonte {index}, "
                f"{len(result)} programas com feed"
            )

            return result

        except Exception as exc:
            print(
                f"Awin: consulta do Feed List "
                f"{index} falhou "
                f"({type(exc).__name__})",
                file=sys.stderr
            )

    raise RuntimeError(
        "Nenhuma fonte oficial de feed Awin respondeu"
    )


def get_products(api_key):
    feeds = product_feeds(api_key)

    products = {}
    report = {}

    for store, _ in STORES:
        candidates = []

        for url in feeds.get(store, [])[:1]:
            try:
                for row in read_csv_stream(
                    url,
                    max_rows=100000
                ):
                    item = product_candidate(
                        row,
                        store
                    )

                    if item:
                        candidates.append(item)

            except Exception as exc:
                print(
                    f"Awin: falha de feed de {store} "
                    f"({type(exc).__name__})",
                    file=sys.stderr
                )

        dedup = []
        used = set()

        for item in sorted(
            candidates,
            key=lambda p: (
                -p["desconto_pct"],
                p["preco"]
            )
        ):
            if item["link"] in used:
                continue

            used.add(item["link"])
            dedup.append(item)

            if len(dedup) >= PRODUCTS_PER_STORE:
                break

        products[store] = dedup

        report[store] = {
            "feed_listado": bool(
                feeds.get(store)
            ),
            "produtos_validos": len(dedup)
        }

    return products, report


# ==========================================
# CUPONS E PROMOCOES
# ==========================================

def parse_offer_date(value):
    try:
        return dt.datetime.fromisoformat(
            str(value).replace(
                "Z", "+00:00"
            )
        )

    except (ValueError, TypeError):
        return None


def unpack_offers(payload):
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in (
            "promotions",
            "offers",
            "results",
            "items",
            "data"
        ):
            records = payload.get(key)

            if isinstance(records, list):
                return records

            if isinstance(records, dict):
                for name in (
                    "promotions",
                    "offers",
                    "results",
                    "items"
                ):
                    if isinstance(
                        records.get(name),
                        list
                    ):
                        return records[name]

    raise ValueError(
        "API de promoções retornou formato inesperado"
    )


def offer_candidate(row):
    if not isinstance(row, dict):
        return None

    advertiser = (
        row.get("advertiser") or {}
    )

    if not isinstance(advertiser, dict):
        return None

    if advertiser.get("joined") is False:
        return None

    store = identify(
        advertiser.get("name") or ""
    )

    if not store:
        return None

    link = safe_url(
        row.get("urlTracking"),
        tracking=True
    )

    title = str(
        row.get("title") or ""
    ).strip()

    if not title or not link:
        return None

    expires = parse_offer_date(
        row.get("endDate")
    )

    if expires:
        if expires.tzinfo is None:
            expires = expires.replace(
                tzinfo=UTC
            )

        if expires < (
            dt.datetime.now(UTC)
            - dt.timedelta(days=1)
        ):
            return None

    voucher = row.get("voucher") or {}

    code = (
        voucher.get("code")
        if isinstance(voucher, dict)
        else None
    )

    return {
        "id": "o-" + str(
            row.get("promotionId")
            or compact(title)
        ),
        "loja": store,
        "tipo": (
            "cupom"
            if row.get("type") == "voucher"
            else "promocao"
        ),
        "titulo": title[:180],
        "imagem": None,
        "preco": None,
        "preco_anterior": None,
        "desconto_pct": None,
        "link": link,
        "cupom": (
            str(code).strip()
            if code else None
        ),
        "validade": (
            row.get("endDate") or None
        ),
        "descricao": str(
            row.get("description") or ""
        )[:240],
        "termos": str(
            row.get("terms") or ""
        )[:700]
    }


def get_offers(token):
    url = (
        f"https://api.awin.com/publisher/"
        f"{PUBLISHER_ID}/promotions"
    )

    offers = defaultdict(list)

    for page in range(1, 8):
        body = {
            "filters": {
                "membership": "joined",
                "regionCodes": ["BR"],
                "status": "active",
                "type": "all"
            },
            "pagination": {
                "page": page,
                "pageSize": 200
            }
        }

        with request(
            url,
            method="POST",
            token=token,
            body=body,
            timeout=40
        ) as response:
            received = unpack_offers(
                json.load(response)
            )

        for row in received:
            item = offer_candidate(row)

            if item:
                offers[
                    item["loja"]
                ].append(item)

        if len(received) < 200:
            break

    for store in offers:
        dedup = []
        seen = set()

        for item in offers[store]:
            key = (
                item["link"],
                item["titulo"]
            )

            if key in seen:
                continue

            seen.add(key)
            dedup.append(item)

            if len(dedup) >= OFFERS_PER_STORE:
                break

        offers[store] = dedup

    return offers


# ==========================================
# LINKS SOL GARIMPA
# ==========================================

def attach_sol_page(item):
    if (
        not item.get("link")
        or item.get("tipo") == "sem_oferta"
    ):
        return item

    name = unicodedata.normalize(
        "NFKD",
        str(
            item.get("titulo") or "oferta"
        )
    )

    name = "".join(
        x for x in name
        if not unicodedata.combining(x)
    )

    base = re.sub(
        r"[^a-z0-9]+",
        "-",
        name.lower()
    ).strip("-")[:58].strip("-")

    base = base or "oferta"

    digest = hashlib.sha256(
        (
            str(item["loja"])
            + "|"
            + str(item["id"])
            + "|"
            + item["link"]
        ).encode()
    ).hexdigest()[:12]

    item["slug"] = (
        f"{base}-{digest}"
    )

    item["url_sol_garimpa"] = (
        f"{SITE_URL}/oferta/"
        f"{item['slug']}"
    )

    return item


# ==========================================
# MENSAGENS WHATSAPP
# ==========================================

def whatsapp_message(item):
    if (
        item.get("tipo") == "sem_oferta"
        or not item.get("link")
    ):
        return None

    parts = [
        "🛍️ *OFERTA SOL GARIMPA*",
        f"🏬 *{item['loja']}*",
        f"✨ {item['titulo']}"
    ]

    if item.get("preco") is not None:
        price = (
            f"R$ {item['preco']:,.2f}"
            .replace(",", "#")
            .replace(".", ",")
            .replace("#", ".")
        )

        if item.get("preco_anterior"):
            old = (
                f"R$ {item['preco_anterior']:,.2f}"
                .replace(",", "#")
                .replace(".", ",")
                .replace("#", ".")
            )

            parts.append(
                f"💰 *{price}* (antes {old})"
            )
        else:
            parts.append(
                f"💰 *{price}*"
            )

    if item.get("cupom"):
        parts.append(
            f"🎟️ Cupom: *{item['cupom']}*"
        )

    if item.get("validade"):
        parts.append(
            "🗓️ Validade informada: "
            + str(item["validade"])[:10]
        )

    if item.get("descricao"):
        parts.append(
            str(item["descricao"])[:200]
        )

    if item.get("termos"):
        parts.append(
            "ℹ️ Condições: "
            + str(item["termos"])[:220]
        )

    parts += [
        (
            "👉 Confira na SOL GARIMPA: "
            + (
                item.get("url_sol_garimpa")
                or item["link"]
            )
        ),
        "⚠️ Preço e disponibilidade sujeitos à confirmação na loja.",
        "Publicidade • Link de afiliado SOL GARIMPA"
    ]

    return "\n".join(parts)


def salvar_texto(path, text):
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    tmp = path.with_suffix(
        path.suffix + ".tmp"
    )

    tmp.write_text(
        text,
        encoding="utf-8"
    )

    tmp.replace(path)


# ==========================================
# EXECUCAO PRINCIPAL
# ==========================================

def main():
    token = os.environ.get(
        "AWIN_PUBLISHER_TOKEN",
        ""
    ).strip()

    api_key = os.environ.get(
        "AWIN_DATAFEED_KEY",
        ""
    ).strip()

    if not token or not api_key:
        sys.exit(
            "Awin: configure AWIN_PUBLISHER_TOKEN "
            "e AWIN_DATAFEED_KEY no GitHub Secrets"
        )

    try:
        # Consulta parceiros efetivamente aprovados.

        branding = get_branding(token)

        configurar_lojas_aprovadas(
            branding
        )

        # Consulta ofertas e produtos.

        promos = get_offers(token)

        try:
            products, report = get_products(
                api_key
            )
        except RuntimeError as exc:
            # As duas fontes oficiais de Feed List podem ficar
            # temporariamente indisponiveis. Nao sobrescrever
            # um catalogo valido com dados vazios ou antigos.
            if str(exc) != (
                "Nenhuma fonte oficial de feed Awin respondeu"
            ):
                raise

            if not TARGET.is_file():
                raise

            previous = json.loads(
                TARGET.read_text(encoding="utf-8")
            )

            existing_cards = previous.get("cards", [])

            if (
                previous.get("fonte") != "Awin"
                or previous.get("publisher_id") != PUBLISHER_ID
                or not isinstance(existing_cards, list)
                or not any(
                    isinstance(card, dict)
                    and card.get("link")
                    and card.get("tipo") in (
                        "produto", "cupom", "promocao"
                    )
                    for card in existing_cards
                )
            ):
                raise RuntimeError(
                    "Feed Awin indisponivel e sem catalogo "
                    "anterior valido para preservar"
                ) from exc

            print(
                "::warning title=Feed Awin temporariamente "
                "indisponivel::As duas fontes de produtos "
                "falharam. Catalogo anterior preservado "
                "sem alterar sua data de atualizacao.",
                flush=True
            )
            return

        cards = []
        active = []

        for store, _ in STORES:
            selection = (
                promos.get(store, [])
                + products.get(store, [])
            )

            if selection:
                active.append(store)
                cards.extend(selection)

            else:
                cards.append({
                    "id": (
                        "s-" + compact(store)
                    ),
                    "loja": store,
                    "tipo": "sem_oferta",
                    "titulo": (
                        "Nenhuma oferta vigente "
                        "encontrada na fonte"
                    ),
                    "descricao": "",
                    "imagem": None,
                    "preco": None,
                    "preco_anterior": None,
                    "desconto_pct": None,
                    "link": None,
                    "cupom": None,
                    "validade": None,
                    "termos": ""
                })

        # Adiciona metadados oficiais.

        for card in cards:
            metadata = branding[
                card["loja"]
            ]

            card["logo_url"] = (
                metadata["logo_url"]
            )

            card["dominio_loja"] = (
                metadata["dominio_loja"]
            )

            attach_sol_page(card)

        now = dt.datetime.now(
            UTC
        ).isoformat(
            timespec="seconds"
        )

        advertisers = []

        for store, _ in STORES:
            advertisers.append({
                "nome": store,
                "advertiser_id": (
                    branding[store].get(
                        "advertiser_id"
                    )
                ),
                "possui_feed": (
                    report[store][
                        "feed_listado"
                    ]
                ),
                "logo_url": (
                    branding[store][
                        "logo_url"
                    ]
                ),
                "dominio_loja": (
                    branding[store][
                        "dominio_loja"
                    ]
                ),
                "ofertas_encontradas": sum(
                    1
                    for item in cards
                    if (
                        item["loja"] == store
                        and item["tipo"]
                        != "sem_oferta"
                    )
                )
            })

        # Compara com o catalogo anterior.

        old_names = set()

        if TARGET.exists():
            try:
                previous = json.loads(
                    TARGET.read_text(
                        encoding="utf-8"
                    )
                )

                old_names = {
                    str(p.get("nome"))
                    for p in previous.get(
                        "anunciantes", []
                    )
                    if (
                        isinstance(p, dict)
                        and p.get("nome")
                    )
                }

            except (
                ValueError,
                OSError,
                TypeError
            ):
                pass

        new_names = [
            name
            for name, _ in STORES
            if name not in old_names
        ]

        # Monta catalogo JSON.

        catalog = {
            "fonte": "Awin",
            "publisher_id": PUBLISHER_ID,
            "atualizado_em": now,
            "anunciantes": advertisers,
            "status": {
                "anunciantes_listados": (
                    len(STORES)
                ),
                "com_ofertas": (
                    len(active)
                ),
                "com_feed": sum(
                    1
                    for info in report.values()
                    if info["feed_listado"]
                )
            },
            "cards": cards
        }

        salvar_texto(
            TARGET,
            json.dumps(
                catalog,
                ensure_ascii=False,
                separators=(",", ":")
            )
        )

        # Prepara mensagens para WhatsApp.

        queue = []

        for card in cards:
            msg = whatsapp_message(
                card
            )

            if card.get("link") and msg:
                queue.append({
                    "id": card["id"],
                    "loja": card["loja"],
                    "link": card["link"],
                    "url_sol_garimpa": (
                        card["url_sol_garimpa"]
                    ),
                    "mensagem": msg,
                    "gerado_em": now
                })

        salvar_texto(
            TARGET.parent
            / "fila_whatsapp.json",
            json.dumps(
                {
                    "gerado_em": now,
                    "enviado": False,
                    "fila": queue
                },
                ensure_ascii=False,
                indent=2
            )
        )

        mensagens = (
            "\n\n"
            + (
                "\n\n"
                + "━" * 32
                + "\n\n"
            ).join(
                item["mensagem"]
                for item in queue
            )
        )

        salvar_texto(
            TARGET.parent
            / "mensagens_whatsapp.txt",
            mensagens
        )

        print(
            f"OK: {len(STORES)} aprovados, "
            f"{len(active)} com ofertas, "
            f"{len(cards)} cards."
        )

        print(
            f"Arquivo gerado: {TARGET}"
        )

        if new_names:
            print(
                "Novos programas no catálogo: "
                + ", ".join(new_names)
            )

    except Exception as exc:
        # Nao divulgar credenciais nos logs.

        message = (
            str(exc)
            .replace(
                token,
                "[SEGREDO]"
            )
            .replace(
                api_key,
                "[SEGREDO]"
            )
        )

        print(
            f"Erro ao atualizar Awin: "
            f"{type(exc).__name__}: "
            f"{message[:220]}",
            file=sys.stderr
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
