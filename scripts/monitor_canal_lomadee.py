#!/usr/bin/env python3
"""SOL GARIMPA — canal publico @ofertaslomadee -> Telegram proprio.

Consulta a pagina publica t.me/s/ofertaslomadee. Nao acessa contas Telegram
pessoais, nao copia links de outros afiliados e nao republica posts antigos.
Somente envia se a API Lomadee gerar link rastreavel da Sol Garimpa.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import html
from html.parser import HTMLParser
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import sync_lomadee as lomadee
from telegram_imagens import enviar_oferta, imagem_publica

ROOT = Path(__file__).resolve().parents[1]
ESTADO = ROOT / "docs" / "telegram" / "lomadee_canal_vistos.json"
FONTE = "https://t.me/s/ofertaslomadee"
CANAL_DESTINO = "@solgarimpaofertas"
MAX_POSTS = 4
MAX_HTML = 2_000_000
MAX_INTERVALO = timedelta(hours=40)
LINKS = re.compile(r"https://[^\s<>\"']+")
FOTO = re.compile(r"background-image:\s*url\(['\"]?(https://[^)'\"\s]+)", re.I)


def normal(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return re.sub(r"[^a-z0-9]+", "", "".join(ch for ch in s if not unicodedata.combining(ch)).lower())


def loja_url(valor):
    try:
        s = str(valor or "").strip().rstrip(".,;)]}")
        u = urlsplit(s)
        host = (u.hostname or "").lower().strip(".")
        if u.scheme != "https" or not host or u.username or u.password:
            return ""
        if host in ("localhost", "t.me", "telegram.me", "app.lomadee.com.br"):
            return ""
        if host.endswith((".local", ".t.me", ".linksynergy.com", ".lmdee.link")):
            return ""
        if host in ("lmdee.link", "linksynergy.com", "api.lomadee.com.br"):
            return ""
        try:
            if not ipaddress.ip_address(host).is_global:
                return ""
        except ValueError:
            pass
        return u.geturl()
    except (ValueError, TypeError):
        return ""


def data_utc(valor):
    try:
        d = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        if d.tzinfo:
            return d.astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass
    return None


class MensagensTelegram(HTMLParser):
    """Extrai so texto e metadados de cada postagem, nao a pagina inteira."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.mensagens = []
        self.atual = None
        self.profundidade = 0
        self.texto_ate = None

    def handle_starttag(self, tag, atributos):
        atr = dict(atributos)
        classes = set((atr.get("class") or "").split())
        identificador = atr.get("data-post", "")
        novo = (tag == "div" and "tgme_widget_message" in classes
                and re.fullmatch(r"ofertaslomadee/\d+", identificador))
        if novo and self.atual is None:
            self.atual = {
                "id": int(identificador.rsplit("/", 1)[1]),
                "partes": [], "links": [], "data": "", "foto": ""
            }
            self.profundidade = 0
            self.texto_ate = None

        if self.atual is None:
            return
        if tag == "div":
            self.profundidade += 1
            if "tgme_widget_message_text" in classes:
                self.texto_ate = self.profundidade
        if tag == "br" and self.texto_ate is not None:
            self.atual["partes"].append("\n")
        if tag == "time" and atr.get("datetime"):
            self.atual["data"] = atr["datetime"]
        if tag == "a" and self.texto_ate is not None and atr.get("href"):
            self.atual["links"].append(atr["href"])
        if ("tgme_widget_message_photo_wrap" in classes
                or "tgme_widget_message_video_thumb" in classes):
            encontrado = FOTO.search(atr.get("style", ""))
            if encontrado:
                self.atual["foto"] = encontrado.group(1)

    def handle_data(self, texto):
        if self.atual is not None and self.texto_ate is not None:
            self.atual["partes"].append(texto)

    def handle_endtag(self, tag):
        if tag != "div" or self.atual is None:
            return
        if self.texto_ate == self.profundidade:
            self.texto_ate = None
        self.profundidade -= 1
        if self.profundidade == 0:
            self.atual["texto"] = "".join(self.atual.pop("partes"))
            self.mensagens.append(self.atual)
            self.atual = None
            self.texto_ate = None


