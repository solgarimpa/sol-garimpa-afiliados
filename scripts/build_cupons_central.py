#!/usr/bin/env python3
"""Gera catálogo de cupons da SOL GARIMPA a partir de feeds de afiliados existentes.

Nunca captura conteúdo de páginas de terceiros nem inventa cupons.
Ignora feeds antigos, registros históricos, links inseguros e vouchers vencidos.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import pathlib
import re
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/cupons/catalogo.json"
UTC = dt.timezone.utc
FONTES = (
    ("Awin", ROOT / "docs/cupons/ofertas.json"),
    ("Rakuten", ROOT / "docs/rakuten/ofertas.json"),
    ("Lomadee", ROOT / "docs/lomadee/ofertas.json"),
)
MAX_IDADE_FONTE_H = 3
MAX_CUPONS = 2500
MAX_PROMOS = 250

def data(v):
    if not isinstance(v, str) or not v.strip():
        return None
    try:
        d = dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
        return d.astimezone(UTC) if d.tzinfo else None
    except ValueError:
        return None

def texto(v, tamanho=300):
    return " ".join(str(v or "").split())[:tamanho]

def https(v):
    s = texto(v, 4000)
    try:
        p = urlsplit(s)
        host = (p.hostname or "").lower()
        if p.scheme != "https" or not host or p.username or p.password:
            return ""
        if host in ("localhost", "127.0.0.1", "::1") or host.endswith(".local"):
            return ""
        return s
    except (ValueError, TypeError):
        return ""

def normalizar(entrada, fonte, agora):
    if not isinstance(entrada, dict) or entrada.get("historico") is True:
        return None
    loja = texto(entrada.get("loja"), 110)
    titulo = texto(entrada.get("titulo"), 240)
    link = https(entrada.get("link"))
    voucher = texto(entrada.get("cupom"), 90)
    validade_bruta = entrada.get("validade")
    vencimento = data(validade_bruta)
    if validade_bruta and not vencimento:
        return None
    if vencimento and vencimento <= agora:
        return None
    if not loja or not titulo or not link:
        return None
    if entrada.get("tipo") == "produto":
        return None
    tipo = "cupom" if voucher else "promocao"
    if tipo == "promocao" and fonte != "Awin":
        return None
    # Cupons sem código não são anunciados como se tivessem voucher.
    chave = (loja.casefold(), voucher.casefold() if voucher else titulo.casefold())
    identificador = hashlib.sha256(repr(chave).encode("utf-8")).hexdigest()[:18]
    return {
        "id": identificador,
        "loja": loja,
        "tipo": tipo,
        "titulo": titulo,
        "descricao": texto(entrada.get("descricao"), 450),
        "termos": texto(entrada.get("termos"), 900),
        "cupom": voucher,
        "validade": vencimento.isoformat().replace("+00:00", "Z") if vencimento else None,
        "link": link,
        "rede": fonte,
    }

def gerar():
    agora = dt.datetime.now(UTC)
    cupons = {}
    promos = {}
    situacao = {}
    fontes_validas = 0
    for rede, arquivo in FONTES:
        try:
            d = json.loads(arquivo.read_text(encoding="utf-8"))
            atualizado = data(d.get("atualizado_em"))
            if not atualizado or atualizado > agora + dt.timedelta(minutes=10):
                situacao[rede] = "sem_data_confiavel"
                continue
            if agora - atualizado > dt.timedelta(hours=MAX_IDADE_FONTE_H):
                situacao[rede] = "desatualizada"
                continue
            linhas = d.get("ofertas") if isinstance(d.get("ofertas"), list) else d.get("cards", [])
            if not isinstance(linhas, list):
                situacao[rede] = "formato_invalido"
                continue
            fontes_validas += 1
            contagem = 0
            for linha in linhas:
                item = normalizar(linha, rede, agora)
                if not item:
                    continue
                dicionario = cupons if item["cupom"] else promos
                if item["id"] not in dicionario:
                    dicionario[item["id"]] = item
                    contagem += 1
            situacao[rede] = contagem
        except (OSError, ValueError, TypeError) as e:
            situacao[rede] = "erro_leitura:" + type(e).__name__
    if not fontes_validas:
        raise RuntimeError("Nenhum feed atualizado. Catálogo anterior preservado.")

    lista = sorted(cupons.values(), key=lambda x: (x["loja"].casefold(), x["titulo"].casefold()))[:MAX_CUPONS]
    promocoes = sorted(promos.values(), key=lambda x: (x["loja"].casefold(), x["titulo"].casefold()))[:MAX_PROMOS]
    todas = lista + promocoes
    catalogo = {
        "titulo": "Os melhores cupons de Desconto atualizados",
        "atualizado_em": agora.isoformat().replace("+00:00", "Z"),
        "total": len(todas),
        "total_cupons": len(lista),
        "total_promocoes": len(promocoes),
        "fontes": situacao,
        "ofertas": todas,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(catalogo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(OUTPUT)
    print(f"Catálogo: {len(lista)} cupons com código; {len(promocoes)} promoções; fontes={situacao}")

if __name__ == "__main__":
    gerar()
