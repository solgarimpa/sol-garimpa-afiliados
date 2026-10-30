#!/usr/bin/env python3
"""SOL GARIMPA - observa um canal Telegram e gera links Rakuten da propria conta.

Uso: servidor persistente com sessao MTProto autorizada pelo proprietario.
Modo seguro inicial: TELEGRAM_ATIVAR_ENVIO=false (nenhuma postagem).
Nao reutiliza links de rastreamento de terceiros.
"""
from __future__ import annotations

import asyncio
import html
import ipaddress
import json
import os
import re
import sqlite3
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from telethon import TelegramClient, events
from telethon.sessions import StringSession

from sync_rakuten import make_access_token, get_partnerships, request

CANAL_DESTINO = "@solgarimpaofertas"
TITULO_ORIGEM = os.getenv("RAKUTEN_TITULO_CANAL", "Rakuten ofertas💜🚀")
CAMINHO_ESTADO = Path(os.getenv("TELEGRAM_ESTADO", "/tmp/sol_garimpa_rakuten.sqlite3"))
ATIVAR_ENVIO = os.getenv("TELEGRAM_ATIVAR_ENVIO", "").lower() == "true"
PADRAO_URL = re.compile(r"https://[^\s<>\"'\u200b]+", re.IGNORECASE)
PADRAO_ANUNCIANTE = re.compile(r"Anunciante\s*:\s*([^\n\r]+)", re.IGNORECASE)


