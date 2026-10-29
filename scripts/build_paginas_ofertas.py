
#!/usr/bin/env python3
"""SOL GARIMPA — catálogo das páginas individuais."""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "paginas_ofertas.json"
LIMITE = int(os.getenv("SG_MAX_POR_REDE", "300"))

FONTES = {
    "Awin": ROOT / "docs" / "ofertas.json",
    "Rakuten": ROOT / "docs" / "rakuten" / "ofertas.json",
    "Lomadee": ROOT / "docs" / "lomadee" / "ofertas.json",
}

def data_hora(valor):
    if not isinstance(valor, str) or not valor:
        return None
    try:
        d = datetime.fromisoformat(
            valor.replace("Z", "+00:00")
        )
        if not d.tzinfo:
            return None
        return d.astimezone(timezone.utc)
    except ValueError:
        return None

def url_segura(valor):
    try:
        u = urlsplit(str(valor or "").strip())
        host = (u.hostname or "").lower()
        if u.scheme != "https" or not host:
            return ""
        if u.username or u.password:
            return ""
        if host in ("localhost", "127.0.0.1"):
            return ""
        if host.endswith(".local"):
            return ""
        return u.geturl()
    except (ValueError, TypeError):
        return ""

def texto(valor, maximo):
    return " ".join(str(valor or "").split())[:maximo]

def preco(valor):
    if isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
        if 0 < numero < 100000000:
            return round(numero, 2)
    except (TypeError, ValueError, OverflowError):
        pass
    return None

def normalizar(rede, item, agora):
    if not isinstance(item, dict):
        return None

    if item.get("tipo") not in (
        "produto", "promocao", "cupom"
    ):
        return None

    titulo = texto(item.get("titulo"), 180)
    loja = texto(item.get("loja"), 100)
    link = url_segura(item.get("link"))

    if not titulo or not loja or not link:
        return None

    validade = data_hora(item.get("validade"))
    if item.get("validade") and not validade:
        return None
    if validade and validade <= agora:
        return None

    identificador = texto(
        item.get("id") or link, 500
    )
    codigo = hashlib.sha256(
        (rede + ":" + identificador).encode()
    ).hexdigest()[:20]
    slug = rede.lower() + "-" + codigo

    valor = preco(item.get("preco"))
    anterior = preco(item.get("preco_anterior"))

    return {
        "slug": slug,
        "rede": rede,
        "tipo": item["tipo"],
        "titulo": titulo,
        "loja": loja,
        "imagem": url_segura(item.get("imagem")),
        "preco": valor,
        "preco_anterior": (
            anterior
            if valor and anterior and anterior > valor
            else None
        ),
        "cupom": texto(item.get("cupom"), 80),
        "descricao": texto(
            item.get("descricao"), 350
        ),
        "validade": (
            validade.isoformat() if validade else None
        ),
        "link": link,
        "url_sol_garimpa": (
            "https://www.ofertaspravc.com.br/oferta/"
            + slug
        )
    }

def gerar():
    agora = datetime.now(timezone.utc)
    ofertas = []
    status = {}

    for rede, arquivo in FONTES.items():
        try:
            dados = json.loads(
                arquivo.read_text(encoding="utf-8")
            )
            atualizado = data_hora(
                dados.get("atualizado_em")
            )

            if (
                not atualizado
                or atualizado > agora
                or (agora - atualizado).total_seconds()
                > 48 * 3600
            ):
                status[rede] = "desatualizado"
                continue

            vistos = set()
            quantidade = 0

            for original in dados.get("cards", []):
                item = normalizar(
                    rede, original, agora
                )
                if not item:
                    continue
                if item["slug"] in vistos:
                    continue

                vistos.add(item["slug"])
                ofertas.append(item)
                quantidade += 1

                if quantidade >= LIMITE:
                    break

            status[rede] = quantidade

        except (OSError, ValueError, TypeError):
            status[rede] = "erro_na_fonte"

    resultado = {
        "gerado_em": agora.isoformat(),
        "total": len(ofertas),
        "redes": status,
        "cards": ofertas
    }

    OUTPUT.parent.mkdir(
        parents=True, exist_ok=True
    )
    OUTPUT.write_text(
        json.dumps(
            resultado,
            ensure_ascii=False,
            separators=(",", ":")
        ) + "\n",
        encoding="utf-8"
    )

    print("Ofertas preparadas:", len(ofertas))
    print("Redes:", status)

if __name__ == "__main__":
    gerar()
