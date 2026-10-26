#!/usr/bin/env python3
"""SOL GARIMPA — Awin official Product Feed List + Publisher Offers API.
No manual downloads, no Wix CMS. Generates ONLY approved affiliate links.
Python 3.11+ standard library. Scheduled via GitHub Actions.
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
import urllib.request
import urllib.error
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
from pathlib import Path

PUBLISHER_ID = 3110826
UTC = dt.timezone.utc
STORES = [
    ('Afiliados Galícia Educação', True), ('Clovis Calçados BR', True),
    ('Earfun, Inc', True), ('Eotica BR', True), ('Eurorelogios BR', True),
    ('Farmácias Indiana BR', False), ('Fut Fanatics BR', True),
    ('Havaianas BR', False), ('Kabum BR', True), ('LG BR', True),
    ('Lego BR', True), ('Mizuno BR', True), ('Nike BR', True),
    ('Polishop BR', True), ('Posthaus BR', True), ("Sam's Club BR", False),
    ('Shark-Ninja BR', True), ('Soldiers Nutrition BR', True),
    ('Stanley BR', True), ('Technos BR', True), ('Tia Sônia BR', False),
    ('Under Armour BR', False),
]
PRODUCTS_PER_STORE = 40
OFFERS_PER_STORE = 5
MIN_DISCOUNT = Decimal('0')
TARGET = Path(__file__).resolve().parents[1] / 'docs' / 'ofertas.json'
SITE_URL = 'https://www.ofertaspravc.com.br'


def compact(s):
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub('[^a-z0-9]+', '', s.lower().replace('&', 'and'))

ALIASES = {
    'kabum': 'Kabum BR', 'kabumbr': 'Kabum BR', 'kabumcombr': 'Kabum BR',
    'nikebr': 'Nike BR', 'nike': 'Nike BR',
    'cloviscalcados': 'Clovis Calçados BR',
    'farmaciasindiana': 'Farmácias Indiana BR',
    'sharkninja': 'Shark-Ninja BR', 'earfun': 'Earfun, Inc',
    'galiciaeducacao': 'Afiliados Galícia Educação',
    'afiliadosgaliciaeducacao': 'Afiliados Galícia Educação',
    'eotica': 'Eotica BR', 'eurorelogios': 'Eurorelogios BR',
    'futfanatics': 'Fut Fanatics BR', 'havaianas': 'Havaianas BR',
    'lg': 'LG BR', 'lego': 'Lego BR', 'mizuno': 'Mizuno BR',
    'polishop': 'Polishop BR', 'posthaus': 'Posthaus BR',
    'samsclub': "Sam's Club BR", 'soldiersnutrition': 'Soldiers Nutrition BR',
    'stanley': 'Stanley BR', 'technos': 'Technos BR',
    'tiasonia': 'Tia Sônia BR', 'underarmour': 'Under Armour BR'
}
by_slug = {compact(n): n for n, _ in STORES}
by_slug.update(ALIASES)

def identify(name):
    s = compact(name)
    if s in by_slug: return by_slug[s]
    # Only conservative suffix handling, never guess unrelated advertiser.
    if s.endswith('br') and s[:-2] in by_slug: return by_slug[s[:-2]]
    return None


def safe_url(link, tracking=False):
    try:
        u = urlparse(str(link or '').strip())
        if u.scheme != 'https' or not u.netloc or u.username or u.password:
            return ''
        host = (u.hostname or '').lower()
        if tracking and host not in ('awin1.com', 'www.awin1.com', 'awin.com', 'www.awin.com'):
            return ''
        return u.geturl()
    except (ValueError, TypeError): return ''


def money(raw):
    if raw is None: return None
    s = str(raw).strip().replace('R$', '').replace(' ', '')
    if not s: return None
    # Simple locale normalization: 1.234,56 or 1,234.56 or 1234.56.
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.') if s.rfind(',') > s.rfind('.') else s.replace(',', '')
    elif ',' in s: s = s.replace(',', '.')
    try:
        d = Decimal(s)
        if not d.is_finite() or d <= 0: return None
        return float(d.quantize(Decimal('0.01')))
    except InvalidOperation: return None


def latest_is_valid(row):
    for field in ('in_stock', 'is_for_sale', 'stock_status'):
        v = str(row.get(field) or '').strip().lower()
        if v in ('false', 'no', 'não', 'nao', '0', 'out of stock', 'outofstock', 'unavailable', 'esgotado'):
            return False
    valid_to = (row.get('valid_to') or '').strip()
    if valid_to:
        try:
            end = dt.datetime.fromisoformat(valid_to.replace('Z', '+00:00'))
            if end.tzinfo is None: end = end.replace(tzinfo=UTC)
            if end < dt.datetime.now(UTC): return False
        except ValueError: pass
    return True


def request(url, method='GET', token=None, body=None, timeout=45):
    headers = {'User-Agent': 'SolGarimpaPublisherFeed/1.0', 'Accept': 'application/json,text/csv,*/*'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if body is not None:
        headers['Content-Type'] = 'application/json'
        body = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    return urllib.request.urlopen(req, timeout=timeout)


def read_csv_stream(url, max_rows=None):
    """CSV Awin em streaming, com detecção do gzip pelo conteúdo real."""
    with request(url, timeout=120) as response:
        buffered = io.BufferedReader(response)
        if buffered.peek(2)[:2] == b'\x1f\x8b':
            fileobj = gzip.GzipFile(fileobj=buffered)
        else:
            fileobj = buffered
        text_io = io.TextIOWrapper(fileobj, encoding='utf-8-sig', errors='replace', newline='')
        reader = csv.DictReader(text_io)
        if not reader.fieldnames: return
        for idx, row in enumerate(reader):
            if max_rows is not None and idx >= max_rows: break
            # Normaliza colunas do CSV sem alterar valores e URLs de afiliados.
            yield {re.sub(r'[^a-z0-9]+', '_', str(k).strip().lower()).strip('_'): (v or '')
                   for k, v in row.items() if k is not None}


def price_old(row):
    return money(row.get('product_price_old') or row.get('rrp_price') or row.get('store_price'))


def product_candidate(row, store):
    currency = (row.get('currency') or '').strip().upper()
    if currency != 'BRL' or not latest_is_valid(row): return None
    name = (row.get('product_name') or row.get('title') or '').strip()
    image = safe_url(row.get('aw_image_url') or row.get('merchant_image_url') or row.get('large_image') or row.get('merchant_thumb_url'))
    link = safe_url(row.get('aw_deep_link'), tracking=True)
    p = money(row.get('search_price'))
    if not (name and image and link and p): return None
    old = price_old(row)
    if old is not None and old <= p: old = None
    percent = int(round(100 * (old - p) / old)) if old else 0
    return {'id': 'p-' + compact(row.get('aw_product_id') or row.get('merchant_product_id') or link)[-100:],
            'loja': store, 'tipo': 'produto', 'titulo': name[:180],
            'imagem': image, 'preco': p, 'preco_anterior': old,
            'desconto_pct': percent, 'link': link, 'cupom': None,
            'validade': None, 'descricao': '', 'termos': ''}


def product_feeds(api_key):
    """Primeiro tenta lista Darwin (interface atual), depois o endpoint documentado.

    A chave é lida somente do ambiente e nunca é escrita nos arquivos publicados.
    """
    feed_list_urls = [
        f'https://ui.awin.com/productdata-darwin-download/publisher/{PUBLISHER_ID}/{api_key}/1/feedList',
        f'https://productdata.awin.com/datafeed/list/apikey/{api_key}',
    ]
    for source_num, list_url in enumerate(feed_list_urls, start=1):
        feeds = defaultdict(list)
        try:
            csv_valid = False
            for row in read_csv_stream(list_url, max_rows=5000):
                if not csv_valid:
                    # HTML de login e respostas não-CSV não são catálogos.
                    if not (row.get('advertiser_name') or row.get('advertisername')):
                        raise ValueError('Feed List não contém as colunas esperadas')
                    csv_valid = True
                store = identify(row.get('advertiser_name') or row.get('advertisername') or '')
                if not store or not dict(STORES)[store]: continue
                status = compact(row.get('membership_status') or row.get('membershipstatus') or '')
                if status and status not in ('joined', 'approved', 'active'): continue
                raw_url = safe_url(row.get('url') or row.get('download_url') or row.get('downloadurl'))
                parsed = urlparse(raw_url)
                host = (parsed.hostname or '').lower()
                host_ok = (host in ('datafeed.api.productserve.com', 'productdata.awin.com')
                           or (host == 'ui.awin.com' and parsed.path.startswith('/productdata-darwin-download/')))
                if host_ok and raw_url not in feeds[store]:
                    feeds[store].append(raw_url)
            if not csv_valid:
                raise ValueError('Lista de feeds vazia')
            print(f'Lista de produtos Awin: fonte {source_num}; {len(feeds)} anunciantes com feed')
            return feeds
        except Exception as err:
            # Não incluir URL nem exceção completa: podem conter a chave de download.
            print(f'Lista Awin fonte {source_num} indisponível ({type(err).__name__}); tentando alternativa',
                  file=sys.stderr)
    raise RuntimeError('Falha nas duas URLs oficiais de lista de produtos Awin')


def get_products(api_key):
    products, report = {}, {}
    feeds = product_feeds(api_key)
    for store, has_feed in STORES:
        if not has_feed: continue
        candidates = []
        for url in feeds.get(store, [])[:1]:
            try:
                for row in read_csv_stream(url, max_rows=100000):
                    obj = product_candidate(row, store)
                    if obj: candidates.append(obj)
            except Exception as e:
                print(f'Feed não processado: {store}: {type(e).__name__}', file=sys.stderr)
        seen = set()
        unique = []
        for obj in sorted(candidates, key=lambda p: (-p['desconto_pct'], p['preco'])):
            if obj['link'] in seen: continue
            seen.add(obj['link']); unique.append(obj)
            if len(unique) == PRODUCTS_PER_STORE: break
        products[store] = unique
        report[store] = {'feed_listado': bool(feeds.get(store)), 'produtos_validos': len(unique)}
    return products, report


def parse_offer_date(text):
    try:
        return dt.datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except (ValueError, TypeError): return None


def unpack_offers(payload):
    if isinstance(payload, list): return payload
    if not isinstance(payload, dict): raise ValueError('Formato de ofertas não reconhecido')
    for k in ('promotions', 'offers', 'results', 'items', 'data'):
        x = payload.get(k)
        if isinstance(x, list): return x
        if isinstance(x, dict):
            for kk in ('promotions', 'offers', 'results', 'items'):
                if isinstance(x.get(kk), list): return x[kk]
    raise ValueError('API retornou formato de ofertas inesperado')


def offer_candidate(row):
    if not isinstance(row, dict): return None
    a = row.get('advertiser') or {}
    if not isinstance(a, dict) or a.get('joined') is False: return None
    store = identify(a.get('name') or '')
    if not store: return None
    url = safe_url(row.get('urlTracking'), tracking=True)
    title = str(row.get('title') or '').strip()
    if not title or not url: return None
    expires = parse_offer_date(row.get('endDate'))
    if expires:
        if expires.tzinfo is None: expires = expires.replace(tzinfo=UTC)
        # Awin labels midnight endDate; API active filter is primary source of validity.
        if expires < dt.datetime.now(UTC) - dt.timedelta(days=1): return None
    voucher = row.get('voucher') or {}
    code = (voucher.get('code') if isinstance(voucher, dict) else None)
    code = str(code).strip() if code else None
    return {'id': 'o-' + str(row.get('promotionId') or compact(title)), 'loja': store,
            'tipo': 'cupom' if row.get('type') == 'voucher' else 'promocao',
            'titulo': title[:180], 'imagem': None, 'preco': None, 'preco_anterior': None,
            'desconto_pct': None, 'link': url, 'cupom': code, 'validade': row.get('endDate') or None,
            'descricao': str(row.get('description') or '')[:240],
            'termos': str(row.get('terms') or '')[:700]}


def get_offers(token):
    url = f'https://api.awin.com/publisher/{PUBLISHER_ID}/promotions'
    result = defaultdict(list)
    for page in range(1, 8):
        body = {'filters': {'membership': 'joined', 'regionCodes': ['BR'], 'status': 'active', 'type': 'all'},
                'pagination': {'page': page, 'pageSize': 200}}
        with request(url, method='POST', token=token, body=body, timeout=40) as response:
            raw = json.load(response)
        found = unpack_offers(raw)
        for row in found:
            item = offer_candidate(row)
            if item: result[item['loja']].append(item)
        if len(found) < 200: break
    for key in result:
        seen = set(); dedup = []
        for x in result[key]:
            if x['link'] in seen and x['titulo'] in [v['titulo'] for v in dedup]: continue
            seen.add(x['link']); dedup.append(x)
            if len(dedup) >= OFFERS_PER_STORE: break
        result[key] = dedup
    return result


def attach_sol_page(item):
    """Stable slug: product readable name + collision resistant ID, no CMS."""
    if not item.get('link') or item.get('tipo') == 'sem_oferta':
        return item
    name = unicodedata.normalize('NFKD', str(item.get('titulo') or 'oferta'))
    name = ''.join(x for x in name if not unicodedata.combining(x))
    base = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:58].strip('-') or 'oferta'
    digest = hashlib.sha256((str(item.get('loja'))+'|'+str(item['id'])+'|'+item['link']).encode()).hexdigest()[:12]
    item['slug'] = f'{base}-{digest}'
    item['url_sol_garimpa'] = f'{SITE_URL}/oferta/{item["slug"]}'
    return item


def whatsapp_message(item):
    if item.get('tipo') == 'sem_oferta' or not item.get('link'): return None
    parts = ["🛍️ *OFERTA SOL GARIMPA*", f"🏬 *{item['loja']}*", f"✨ {item['titulo']}"]
    if item.get('preco') is not None:
        price = f"R$ {item['preco']:,.2f}".replace(',', '#').replace('.', ',').replace('#', '.')
        if item.get('preco_anterior'):
            old = f"R$ {item['preco_anterior']:,.2f}".replace(',', '#').replace('.', ',').replace('#', '.')
            parts.append(f"💰 *{price}* (antes {old})")
        else: parts.append(f"💰 *{price}*")
    if item.get('cupom'): parts.append(f"🎟️ Cupom: *{item['cupom']}*")
    if item.get('validade'): parts.append(f"🗓️ Validade informada: {str(item['validade'])[:10]}")
    if item.get('descricao'): parts.append(str(item['descricao'])[:200])
    if item.get('termos'): parts.append('ℹ️ Condições: ' + str(item['termos'])[:220])
    parts += [f"👉 Confira na SOL GARIMPA: {item.get('url_sol_garimpa') or item['link']}",
              '⚠️ Preço e disponibilidade sujeitos à confirmação na loja.',
              'Publicidade • Link de afiliado SOL GARIMPA']
    return '\n'.join(parts)




def logo_https(raw):
    """Normaliza URLs públicas de logos da Awin sem baixar/copiar as imagens."""
    try:
        from urllib.parse import urlsplit, urlunsplit
        raw = str(raw or '').strip()
        if not raw: return ''
        u = urlsplit(raw)
        if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password:
            return ''
        # Conteúdo misto (HTTP) costuma ser bloqueado em GitHub Pages; usa HTTPS.
        return urlunsplit(('https', u.netloc, u.path, u.query, ''))
    except (ValueError, TypeError):
        return ''


def loja_dominio(programme):
    """Extrai o domínio do anunciante, sem usar o domínio da Awin."""
    from urllib.parse import urlsplit
    urls = [programme.get('displayUrl') or '']
    for item in programme.get('validDomains') or []:
        if isinstance(item, dict): urls.append(item.get('domain') or '')
        elif isinstance(item, str): urls.append(item)
    for raw in urls:
        try:
            text = str(raw).strip()
            u = urlsplit(text if '://' in text else 'https://' + text)
            host = str(u.hostname or '').lower().removeprefix('www.')
            if host and '.' in host and all(c.isalnum() or c in '.-' for c in host):
                if not host.endswith(('awin.com', 'awin1.com')):
                    return host
        except ValueError:
            continue
    return ''


def get_branding(token):
    """Lê metadados de lojas aprovadas da API oficial de programas da Awin.

    Cada resultado pode conter logoUrl e displayUrl/validDomains. Uma falha na API
    NÃO deve interromper a busca de ofertas nem a publicação da vitrine.
    """
    url = f'https://api.awin.com/publishers/{PUBLISHER_ID}/programmes?relationship=joined'
    try:
        with request(url, token=token, timeout=35) as response:
            programmes = json.load(response)
        if isinstance(programmes, dict):
            programmes = (programmes.get('programmes') or programmes.get('results')
                          or programmes.get('data') or [])
        if not isinstance(programmes, list): raise ValueError('Resposta de programas não é lista')
        metadata = {}
        for programme in programmes:
            if not isinstance(programme, dict): continue
            store = identify(programme.get('name'))
            if not store: continue
            metadata[store] = {
                'logo_url': logo_https(programme.get('logoUrl')),
                'dominio_loja': loja_dominio(programme)
            }
        print(f'Metadados oficiais de logos: {len(metadata)} lojas aprovadas identificadas')
        return metadata
    except Exception as err:
        print(f'Metadados de logos indisponíveis ({type(err).__name__}); ofertas preservadas', file=sys.stderr)
        return {}


def main():
    token = os.environ.get('AWIN_PUBLISHER_TOKEN', '').strip()
    key = os.environ.get('AWIN_DATAFEED_KEY', '').strip()
    if not token: sys.exit('AWIN_PUBLISHER_TOKEN não configurado. Nenhum arquivo atualizado.')
    if not key: sys.exit('AWIN_DATAFEED_KEY não configurado. Nenhum arquivo atualizado.')
    try:
        branding = get_branding(token)
        promos = get_offers(token)
        products, report = get_products(key)
        cards = []; active = []
        for store, has_feed in STORES:
            selection = promos.get(store, []) + products.get(store, [])
            # For empty stores, a truthful informational tile only, no affiliate link.
            if selection:
                active.append(store); cards.extend(selection)
            else:
                cards.append({'id': 's-' + compact(store), 'loja': store,
                    'tipo': 'sem_oferta', 'titulo': 'Nenhuma oferta vigente encontrada na fonte',
                    'descricao': '', 'imagem': None, 'preco': None, 'preco_anterior': None,
                    'desconto_pct': None, 'link': None, 'cupom': None, 'validade': None,
                    'termos': ''})
        for item in cards:
            # Adiciona logos oficiais e domínios sem pedir arquivos manuais.
            meta = branding.get(item['loja'], {})
            item['logo_url'] = meta.get('logo_url', '')
            item['dominio_loja'] = meta.get('dominio_loja', '')
            attach_sol_page(item)
        now = dt.datetime.now(UTC).isoformat(timespec='seconds')
        output = {'fonte': 'Awin', 'publisher_id': PUBLISHER_ID, 'atualizado_em': now,
                  'anunciantes': [{'nome': n, 'possui_feed': f,
                      'logo_url': branding.get(n, {}).get('logo_url', ''),
                      'dominio_loja': branding.get(n, {}).get('dominio_loja', ''),
                      'ofertas_encontradas':
                      sum(1 for item in cards if item['loja'] == n and item['tipo'] != 'sem_oferta')}
                      for n, f in STORES],
                  'status': {'anunciantes_listados':len(STORES), 'com_ofertas':len(active),
                             'com_feed': sum(1 for _, feed in STORES if feed)},
                  'cards': cards}
        TARGET.parent.mkdir(exist_ok=True, parents=True)
        TARGET.write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        # Queue is intentionally NOT an automatic WhatsApp sender.
        queue = [{'id': p['id'], 'loja': p['loja'], 'link': p['link'], 'url_sol_garimpa': p['url_sol_garimpa'],
                  'mensagem': whatsapp_message(p), 'gerado_em': now}
                 for p in cards if p.get('link') and whatsapp_message(p)]
        (TARGET.parent / 'fila_whatsapp.json').write_text(
            json.dumps({'gerado_em': now, 'enviado': False, 'fila': queue}, ensure_ascii=False, indent=2),
            encoding='utf-8')
        (TARGET.parent / 'mensagens_whatsapp.txt').write_text(
            '\n\n' + ('\n\n' + '━' * 32 + '\n\n').join(item['mensagem'] for item in queue),
            encoding='utf-8')
        print('OK:', len(cards), 'cards,', len(active), 'anunciantes com ofertas', '->', TARGET)
        for store in report:
            if not report[store]['feed_listado']:
                print('Não encontrado feed na lista:', store)
    except Exception as e:
        # Fail closed. Preserve previous JSON; HTML rejects stale data after max age.
        print('Erro ao atualizar dados Awin:', type(e).__name__, str(e).replace(token,'[SEGREDO]').replace(key,'[SEGREDO]')[:220], file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__': main()
