#!/usr/bin/env python3
"""SOL GARIMPA: ler a planilha de avisos da Rakuten e postar novidades autorizadas.

Usa somente links recriados pela API Rakuten para parcerias ativas.
Primeira execução registra a linha de base; não anuncia ofertas antigas.
Não acessa o Telegram pessoal via sessão MTProto.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import html
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from sync_rakuten import make_access_token, get_partnerships, request as rakuten_request
from telegram_imagens import enviar_oferta, imagem_publica

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "docs" / "telegram" / "rakuten_planilha_vistos.json"
SHEET_ID = "1o_0X4axrY5gXNMuXxfxGohmswjyUV0nx4m6i4qWTxN8"
TABS = {"Ofertas": (101, 9), "Cupons": (102, 10), "Lançamentos": (103, 7)}
FUSO = ZoneInfo("America/Sao_Paulo")
CANAL = "@solgarimpaofertas"
MAX_POSTS = 4
MAX_BYTES = 1000000


def normal(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or ""))
    return re.sub(r"[^a-z0-9]+", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


def url_loja(s):
    try:
        u = urlsplit(str(s or "").strip())
        host = (u.hostname or "").lower().rstrip(".")
        if u.scheme != "https" or not host or u.username or u.password:
            return ""
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
            return ""
        try:
            if not ipaddress.ip_address(host).is_global:
                return ""
        except ValueError:
            pass
        if host == "linksynergy.com" or host.endswith(".linksynergy.com"):
            return ""
        if host in ("t.me", "telegram.me") or host.endswith(".t.me"):
            return ""
        return u.geturl()
    except (TypeError, ValueError):
        return ""


def baixar_aba(aba, gid, minimo):
    raiz = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
    enderecos = [
        f"{raiz}/export?format=csv&gid={gid}",
        f"{raiz}/gviz/tq?tqx=out:csv&gid={gid}",
    ]
    falhas = []
    for endereco in enderecos:
        req = Request(endereco, headers={"User-Agent": "SolGarimpa/1.0", "Accept": "text/csv"})
        try:
            with urlopen(req, timeout=25) as resp:
                bruto = resp.read(MAX_BYTES + 1)
                tipo = resp.headers.get("Content-Type", "")
            if len(bruto) > MAX_BYTES or "text/html" in tipo.lower():
                raise ValueError("resposta HTML ou CSV grande demais")
            conteudo = bruto.decode("utf-8-sig")
            linhas = list(csv.reader(io.StringIO(conteudo)))
            if not linhas or len(linhas[0]) < minimo - 1:
                raise ValueError("cabecalho da planilha incompleto")
            if normal(linhas[0][0]) != "data" or normal(linhas[0][1]) != "anunciante":
                raise ValueError("formato inesperado da planilha")
            return [linha + [""] * max(0, minimo - len(linha)) for linha in linhas[1:] if any(x.strip() for x in linha)]
        except (HTTPError, URLError, TimeoutError, UnicodeError, ValueError) as exc:
            falhas.append(type(exc).__name__ if not isinstance(exc, HTTPError) else f"HTTP {exc.code}")
    raise RuntimeError(
        f"Aba {aba} indisponivel sem login ({', '.join(falhas)}). "
        "A planilha precisa permitir leitura publica por link; nenhum envio foi feito."
    )


def data_br(s):
    try:
        return datetime.strptime(str(s).strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def linhas_ofertas(agora):
    itens = []
    for aba, (gid, minimo) in TABS.items():
        linhas = baixar_aba(aba, gid, minimo)
        print(f"{aba}: {len(linhas)} linhas consultadas.")
        for linha in linhas:
            if aba == "Ofertas":
                dt, loja, tipo, titulo, antes, preco, desconto, validade, destino = linha[:9]
                cupom = ""
            elif aba == "Cupons":
                dt, loja, cupom, desconto, titulo, antes, preco, regras, validade, destino = linha[:10]
            else:
                dt, loja, titulo, lancamento, preco, detalhes, destino = linha[:7]
                antes, desconto, validade, cupom = "", "", "", ""
            loja, titulo = loja.strip(), titulo.strip()
            destino = url_loja(destino)
            if not loja or not titulo or not destino:
                continue
            data = data_br(dt)
            if not data:
                continue
            chave = hashlib.sha256(
                (aba + "|" + normal(loja) + "|" + normal(titulo) + "|" +
                 normal(cupom) + "|" + destino).encode("utf-8")
            ).hexdigest()[:28]
            valido_ate = data_br(validade)
            # Anuncios antigos nao entram na fila, sem inventar prazo para cupons.
            elegivel = (0 <= (agora.date() - data).days <= 2 and
                        (valido_ate is None or valido_ate >= agora.date()))
            itens.append({
                "id": chave, "aba": aba, "loja": loja, "titulo": titulo,
                "cupom": cupom.strip(), "desconto": desconto.strip(),
                "preco": preco.strip(), "antes": antes.strip(), "link": destino,
                "data": dt, "elegivel": elegivel,
            })
    return itens


def parceiros_ativos(token):
    parceiros = get_partnerships(token)
    mapa = {}
    for parceiro in parceiros:
        nome = normal(parceiro.get("loja"))
        mid = str(parceiro.get("mid") or "")
        if nome and mid.isdigit():
            mapa.setdefault(nome, set()).add(mid)
    return mapa


def gerar_link(token, mid, destino, identificador):
    payload = json.dumps({
        "url": destino,
        "advertiser_id": int(mid),
        "name": "SolGarimpa-Planilha-" + identificador[:15],
    }).encode("utf-8")
    try:
        resposta = json.loads(rakuten_request(
            "/v1/links/deep_links", token, data=payload,
            extra_headers={"Content-Type": "application/json", "Accept": "application/json"}
        ))
        link = resposta.get("advertiser", {}).get("deep_link", {}).get("deep_link_url", "")
        u = urlsplit(link)
        host = (u.hostname or "").lower()
        if u.scheme == "https" and (host == "linksynergy.com" or host.endswith(".linksynergy.com")):
            return link
    except (RuntimeError, ValueError, TypeError, KeyError):
        pass
    return ""



def imagens_do_catalogo(agora):
    """Relaciona produtos pelo mesmo anunciante e título exatos; nunca inventa fotos."""
    arquivo = ROOT / "docs" / "paginas_ofertas.json"
    try:
        with arquivo.open(encoding="utf-8") as f:
            catalogo = json.load(f)
        atualizado = datetime.fromisoformat(catalogo["gerado_em"].replace("Z", "+00:00"))
        if not (timedelta(0) <= agora - atualizado <= timedelta(hours=48)):
            return {}
        grupos = {}
        for card in catalogo.get("cards", []):
            if not isinstance(card, dict) or card.get("historico") is not False:
                continue
            foto = imagem_publica(card.get("imagem"))
            loja, titulo = normal(card.get("loja")), normal(card.get("titulo"))
            if foto and loja and titulo:
                grupos.setdefault((loja, titulo), set()).add(foto)
        return {
            chave: next(iter(fotos)) for chave, fotos in grupos.items()
            if len(fotos) == 1
        }
    except (OSError, ValueError, TypeError, KeyError):
        return {}

def texto_telegram(item, link):
    safe = lambda s: html.escape(str(s or "")[:250])
    msg = [
        "🛍️ <b>SOL GARIMPA | NOVA OFERTA</b>",
        "",
        f"<b>{safe(item['titulo'])}</b>",
        f"🏬 {safe(item['loja'])}",
    ]
    if item["preco"]:
        msg.append(f"💰 Preço divulgado: {safe(item['preco'])}")
    if item["antes"]:
        msg.append(f"Antes: {safe(item['antes'])}")
    if item["desconto"]:
        msg.append(f"🏷️ {safe(item['desconto'])}")
    if item["cupom"]:
        msg.append(f"🎟️ Cupom: <code>{safe(item['cupom'])}</code>")
    msg.extend([
        "",
        f'🛒 <a href="{html.escape(link, quote=True)}">Conferir oferta na loja</a>',
        "🌐 https://www.ofertaspravc.com.br",
        "",
        "Publicidade • Oferta divulgada pelo anunciante. Confira preço, estoque e regras no site.",
    ])
    return "\n".join(msg)


def publicar(token, mensagem, imagem=""):
    """Publica com foto quando existir imagem de produto confirmada no catalogo."""
    return enviar_oferta(token, CANAL, mensagem, imagem)


def ler_estado():
    if not STATE_PATH.exists():
        return None
    with STATE_PATH.open(encoding="utf-8") as f:
        dados = json.load(f)
    if not isinstance(dados.get("vistos"), dict):
        raise RuntimeError("Estado do monitor invalido; nao publicar antes de corrigir.")
    return dados


def salvar_estado(dados):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE_PATH)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Nao envia nem grava estado.")
    args = parser.parse_args()
    agora = datetime.now(FUSO)
    itens = linhas_ofertas(agora)
    if not itens:
        raise RuntimeError("Nenhum registro valido encontrado nas abas; estado preservado.")

    estado = ler_estado()
    if estado is None:
        print(f"Primeiro acesso: {len(itens)} registros atuais serao marcados como historicos.")
        if not args.dry_run:
            salvar_estado({"criado_em": agora.isoformat(),
                           "vistos": {i["id"]: agora.isoformat() for i in itens}})
        return

    vistos = estado["vistos"]
    novos = [i for i in itens if i["id"] not in vistos]
    print(f"Novos registros: {len(novos)}.")
    if args.dry_run:
        print("Simulacao: nenhum envio e nenhuma alteracao no historico.")
        return

    validos = [i for i in novos if i["elegivel"]]
    if validos:
        fotos = imagens_do_catalogo(agora)
        token = make_access_token()
        mapa = parceiros_ativos(token)
        enviados = 0
        for item in validos:
            if enviados >= MAX_POSTS:
                break
            mids = mapa.get(normal(item["loja"]), set())
            if len(mids) != 1:
                print("Ignorando anunciante sem parceria ativa e unica:", item["loja"])
                vistos[item["id"]] = agora.isoformat()
                continue
            link = gerar_link(token, next(iter(mids)), item["link"], item["id"])
            if not link:
                print("Deep link nao aprovado para:", item["loja"], "- sem publicacao.")
                continue
            try:
                foto = fotos.get((normal(item["loja"]), normal(item["titulo"])), "")
                formato = publicar(
                    os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
                    texto_telegram(item, link), foto
                )
                print("Formato de publicacao:", formato)
            except (RuntimeError, URLError, TimeoutError) as exc:
                print("Falha ao publicar:", type(exc).__name__, "cheque o canal antes de repetir.")
                continue
            vistos[item["id"]] = agora.isoformat()
            enviados += 1
            print("Oferta enviada:", item["loja"], "-", item["titulo"][:80])
        print("Publicacoes confirmadas:", enviados)
    # Registros muito antigos ou vencidos nao devem ser enviados em execucoes seguintes.
    for item in novos:
        if not item["elegivel"]:
            vistos[item["id"]] = agora.isoformat()
    # Nunca reduzir o historico por mudanca de posicao das linhas; limite apenas por idade.
    limite = agora - timedelta(days=90)
    estado["vistos"] = {
        id_: dt for id_, dt in vistos.items()
        if (lambda d: d is not None and d >= limite)(
            datetime.fromisoformat(dt) if isinstance(dt, str) else None
        )
    }
    estado["atualizado_em"] = agora.isoformat()
    salvar_estado(estado)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Monitoramento Rakuten:", str(exc), file=sys.stderr)
        raise SystemExit(1)
