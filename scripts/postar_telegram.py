#!/usr/bin/env python3
"""SOL GARIMPA: publica uma oferta de afiliado no canal Telegram.

Lê exclusivamente o catálogo consolidado gerado pelos coletores oficiais.
Não copia links recebidos em canais de outros afiliados.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import html
import ipaddress
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from telegram_imagens import enviar_oferta, imagem_publica

ROOT = Path(__file__).resolve().parents[1]
CATALOGO = ROOT / "docs" / "paginas_ofertas.json"
HISTORICO = ROOT / "docs" / "telegram" / "publicados.json"
REDES = {"Rakuten", "Lomadee", "Awin"}
DESTINO_PADRAO = "@solgarimpaofertas"
LIMITE_HISTORICO = 2000


def data_utc(valor):
    if not isinstance(valor, str) or not valor:
        return None
    try:
        dt = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        pass
    return None


def url_publica(valor):
    if not isinstance(valor, str):
        return ""
    try:
        url = urlsplit(valor.strip())
        host = (url.hostname or "").lower().strip(".")
        if url.scheme != "https" or not host or url.username or url.password:
            return ""
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
            return ""
        try:
            endereco = ipaddress.ip_address(host)
            if not endereco.is_global:
                return ""
        except ValueError:
            pass
        return url.geturl()
    except ValueError:
        return ""


def numero(valor):
    if isinstance(valor, bool):
        return None
    try:
        valor = float(valor)
        if 0 < valor < 100000000:
            return valor
    except (ValueError, TypeError, OverflowError):
        pass
    return None


def reais(valor):
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def ler_json(caminho, padrao):
    if not caminho.exists():
        return padrao
    with caminho.open(encoding="utf-8") as arquivo:
        return json.load(arquivo)


def selecionar(catalogo, publicados, agora):
    gerado = data_utc(catalogo.get("gerado_em"))
    if not gerado or not timedelta(0) <= agora - gerado <= timedelta(hours=24):
        raise RuntimeError("Catálogo consolidado ausente, futuro ou desatualizado (mais de 24h).")

    vistos = set(publicados)
    candidatos = []
    for item in catalogo.get("cards", []):
        if not isinstance(item, dict) or item.get("historico") is not False:
            continue
        rede = item.get("rede")
        if rede not in REDES or item.get("tipo") not in {"produto", "promocao", "cupom"}:
            continue
        slug = str(item.get("slug") or "")
        titulo = " ".join(str(item.get("titulo") or "").split())[:170]
        loja = " ".join(str(item.get("loja") or "").split())[:80]
        link = url_publica(item.get("link"))
        ultima = data_utc(item.get("ultima_confirmacao"))
        vence = data_utc(item.get("validade"))
        if item.get("validade") and not vence:
            continue
        if vence and vence <= agora:
            continue
        if not slug or not titulo or not loja or not link or not ultima:
            continue
        if not timedelta(0) <= agora - ultima <= timedelta(hours=24):
            continue
        identificador = hashlib.sha256((rede + ":" + slug).encode()).hexdigest()[:24]
        if identificador in vistos:
            continue

        preco = numero(item.get("preco")) if item.get("moeda") == "BRL" else None
        anterior = numero(item.get("preco_anterior")) if preco else None
        desconto = (100 * (1 - preco / anterior)) if anterior and anterior > preco else 0
        cupom = " ".join(str(item.get("cupom") or "").split())[:50]
        # Prioriza descontos verificáveis e cupons sobre preço de catálogo.
        pontuacao = (40 if cupom else 0) + min(desconto, 80)
        if item.get("tipo") == "promocao":
            pontuacao += 5
        candidatos.append((pontuacao, identificador, {
            "rede": rede, "slug": slug, "titulo": titulo, "loja": loja,
            "link": link, "preco": preco, "anterior": anterior,
            "desconto": desconto, "cupom": cupom,
            "imagem": imagem_publica(item.get("imagem")),
        }))

    # Ordem estável para que a oferta seguinte seja escolhida após salvar o histórico.
    candidatos.sort(key=lambda r: (-r[0], r[1]))
    return candidatos[0][1:] if candidatos else None


def formatar(oferta):
    nome = html.escape(oferta["titulo"])
    loja = html.escape(oferta["loja"])
    url = html.escape(oferta["link"], quote=True)
    partes = ["🛍️ <b>SOL GARIMPA | OFERTA</b>", "", f"<b>{nome}</b>",
              f"🏬 {loja}"]
    if oferta["preco"] is not None:
        partes.append(f"💰 {reais(oferta['preco'])}")
    if oferta["desconto"] >= 1:
        partes.append(f"🏷️ {oferta['desconto']:.0f}% de desconto indicado no catálogo")
    if oferta["cupom"]:
        partes.append(f"🎟️ Cupom: <code>{html.escape(oferta['cupom'])}</code>")
    partes.extend(["", f'🛒 <a href="{url}">Conferir oferta na loja</a>',
                   "🔎 Mais ofertas: https://www.ofertaspravc.com.br",
                   "", "Publicidade • Preços, estoque e condições sujeitos a alteração."])
    return "\n".join(partes)


def enviar(token, canal, mensagem, imagem=""):
    """Usa foto real do catalogo, com alternativa em texto."""
    return enviar_oferta(token, canal, mensagem, imagem)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Inspeciona uma oferta sem enviar mensagem nem modificar histórico.")
    args = parser.parse_args()
    agora = datetime.now(timezone.utc)
    catalogo = ler_json(CATALOGO, {})
    estado = ler_json(HISTORICO, {"itens": []})
    itens = estado.get("itens", [])
    if not isinstance(itens, list):
        raise RuntimeError("Histórico de publicações inválido.")
    publicados = {r["id"] for r in itens if isinstance(r, dict) and isinstance(r.get("id"), str)}
    escolhido = selecionar(catalogo, publicados, agora)
    if not escolhido:
        print("Nenhuma nova oferta elegível para publicar.")
        return

    identificador, oferta = escolhido
    print("Oferta selecionada:", oferta["rede"], "-", oferta["loja"], "-", oferta["titulo"])
    if args.dry_run:
        print("TESTE: nenhuma mensagem enviada e histórico não modificado.")
        return

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    canal = os.getenv("TELEGRAM_CHAT_ID", DESTINO_PADRAO).strip()
    if not token or canal != DESTINO_PADRAO:
        raise RuntimeError("Confira TELEGRAM_BOT_TOKEN e destino @solgarimpaofertas.")
    formato = enviar(token, canal, formatar(oferta), oferta.get("imagem", ""))
    print("Formato enviado ao Telegram:", formato)
    HISTORICO.parent.mkdir(parents=True, exist_ok=True)
    itens.append({"id": identificador, "slug": oferta["slug"], "rede": oferta["rede"],
                  "publicado_em": agora.isoformat()})
    dados = {"atualizado_em": agora.isoformat(), "itens": itens[-LIMITE_HISTORICO:]}
    temp = HISTORICO.with_suffix(".tmp")
    temp.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(HISTORICO)
    print("Publicação confirmada e registrada. Nenhum token foi exibido.")


if __name__ == "__main__":
    main()
