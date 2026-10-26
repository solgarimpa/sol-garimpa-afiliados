#!/usr/bin/env python3
"""Sol Garimpa: Rakuten Advertising -> GitHub Pages.
Official API data only; does not fabricate offers or construct affiliate links.
Credentials stay in GitHub Actions Secrets. Stdlib Python 3.11+.

Docs:
https://developers.rakutenadvertising.com/guides/access_tokens
https://developers.rakutenadvertising.com/guides/partnerships
https://developers.rakutenadvertising.com/guides/product_search
https://developers.rakutenadvertising.com/guides/coupon
"""
from __future__ import annotations
import base64
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

API = 'https://api.linksynergy.com'
OUTPUT = Path(__file__).resolve().parents[1] / 'docs' / 'rakuten' / 'ofertas.json'
MAX_PAGES_PER_MID = max(1, min(200, int(os.getenv('RAKUTEN_PRODUCT_PAGES_PER_STORE', '5'))))
MAX_PAGES_COUPON = max(1, min(200, int(os.getenv('RAKUTEN_COUPON_PAGES', '20'))))
MAX_CARDS = max(100, min(100000, int(os.getenv('RAKUTEN_MAX_CARDS', '40000'))))
NOW = datetime.now(timezone.utc)
_NEXT_REQUEST_AT = 0.0  # Rakuten limits the consulted APIs to <=100 calls/min.


def log(message: str):
    print(message, flush=True)


