#!/usr/bin/env python3
"""SOL GARIMPA: vitrine AliExpress a partir da API oficial de afiliados.

Usa somente segredos de ambiente (GitHub Actions), sem gravar credenciais.
Nao usa wishlist privada nem cria links artificiais. Publica apenas itens
com URL promocional devolvida pela API para o Tracking ID configurado.
"""
import hashlib
import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "aliexpress" / "ofertas.json"
GATEWAY = "https://api-sg.aliexpress.com/sync"
KEYWORDS = ("organizador", "cozinha", "casa", "tecnologia", "beleza", "acessorios carro")
LIMIT = 120
USER_AGENT = "SolGarimpaCatalog/1.0"

def sign_top(parameters, secret):
    """Assinatura MD5 TOP para métodos aliexpress.affiliate.* do gateway /sync."""
    values = "".join(k + str(v) for k, v in sorted(parameters.items()) if v is not None)
    return hashlib.md5((secret + values + secret).encode("utf-8")).hexdigest().upper()

def request_api(method, extra, app_key, app_secret):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    params = {
        "method": method,
        "app_key": app_key,
        "timestamp": stamp,
        "format": "json",
        "v": "2.0",
        "sign_method": "md5",
        **extra,
    }
    params["sign"] = sign_top(params, app_secret)
    req = urllib.request.Request(
        GATEWAY,
        data=urllib.parse.urlencode(params).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25, context=ssl.create_default_context()) as response:
            data = json.loads(response.read(2_000_000).decode("utf-8"))
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        raise RuntimeError("Falha de rede ou resposta invalida do AliExpress") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Resposta da API sem objeto JSON")
    error = data.get("error_response")
    if isinstance(error, dict):
        raise RuntimeError("AliExpress API: " + str(error.get("sub_code") or error.get("code") or "erro"))
    root = data.get(method.replace(".", "_") + "_response", {})
    result = root.get("resp_result", {}) if isinstance(root, dict) else {}
    if not isinstance(result, dict) or str(result.get("resp_code")) != "200":
        raise RuntimeError("AliExpress retornou falha para " + method)
    return result.get("result") or {}

def safe_url(raw, host_suffixes):
    try:
        value = str(raw or "").strip()
        url = urllib.parse.urlsplit(value)
        host = (url.hostname or "").lower()
        if url.scheme not in ("https", "http") or not host or url.username or url.password:
            return ""
        if not any(host == h or host.endswith("." + h) for h in host_suffixes):
            return ""
        return urllib.parse.urlunsplit(("https", url.netloc, url.path, url.query, ""))
    except (TypeError, ValueError):
        return ""

def promotional_url(value):
    # So links promocionais AliExpress fornecidos pela API (nunca URL de vitrine Wix).
    return safe_url(value, ("s.click.aliexpress.com", "a.aliexpress.com"))

def image_url(value):
    return safe_url(value, ("alicdn.com", "aliexpress-media.com", "aliexpress.com"))

def product_url(value):
    url = safe_url(value, ("aliexpress.com",))
    return url if "/item/" in urllib.parse.urlsplit(url).path else ""

def link_for_product(raw, app_key, app_secret, tracking_id):
    detail = product_url(raw)
    if not detail:
        return ""
    result = request_api("aliexpress.affiliate.link.generate", {
        "promotion_link_type": "0",
        "source_values": detail,
        "tracking_id": tracking_id,
    }, app_key, app_secret)
    if not isinstance(result, dict) or str(result.get("tracking_id") or tracking_id) != tracking_id:
        return ""
    links = (result.get("promotion_links") or {}).get("promotion_link", [])
    if isinstance(links, dict):
        links = [links]
    for entry in links:
        if isinstance(entry, dict) and entry.get("source_value") in (detail, raw):
            link = promotional_url(entry.get("promotion_link"))
            if link:
                return link
    return ""

def collect(app_key, app_secret, tracking_id):
    products, used, errors = [], set(), []
    for term in KEYWORDS:
        try:
            data = request_api("aliexpress.affiliate.product.query", {
                "keywords": term,
                "page_no": "1",
                "page_size": "25",
                "sort": "LAST_VOLUME_DESC",
                "ship_to_country": "BR",
                "target_currency": "BRL",
                "target_language": "PT",
                "tracking_id": tracking_id,
            }, app_key, app_secret)
            group = (data.get("products") or {}).get("product", []) if isinstance(data, dict) else []
            if isinstance(group, dict):
                group = [group]
            print("Busca", term, "-", len(group), "produtos retornados")
        except RuntimeError as exc:
            errors.append(term)
            print("Aviso: consulta nao disponivel para", term, "-", str(exc))
            continue
        for obj in group:
            if not isinstance(obj, dict):
                continue
            pid = str(obj.get("product_id") or "").strip()
            title = " ".join(str(obj.get("product_title") or "").split())[:180]
            photo = image_url(obj.get("product_main_image_url"))
            if not pid.isdigit() or pid in used or not title or not photo:
                continue
            url = promotional_url(obj.get("promotion_link"))
            if not url:
                try:
                    url = link_for_product(obj.get("product_detail_url"), app_key, app_secret, tracking_id)
                except RuntimeError:
                    url = ""
            if not url:
                continue
            item = {"id": pid, "nome": title, "imagem": photo, "link": url, "loja": "aliexpress"}
            currency = str(obj.get("target_sale_price_currency") or "")
            price = str(obj.get("target_sale_price") or "")
            try:
                value = float(price)
                if currency == "BRL" and 0 < value < 1_000_000:
                    item["preco"] = round(value, 2)
                    item["moeda"] = "BRL"
            except ValueError:
                pass
            products.append(item)
            used.add(pid)
            if len(products) >= LIMIT:
                break
        if len(products) >= LIMIT:
            break
    if not products:
        raise RuntimeError(
            "Sem produtos com link comissionado verificavel; "
            "catalogo existente preservado. Consultas com falha: " + ",".join(errors)
        )
    return products, errors

def main():
    credentials = {k: os.environ.get(k, "").strip() for k in (
        "ALIEXPRESS_APP_KEY", "ALIEXPRESS_APP_SECRET", "ALIEXPRESS_TRACKING_ID"
    )}
    if not all(credentials.values()):
        raise SystemExit("Faltam credenciais nos Secrets do GitHub")
    items, errors = collect(
        credentials["ALIEXPRESS_APP_KEY"],
        credentials["ALIEXPRESS_APP_SECRET"],
        credentials["ALIEXPRESS_TRACKING_ID"],
    )
    catalog = {
        "fonte": "AliExpress Affiliates API",
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
        "total": len(items),
        "status": "ok" if not errors else "parcial",
        "produtos": items,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    print("Catalogo AliExpress preparado com", len(items), "produtos rastreaveis.")

if __name__ == "__main__":
    main()