def pagina_publica():
    req = Request(FONTE, headers={
        "User-Agent": "Mozilla/5.0 (compatible; SolGarimpaMonitor/1.0)",
        "Accept": "text/html",
    })
    try:
        with urlopen(req, timeout=25) as resposta:
            conteudo = resposta.read(MAX_HTML + 1)
            tipo = resposta.headers.get("Content-Type", "")
    except HTTPError as exc:
        raise RuntimeError(f"Pagina Telegram indisponivel: HTTP {exc.code}") from None
    except (URLError, TimeoutError):
        raise RuntimeError("Pagina Telegram sem resposta; nenhuma publicacao realizada.") from None
    if len(conteudo) > MAX_HTML or "html" not in tipo.lower():
        raise RuntimeError("Resposta publica do Telegram invalida.")
    texto = conteudo.decode("utf-8", "replace")
    analisador = MensagensTelegram()
    analisador.feed(texto)
    posts = analisador.mensagens
    if not posts:
        raise RuntimeError("Preview sem mensagens reconheciveis; nao alterar historico.")
    return sorted({x["id"]: x for x in posts}.values(), key=lambda x: x["id"])


def buscar_anunciantes():
    if not lomadee.KEY:
        raise RuntimeError("Secret LOMADEE_API_TOKEN ausente; nao publicar.")
    marcas = lomadee.paginate("/affiliate/brands", 20, 25, meta_key="pagination")
    resultado = {}
    for marca in marcas:
        id_ = str(marca.get("id") or "")
        nome = str(marca.get("name") or "")
        if id_ and nome:
            resultado.setdefault(normal(nome), []).append((id_, nome))
    return resultado


def extrair(post, marcas):
    texto = post.get("texto") or ""
    linhas = [s.strip() for s in texto.splitlines() if s.strip()]
    if len(linhas) < 2 or "novo anunciante" in normal(texto[:120]):
        return None
    primeira = normal(linhas[0])
    if not primeira:
        return None
    # Compatibilidade com "Gazin Fecha Mes", "Camisaria Colombo:" e similares.
    possiveis = [
        (len(marca), dados) for marca, itens in marcas.items()
        if primeira == marca or (primeira.startswith(marca) and len(marca) >= 5)
        for dados in itens
    ]
    if not possiveis:
        return None
    possiveis.sort(key=lambda z: z[0], reverse=True)
    if len(possiveis) > 1 and possiveis[0][0] == possiveis[1][0]:
        return None
    organizacao, nome = possiveis[0][1]

    urls = [*post.get("links", []), *LINKS.findall(texto)]
    destino = next((u for valor in urls if (u := loja_url(valor))), "")
    if not destino:
        return None

    conteudo = []
    for linha in linhas[1:]:
        if (linha.startswith("http") or
                "não esqueça de gerar seu link" in linha.lower() or
                "nao esqueca de gerar seu link" in linha.lower()):
            continue
        conteudo.append(linha)
    if not conteudo:
        return None

    titulo = conteudo[0][:170]
    detalhes = "\n".join(conteudo[1:])[:350]
    if "na plataforma lomadee" in titulo.lower():
        return None
    return {"id":post["id"],"organizacao":organizacao, "loja":nome,
            "titulo":titulo, "detalhes":detalhes, "destino":destino,
            "imagem": imagem_publica(post.get("foto"))}


def link_solgarimpa(organizacao, destino):
    # A API so retorna links do canal afiliado configurado da Sol Garimpa.
    try:
        resposta = lomadee.request("/affiliate/shortener/url", payload={
            "organizationId": organizacao,
            "type": "Custom",
            "url": destino,
        })
        link = lomadee.select_link(resposta)
        host = (urlsplit(link).hostname or "").lower()
        if urlsplit(link).scheme == "https" and (host == "lmdee.link" or host.endswith(".lmdee.link")):
            return link
    except (RuntimeError, ValueError, KeyError, TypeError):
        pass
    return ""


