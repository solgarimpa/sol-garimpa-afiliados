#!/usr/bin/env python3
"""Segunda camada de fontes oficiais para parceiros sem feed da SOL GARIMPA.

Rakuten: links de texto e banners fornecidos pela Link Locator API.
Awin: links de visita a loja fornecidos pela Link Builder API.
Nenhum preco, desconto, cupom ou URL de rastreamento e inventado.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import unescape
import json
import os
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET


def https_url(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return None
    except ValueError:
        return None
    return value


def _field(element, field):
    for child in element:
        if child.tag.rsplit("}", 1)[-1].lower() == field.lower():
            return (child.text or "").strip()
    return ""


def _date(value):
    value = str(value or "").strip()
    if not value:
        return None
    for fmt in ("%m%d%Y", "%m/%d/%Y", "%Y-%m-%d", "%Y%m%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None
                else parsed.astimezone(timezone.utc))
    except ValueError:
        return None


def _clean_title(value):
    plain = unescape(re.sub(r"<[^>]*>", " ", str(value or "")))
    return re.sub(r"\s+", " ", plain).strip()[:260]


def rakuten_creatives(token, partner, request_fn, safe_id_fn, *, now=None):
    """Retorna criativos oficiais com clickURL; nao converte paginas em descontos.

    request_fn e a funcao autenticada e limitada por taxa de sync_rakuten.py.
    Erros individuais sao coletados, sem apagar produtos ja existentes.
    """
    now = now or datetime.now(timezone.utc)
    mid = str(partner["mid"])
    max_cards = max(1, min(80, int(os.getenv("RAKUTEN_CREATIVE_CARDS_PER_STORE", "20"))))
    max_pages = max(1, min(4, int(os.getenv("RAKUTEN_CREATIVE_PAGES", "2"))))
    cards = {}
    warnings = []
    for kind, operation in (("texto", "getTextLinks"), ("banner", "getBannerLinks")):
        for page in range(1, max_pages + 1):
            suffix = (f"{mid}/-1///-1/{page}" if kind == "texto"
                      else f"{mid}/-1///-1/-1/{page}")
            path = f"/linklocator/1.0?{operation}/{suffix}"
            try:
                root = ET.fromstring(request_fn(path, token))
                records = root.findall(".//{*}return")
                if root.tag.rsplit("}", 1)[-1].lower() == "return":
                    records = [root]
                # Falhas declaradas pelo XML nao sao uma lista vazia de ofertas.
                faults = root.findall(".//{*}Fault") + root.findall(".//{*}fault")
                if faults:
                    raise ValueError("Link Locator retornou falha")
            except (ET.ParseError, ValueError, RuntimeError, OSError) as exc:
                warnings.append(f"{partner['loja']}: Link Locator {kind}: {type(exc).__name__}")
                break
            for item in records:
                item_mid = _field(item, "mid")
                if item_mid and item_mid != mid:
                    continue
                url = https_url(_field(item, "clickURL"))
                title = _clean_title(
                    _field(item, "textDisplay") or _field(item, "linkName")
                    or _field(item, "categoryName")
                )
                if not url or not title:
                    continue
                start_raw = _field(item, "startDate")
                end_raw = _field(item, "endDate")
                start, end = _date(start_raw), _date(end_raw)
                if (start_raw and start is None) or (end_raw and end is None):
                    continue
                if (start and start > now) or (end and end < now):
                    continue
                card_id = safe_id_fn("ll", mid, _field(item, "linkID"), url)
                cards[card_id] = {
                    "id": card_id,
                    "tipo": "promocao",
                    "loja": partner["loja"],
                    "mid": mid,
                    "titulo": title,
                    "imagem": https_url(_field(item, "imgURL") or _field(item, "iconURL")),
                    "preco": None,
                    "preco_anterior": None,
                    "moeda": None,
                    "link": url,
                    "descricao": "Material oficial divulgado pela loja parceira. Consulte as condicoes na loja.",
                    "categoria": _field(item, "categoryName")[:80] or "Links oficiais",
                    "validade": end.isoformat() if end else None,
                    "origem": "rakuten_link_locator",
                }
                if len(cards) >= max_cards:
                    break
            if len(cards) >= max_cards or not records:
                break
        if len(cards) >= max_cards:
            break
    return list(cards.values()), warnings


def awin_store_links(token, partners, request_fn, publisher_id, safe_tracking_url):
    """Gera links de visita a loja para anunciantes joined sem ofertas.

    Usa landing page padrao do anunciante. Resultado NAO e um produto ou cupom.
    O retorno e um dicionario {nome_da_loja: link_gerado_pela_awin}.
    """
    approved = []
    for store, advertiser_id in partners:
        try:
            advertiser_id = int(advertiser_id)
        except (TypeError, ValueError):
            continue
        if advertiser_id > 0:
            approved.append((store, advertiser_id))
    links = {}
    url = f"https://api.awin.com/publishers/{publisher_id}/linkbuilder/generate-batch"
    for offset in range(0, len(approved), 100):
        chunk = approved[offset:offset + 100]
        request_body = {"requests": [{"advertiserId": advertiser_id} for _, advertiser_id in chunk]}
        with request_fn(url, method="POST", token=token, body=request_body, timeout=40) as reply:
            payload = json.load(reply)
        responses = payload.get("responses", []) if isinstance(payload, dict) else []
        if not isinstance(responses, list):
            raise ValueError("Resposta inesperada da Awin Link Builder")
        by_id = {advertiser_id: store for store, advertiser_id in chunk}
        for index, entry in enumerate(responses):
            if not isinstance(entry, dict) or entry.get("status") != 200:
                continue
            body = entry.get("body")
            if not isinstance(body, dict):
                continue
            original = body.get("request")
            requested_id = original.get("advertiserId") if isinstance(original, dict) else None
            if requested_id is None and index < len(chunk):
                requested_id = chunk[index][1]
            try:
                store = by_id.get(int(requested_id))
            except (TypeError, ValueError):
                continue
            link = safe_tracking_url(body.get("url"), tracking=True)
            if store and link:
                links[store] = link
    return links