def request(path: str, token: str | None, *, data: bytes | None = None,
            extra_headers: dict | None = None) -> bytes:
    assert path.startswith('/') and not path.startswith('//')
    headers = {'User-Agent': 'SolGarimpa-Rakuten/1.0', 'Accept': '*/*'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    headers.update(extra_headers or {})
    global _NEXT_REQUEST_AT
    for attempt in range(4):
        sleep_for = _NEXT_REQUEST_AT - time.monotonic()
        if sleep_for > 0:
            time.sleep(sleep_for)
        _NEXT_REQUEST_AT = time.monotonic() + 0.7  # approx. 85 calls/min
        req = urllib.request.Request(API + path, data=data, headers=headers,
                                     method='POST' if data is not None else 'GET')
        try:
            with urllib.request.urlopen(req, timeout=32) as response:
                content = response.read(24 * 1024 * 1024 + 1)
                if len(content) > 24 * 1024 * 1024:
                    raise RuntimeError('Resposta Rakuten maior que limite de segurança')
                return content
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                retry = min(12, 2 ** attempt + random.random())
                log(f'API retornou HTTP {e.code}; retentativa após {retry:.1f}s')
                time.sleep(retry)
                continue
            # Never include response body or Authorization header in logs.
            raise RuntimeError(f'Erro HTTP {e.code} em {path.split("?")[0]}') from None
        except (TimeoutError, urllib.error.URLError) as e:
            if attempt < 3:
                time.sleep(2 ** attempt + random.random())
                continue
            raise RuntimeError(f'Falha de rede em {path.split("?")[0]}: {type(e).__name__}') from None
    raise RuntimeError('Falha nas tentativas de consulta')


def make_access_token() -> str:
    account = os.getenv('RAKUTEN_ACCOUNT_ID', '').strip()
    client_id = os.getenv('RAKUTEN_CLIENT_ID', '').strip()
    client_secret = os.getenv('RAKUTEN_CLIENT_SECRET', '').strip()
    if not (account and client_id and client_secret):
        raise RuntimeError('Cadastre GitHub Secrets: RAKUTEN_ACCOUNT_ID, RAKUTEN_CLIENT_ID e RAKUTEN_CLIENT_SECRET.')
    token_key = base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()
    data = urllib.parse.urlencode({'scope': account}).encode()
    raw = request('/token', token_key, data=data,
                  extra_headers={'Content-Type': 'application/x-www-form-urlencoded',
                                 'Accept': 'application/json'})
    reply = json.loads(raw)
    access = reply.get('access_token')
    if not isinstance(access, str) or not access:
        raise RuntimeError('Rakuten não retornou access_token; confira a aplicação e o Account ID.')
    log('Token de acesso temporário obtido (valor não exibido).')
    return access


def parsedate(value: str | None):
    if not value:
        return None
    value = str(value).strip()
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        try:
            result = parsedate_to_datetime(value)
        except Exception:
            return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def clean_url(value: str | None):
    if not isinstance(value, str):
        return None
    value = value.strip()
    try:
        u = urllib.parse.urlsplit(value)
    except ValueError:
        return None
    # Rakuten links are never rebuilt/modified, only validated.
    if u.scheme != 'https' or not u.netloc or '@' in u.netloc:
        return None
    return value


def txt(e: ET.Element | None, path: str, default: str = '') -> str:
    if e is None:
        return default
    node = e.find(path)
    return (node.text or '').strip() if node is not None else default


def money(text: str):
    try:
        num = float((text or '').strip().replace(',', '.'))
        if num >= 0 and num < 10**12:
            return round(num, 2)
    except ValueError:
        pass
    return None


def safe_id(prefix: str, *bits) -> str:
    digest = hashlib.sha256('|'.join(map(str, bits)).encode('utf-8')).hexdigest()[:18]
    return f'{prefix}-{digest}'


def get_partnerships(token: str) -> list[dict]:
    # Network is intentionally unfiltered: all accepted partners, not only Brazil.
    approved = {}
    page = 1
    while page <= 200:
        params = urllib.parse.urlencode({'partner_status': 'active',
                                         'advertiser_status': 'active',
                                         'limit': 200, 'page': page})
        response = json.loads(request(f'/v1/partnerships?{params}', token))
        partnerships = response.get('partnerships') or []
        if not isinstance(partnerships, list):
            raise RuntimeError('Formato inesperado na Partnerships API')
        for p in partnerships:
            advertiser = p.get('advertiser') or {}
            if str(p.get('status', '')).lower() != 'active':
                continue
            if str(advertiser.get('status', '')).lower() != 'active':
                continue
            mid = str(advertiser.get('id', '')).strip()
            if not mid.isdigit():
                continue
            approved[mid] = {
                'mid': mid, 'loja': str(advertiser.get('name') or f'Loja {mid}').strip(),
                'network': advertiser.get('network'),
            }
        total = (response.get('metadata') or response.get('_metadata') or {}).get('total')
        log(f'Parcerias ativas: página {page}, {len(partnerships)} registros recebidos.')
        if not partnerships or len(partnerships) < 200 or (isinstance(total, int) and page * 200 >= total):
            break
        page += 1
    if page >= 200 and len(partnerships) == 200:
        raise RuntimeError('Paginação de parceiros excedeu 200 páginas; coleta incompleta.')
    return sorted(approved.values(), key=lambda a: a['loja'].casefold())


def product_from_xml(el: ET.Element, partner: dict) -> dict | None:
    title = txt(el, 'productname')
    raw_url = txt(el, 'linkurl')
    link = clean_url(raw_url)
    image = clean_url(txt(el, 'imageurl'))
    if not title or not link:
        return None
    retail_el = el.find('price')
    sale_el = el.find('saleprice')
    retail = money(retail_el.text or '') if retail_el is not None else None
    sale = money(sale_el.text or '') if sale_el is not None else None
    currency = (sale_el.get('currency') if sale_el is not None else None) or (
        retail_el.get('currency') if retail_el is not None else 'BRL')
    # Never label a product as discounted unless price and saleprice prove it.
    price = sale if sale is not None else retail
    previous = retail if sale is not None and retail is not None and retail > sale else None
    mid = txt(el, 'mid', partner['mid'])
    store = txt(el, 'merchantname', partner['loja']) or partner['loja']
    # ProductSearch links are generated by Rakuten for this authenticated publisher.
    return {
        'id': safe_id('p', mid, txt(el, 'linkid'), txt(el, 'sku'), link),
        'tipo': 'produto', 'loja': store, 'mid': mid, 'titulo': title[:260],
        'imagem': image, 'preco': price, 'preco_anterior': previous,
        'moeda': str(currency or 'BRL').upper(), 'link': link,
        'descricao': txt(el, 'description/short')[:320],
        'categoria': txt(el, 'category/primary')[:80],
        'validade': None,
    }


def fetch_products(token: str, partner: dict):
    products = {}
    mid = partner['mid']
    for page in range(1, MAX_PAGES_PER_MID + 1):
        params = urllib.parse.urlencode({'mid': mid, 'max': 100, 'pagenumber': page})
        raw = request(f'/productsearch/1.0?{params}', token)
        root = ET.fromstring(raw)
        xml_items = root.findall('.//item')
        total_pages = int(txt(root, './/TotalPages', '0') or 0)
        for el in xml_items:
            obj = product_from_xml(el, partner)
            if obj:
                products[obj['id']] = obj
        if not xml_items or page >= total_pages:
            break
        time.sleep(.08)
    return list(products.values())


def coupon_from_xml(el: ET.Element, partners: dict) -> dict | None:
    mid = txt(el, 'advertiserid')
    if mid not in partners:
        return None
    title = txt(el, 'offerdescription')
    link = clean_url(txt(el, 'clickurl'))
    if not title or not link:
        return None
    start = parsedate(txt(el, 'offerstartdate'))
    end = parsedate(txt(el, 'offerenddate'))
    if (start and start > NOW) or (end and end < NOW):
        return None
    store = partners[mid]['loja']
    return {
        'id': safe_id('c', mid, link, title), 'tipo': 'cupom',
        'loja': store, 'mid': mid, 'titulo': title[:260],
        'imagem': None, 'preco': None, 'preco_anterior': None,
        'moeda': None, 'link': link, 'descricao': '',
        'categoria': 'Cupons e promoções',
        'validade': end.isoformat() if end else None,
    }


def fetch_coupons(token: str, partners: list[dict]):
    approved = {p['mid']:p for p in partners}
    coupons = {}
    for page in range(1, MAX_PAGES_COUPON+1):
        params = urllib.parse.urlencode({'resultsperpage': 500, 'pagenumber': page})
        root = ET.fromstring(request(f'/coupon/1.0?{params}', token))
        links = root.findall('.//link')
        total_pages = int(txt(root, './/TotalPages', '0') or 0)
        for el in links:
            coupon = coupon_from_xml(el, approved)
            if coupon:
                coupons[coupon['id']] = coupon
        if not links or page >= total_pages:
            break
        time.sleep(.08)
    return list(coupons.values())


def balanced(items: list[dict]) -> list[dict]:
    # Interleave merchants to keep every approved merchant visible in the slider.
    stores = defaultdict(list)
    for obj in items:
        stores[obj['mid']].append(obj)
    for pool in stores.values():
        # Newly started active partner's newest products appear in different positions per run.
        random.shuffle(pool)
    # start merchant order varies between refreshes
    mids = list(stores)
    random.shuffle(mids)
    result = []
    while mids and len(result) < MAX_CARDS:
        remaining = []
        for mid in mids:
            if len(result) >= MAX_CARDS:
                break
            result.append(stores[mid].pop())
            if stores[mid]:
                remaining.append(mid)
        mids = remaining
    return result


def build_catalog(partners: list[dict], cards: list[dict], errors: list[str]):
    products = [i for i in cards if i['tipo']=='produto']
    coupons = [i for i in cards if i['tipo']=='cupom']
    counts = defaultdict(lambda: {'produtos':0,'cupons':0})
    for item in cards:
        counts[item['mid']]['produtos' if item['tipo']=='produto' else 'cupons'] += 1
    return {
        'rede': 'Rakuten Advertising', 'atualizado_em': NOW.isoformat(),
        'fonte': 'APIs oficiais Rakuten Advertising',
        'estatisticas': {'parceiros_ativos': len(partners), 'produtos': len(products),
                         'cupons': len(coupons), 'ofertas_exibidas':len(cards)},
        'limites_coleta': {'paginas_produtos_por_parceiro': MAX_PAGES_PER_MID,
                          'paginas_cupons': MAX_PAGES_COUPON,
                          'limite_cartoes': MAX_CARDS},
        'avisos': errors[:100],
        'parceiros': [{**p, **counts[p['mid']]} for p in partners],
        'cards': cards,
    }


def main():
    token = make_access_token()
    partners = get_partnerships(token)
    log(f'Total de parceiros ativos identificados: {len(partners)}')
    allcards, errors = [], []
    ok_product_requests = 0
    for idx, partner in enumerate(partners, start=1):
        try:
            items = fetch_products(token, partner)
            ok_product_requests += 1
            allcards.extend(items)
            log(f'[{idx}/{len(partners)}] {partner["loja"]}: {len(items)} produtos')
        except (ET.ParseError, ValueError, RuntimeError) as e:
            errors.append(f'Sem consulta de produtos para {partner["loja"]} ({type(e).__name__})')
            log(f'[{idx}/{len(partners)}] {partner["loja"]}: erro de produto ({type(e).__name__})')
    coupons_ok = False
    try:
        items = fetch_coupons(token, partners)
        allcards.extend(items)
        coupons_ok = True
        log(f'Cupons e promoções encontrados: {len(items)}')
    except (ET.ParseError, ValueError, RuntimeError) as e:
        errors.append(f'Consulta de cupons falhou ({type(e).__name__})')
        log(f'Falha nos cupons ({type(e).__name__})')
    if partners and not ok_product_requests and not coupons_ok:
        raise RuntimeError('Consultas de produto e cupom falharam; preservado o catálogo anterior.')
    # No partner found is valid only if the Partnerships API succeeded.
    unique = {card['id']:card for card in allcards}
    final = balanced(list(unique.values()))
    output = build_catalog(partners, final, errors)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUTPUT.with_suffix('.tmp')
    temp.write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf8')
    temp.replace(OUTPUT)
    log(f'Gerado: {OUTPUT}; parceiros {len(partners)}, cards {len(final)}, avisos {len(errors)}')


if __name__ == '__main__':
    try:
        main()
    except Exception as ex:
        print(f'Falha na sincronização Rakuten: {ex}', file=sys.stderr)
        sys.exit(1)