def normalizar(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def validar_url(s):
    try:
        u = urlsplit(s.rstrip(".,;!)]}"))
        host = (u.hostname or "").lower().strip(".")
        if u.scheme != "https" or not host or u.username or u.password:
            return ""
        if host.endswith(".local") or host == "localhost":
            return ""
        try:
            if not ipaddress.ip_address(host).is_global:
                return ""
        except ValueError:
            pass
        if host == "linksynergy.com" or host.endswith(".linksynergy.com"):
            return ""  # nao reaproveitar links rastreados da origem
        if host.startswith("t.me") or host.endswith(".t.me"):
            return ""
        return u.geturl()
    except (ValueError, TypeError):
        return ""


def extrair_urls(mensagem):
    urls = list(PADRAO_URL.findall(mensagem.raw_text or ""))
    marca = getattr(mensagem, "reply_markup", None)
    if marca:
        for linha in getattr(marca, "rows", []):
            for botao in getattr(linha, "buttons", []):
                if getattr(botao, "url", None):
                    urls.append(botao.url)
    for item in getattr(mensagem, "entities", []) or []:
        url = getattr(item, "url", None)
        if url:
            urls.append(url)
    resultado = []
    for u in urls:
        u = validar_url(u)
        if u and u not in resultado:
            resultado.append(u)
    return resultado[:5]


def banco():
    CAMINHO_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(CAMINHO_ESTADO)
    conexao.execute(
        "CREATE TABLE IF NOT EXISTS publicados "
        "(canal INTEGER NOT NULL, mensagem INTEGER NOT NULL, "
        "data TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (canal, mensagem))"
    )
    conexao.commit()
    return conexao


def ja_publicado(conexao, canal, mensagem):
    return conexao.execute(
        "SELECT 1 FROM publicados WHERE canal=? AND mensagem=?",
        (int(canal), int(mensagem)),
    ).fetchone() is not None


def registrar(conexao, canal, mensagem):
    conexao.execute(
        "INSERT OR IGNORE INTO publicados (canal, mensagem) VALUES (?, ?)",
        (int(canal), int(mensagem)),
    )
    conexao.commit()


class Rakuten:
    def __init__(self):
        self.token = None
        self.atualizado = 0
        self.parceiros = {}

    def carregar(self):
        if self.token and time.monotonic() - self.atualizado < 2700:
            return
        token = make_access_token()
        lista = get_partnerships(token)
        mapa = {}
        for p in lista:
            nome = normalizar(p.get("loja", ""))
            mid = str(p.get("mid", ""))
            if nome and mid.isdigit():
                mapa.setdefault(nome, []).append(mid)
        self.parceiros = mapa
        self.token = token
        self.atualizado = time.monotonic()
        print("Parcerias ativas verificadas:", len(lista), flush=True)

    def afiliado(self, nome, url, referencia):
        self.carregar()
        mids = self.parceiros.get(normalizar(nome), [])
        if len(mids) != 1:
            return ""  # ambiguidade ou parceria nao ativa
        payload = json.dumps({
            "url": url,
            "advertiser_id": int(mids[0]),
            "name": "Sol Garimpa Telegram " + str(referencia)[:35],
        }).encode("utf-8")
        try:
            bruto = request(
                "/v1/links/deep_links", self.token, data=payload,
                extra_headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            resp = json.loads(bruto)
            url_afiliada = (
                resp.get("advertiser", {})
                    .get("deep_link", {})
                    .get("deep_link_url", "")
            )
            host = (urlsplit(url_afiliada).hostname or "").lower()
            if urlsplit(url_afiliada).scheme != "https":
                return ""
            if host != "linksynergy.com" and not host.endswith(".linksynergy.com"):
                return ""
            return url_afiliada
        except (ValueError, KeyError, RuntimeError, URLError, HTTPError):
            return ""  # nao publicar links nao autorizados


def montar_mensagem(texto, loja, links):
    # Preserva a chamada da promocao, mas remove todos os links originais.
    texto_limpo = PADRAO_URL.sub("", texto or "")
    texto_limpo = re.sub(r"\n{3,}", "\n\n", texto_limpo).strip()
    texto_limpo = texto_limpo[:800]
    pedacos = [
        "🛍️ <b>SOL GARIMPA | OFERTA</b>",
        "🏬 <b>" + html.escape(loja) + "</b>",
        "",
        html.escape(texto_limpo),
        "",
    ]
    for i, link in enumerate(links, start=1):
        pedacos.append(
            f'🛒 <a href="{html.escape(link, quote=True)}">Ver oferta {i} na loja</a>'
        )
    pedacos.extend([
        "",
        "🌐 https://www.ofertaspravc.com.br",
        "Publicidade • Confirme valores, cupons e validade na loja.",
    ])
    return "\n".join(pedacos)[:3800]


def mandar_telegram(texto):
    token = os.environ["TELEGRAM_BOT_TOKEN"].strip()
    pedido = Request(
        "https://api.telegram.org/bot" + token + "/sendMessage",
        headers={"Content-Type": "application/json"},
        data=json.dumps({
            "chat_id": CANAL_DESTINO,
            "text": texto,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, ensure_ascii=False).encode("utf-8"),
        method="POST",
    )
    try:
        with urlopen(pedido, timeout=30) as resposta:
            dados = json.load(resposta)
        if dados.get("ok") is not True:
            raise RuntimeError("Telegram nao confirmou o envio")
    except HTTPError as e:
        raise RuntimeError(f"Telegram HTTP {e.code} (token nao exibido)") from None


async def executar():
    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    sessao = os.environ["TELEGRAM_STRING_SESSION"]
    if ATIVAR_ENVIO and not os.getenv("TELEGRAM_BOT_TOKEN"):
        raise RuntimeError("Defina TELEGRAM_BOT_TOKEN antes de ativar envios.")

    cliente = TelegramClient(StringSession(sessao), api_id, api_hash)
    api = Rakuten()
    conexao = banco()
    bloqueio = asyncio.Lock()
    async with cliente:
        dialogos = await cliente.get_dialogs(limit=300)
        id_exato = os.getenv("RAKUTEN_CANAL_ID", "").strip()
        if id_exato:
            candidatos = [d for d in dialogos if str(d.entity.id) == id_exato]
        else:
            candidatos = [
                d for d in dialogos
                if d.is_channel and normalizar(d.name) == normalizar(TITULO_ORIGEM)
            ]
        if len(candidatos) != 1:
            raise RuntimeError(
                "Canal da Rakuten nao localizado de forma unica; "
                "confira a conta autorizada, assinatura e RAKUTEN_CANAL_ID."
            )
        canal = candidatos[0].entity
        print("Monitorando canal:", candidatos[0].name, "| ID:", canal.id, flush=True)
        print("Modo:", "ENVIO ATIVO" if ATIVAR_ENVIO else "SOMENTE SIMULACAO", flush=True)

        @cliente.on(events.NewMessage(chats=canal))
        async def ao_receber(evento):
            async with bloqueio:
                mid = evento.message.id
                if ja_publicado(conexao, canal.id, mid):
                    return
                texto = evento.raw_text or ""
                anuncio = PADRAO_ANUNCIANTE.search(texto)
                if not anuncio:
                    print("Mensagem ignorada: anunciante nao identificado.", flush=True)
                    return
                loja = anuncio.group(1).strip()
                urls = extrair_urls(evento.message)
                if not urls:
                    print("Mensagem ignorada: sem URL direta valida.", flush=True)
                    return
                identificacao = f"{canal.id}-{mid}"
                gerados = []
                for url in urls:
                    link = await asyncio.to_thread(
                        api.afiliado, loja, url, identificacao
                    )
                    if link:
                        gerados.append(link)
                if not gerados:
                    print("Mensagem ignorada: sem deep link autorizado.", flush=True)
                    return
                if not ATIVAR_ENVIO:
                    print(f"SIMULACAO: {loja} com {len(gerados)} links proprios.", flush=True)
                    registrar(conexao, canal.id, mid)
                    return
                mensagem = montar_mensagem(texto, loja, gerados)
                try:
                    await asyncio.to_thread(mandar_telegram, mensagem)
                except (RuntimeError, URLError, TimeoutError):
                    print("Falha ao postar; verificar canal antes de novo envio.", flush=True)
                    return
                registrar(conexao, canal.id, mid)
                print(f"Publicado: mensagem {mid}, anunciante {loja}.", flush=True)

        await cliente.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(executar())
    except (KeyError, ValueError):
        raise SystemExit("Credenciais ausentes ou invalidas; confira as variaveis privadas.")