def mensagem(item, link):
    esc = lambda s: html.escape(str(s or ""), quote=True)
    pedacos = ["🛍️ <b>SOL GARIMPA | OFERTA LOMADEE</b>", "",
               f"<b>{esc(item['titulo'])}</b>", f"🏬 {esc(item['loja'])}"]
    if item["detalhes"]:
        pedacos.append(esc(item["detalhes"]))
    pedacos.extend([
        "", f'🛒 <a href="{esc(link)}">Ver oferta na loja</a>',
        "🔎 https://www.ofertaspravc.com.br", "",
        "Publicidade • Verifique preços, validade e estoque no site da loja.",
    ])
    return "\n".join(pedacos)[:3600]


def ler_estado():
    if not ESTADO.exists():
        return None
    with ESTADO.open(encoding="utf-8") as f:
        estado = json.load(f)
    if not isinstance(estado, dict) or not isinstance(estado.get("vistos"), dict):
        raise RuntimeError("Historico Lomadee invalido; preservado sem publicar.")
    return estado


def salvar_estado(estado):
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    tmp = ESTADO.with_suffix(".tmp")
    tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(ESTADO)


def executar():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Apenas ler, sem postar nem registrar.")
    args = parser.parse_args()
    agora = datetime.now(timezone.utc)
    posts = pagina_publica()
    estado = ler_estado()
    if estado is None:
        print(f"Inicializacao: {len(posts)} mensagens atuais marcadas como historicas.")
        if not args.dry_run:
            salvar_estado({"iniciado_em":agora.isoformat(),
                           "vistos":{str(x["id"]):agora.isoformat() for x in posts},
                           "ultima_consulta":agora.isoformat()})
        return

    vistos = estado["vistos"]
    novos = [p for p in posts if str(p["id"]) not in vistos]
    print(f"Mensagens visiveis: {len(posts)}; novas: {len(novos)}.")
    if args.dry_run:
        print("SIMULACAO: nenhuma mensagem enviada.")
        return
    if not novos:
        return

    # Consultar API apenas quando houver mensagens novas (economiza chamadas).
    recentes = [
        p for p in novos if (d := data_utc(p.get("data")))
        and timedelta(0) <= agora - d <= MAX_INTERVALO
    ]
    for p in novos:
        if p not in recentes:
            vistos[str(p["id"])] = agora.isoformat()
    if not recentes:
        estado["ultima_consulta"] = agora.isoformat()
        salvar_estado(estado)
        return
    marcas = buscar_anunciantes()
    enviados = 0
    for post in recentes:
        if enviados >= MAX_POSTS:
            break
        id_ = str(post["id"])
        dados = extrair(post, marcas)
        if not dados:
            print("Mensagem ignorada (anunciante ou link sem correspondencia):", id_)
            vistos[id_] = agora.isoformat()
            continue
        link = link_solgarimpa(dados["organizacao"], dados["destino"])
        if not link:
            print("Nenhum link afiliado autorizado para a mensagem", id_)
            # Tentar novamente no proximo ciclo: talvez seja indisponibilidade temporaria.
            continue
        try:
            formato = enviar_oferta(
                os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
                CANAL_DESTINO, mensagem(dados, link), dados["imagem"]
            )
        except (RuntimeError, URLError, TimeoutError):
            print("Falha no envio; verificar o Telegram antes de tentar novamente:", id_)
            continue
        vistos[id_] = agora.isoformat()
        enviados += 1
        print("Publicado com", formato, "mensagem:", id_, dados["loja"])
    limite = agora - timedelta(days=90)
    estado["vistos"] = {
        k:v for k,v in vistos.items()
        if (dt := data_utc(v)) and dt >= limite
    }
    estado["ultima_consulta"] = agora.isoformat()
    salvar_estado(estado)


if __name__ == "__main__":
    try:
        executar()
    except Exception as exc:
        print("Monitor Lomadee:", str(exc), file=sys.stderr)
        raise SystemExit(1)
