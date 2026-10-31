"""Entrega de ofertas Telegram: foto real quando disponível, texto como fallback."""
from __future__ import annotations

import html
import ipaddress
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

CANAL = "@solgarimpaofertas"


def imagem_publica(valor):
    """Aceita apenas URLs HTTPS de host público (nunca URL local ou credenciais)."""
    if not isinstance(valor, str) or len(valor) > 1800:
        return ""
    try:
        url = urlsplit(valor.strip())
        host = (url.hostname or "").lower().strip(".")
        if url.scheme != "https" or not host or url.username or url.password:
            return ""
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
            return ""
        try:
            if not ipaddress.ip_address(host).is_global:
                return ""
        except ValueError:
            pass
        return url.geturl()
    except ValueError:
        return ""


def tamanho_legenda(mensagem):
    """O limite do Telegram é depois da formatação HTML, não antes."""
    sem_tags = re.sub(r"<[^>]*>", "", mensagem)
    return len(html.unescape(sem_tags).encode("utf-16-le")) // 2


def requisitar(token, metodo, dados):
    req = Request(
        f"https://api.telegram.org/bot{token}/{metodo}",
        data=json.dumps(dados, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=30) as resp:
        resposta = json.load(resp)
    if resposta.get("ok") is not True:
        raise RuntimeError(f"Telegram não confirmou {metodo}.")
    return resposta


def enviar_oferta(token, canal, mensagem, imagem=""):
    """Envia foto+legenda. Fallback somente em erro HTTP 400 confirmado.

    Falhas de rede de resultado incerto nunca causam um segundo envio automático,
    para reduzir o risco de publicação duplicada.
    """
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN ausente.")
    if canal != CANAL:
        raise RuntimeError("Canal não autorizado.")
    foto = imagem_publica(imagem)
    if foto and tamanho_legenda(mensagem) <= 1024:
        try:
            requisitar(token, "sendPhoto", {
                "chat_id": canal,
                "photo": foto,
                "caption": mensagem,
                "parse_mode": "HTML",
                "show_caption_above_media": False,
            })
            return "foto"
        except HTTPError as exc:
            if exc.code != 400:
                raise RuntimeError(f"Falha HTTP {exc.code} em sendPhoto.") from None
            print("Imagem rejeitada pelo Telegram (HTTP 400); enviando texto.")
    elif foto:
        print("Legenda longa demais para sendPhoto; enviando texto.")

    try:
        requisitar(token, "sendMessage", {
            "chat_id": canal,
            "text": mensagem,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })
        return "texto"
    except HTTPError as exc:
        raise RuntimeError(f"Falha HTTP {exc.code} em sendMessage.") from None
