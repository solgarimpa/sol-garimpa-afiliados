#!/usr/bin/env python3
"""SOL GARIMPA: audita estrutura dos links sem gerar cliques artificiais.

Confere protocolo, dominio de rastreamento, identificador do afiliado
e macros pendentes nos catalogos Awin, Rakuten, Lomadee e paginas individuais.
Nao faz requisicoes a URLs de afiliados: uma auditoria estrutural nao
comprova disponibilidade final, comissao ou ausencia de bloqueio HTTP.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
FONTES = {
    "Awin": ROOT / "docs" / "ofertas.json",
    "Rakuten": ROOT / "docs" / "rakuten" / "ofertas.json",
    "Lomadee": ROOT / "docs" / "lomadee" / "ofertas.json",
    "Paginas": ROOT / "docs" / "paginas_ofertas.json",
}
AWIN_PUBLISHER = "3110826"
MACRO = re.compile(
    r"\[(?:ld_site_id|site_id|affiliate_id|publisher_id)\]",
    flags=re.IGNORECASE,
)


def macro_nao_resolvida(url: str) -> bool:
    texto = url
    for _ in range(4):
        novo = unquote(texto)
        if novo == texto:
            break
        texto = novo
    return MACRO.search(texto) is not None


def problema(link: object, rede: str) -> str | None:
    if not isinstance(link, str) or not link:
        return "sem_link"
    try:
        u = urlsplit(link)
        if u.scheme != "https" or not u.hostname or u.username or u.password:
            return "url_nao_https"
        host = u.hostname.lower()
        params = parse_qs(u.query, keep_blank_values=True)
    except (ValueError, TypeError):
        return "url_malformada"
    if macro_nao_resolvida(link):
        return "macro_de_afiliado_nao_resolvida"
    if rede == "Awin":
        if host != "www.awin1.com":
            return "dominio_awin_inesperado"
        if AWIN_PUBLISHER not in (
            params.get("a", []) + params.get("awinaffid", [])
        ):
            return "id_awin_ausente_ou_divergente"
        if not (params.get("m") or params.get("awinmid")):
            return "anunciante_awin_ausente"
    elif rede == "Rakuten":
        if host != "click.linksynergy.com":
            return "dominio_rakuten_inesperado"
        if not params.get("id") or not params.get("offerid"):
            return "id_ou_oferta_rakuten_ausente"
    elif rede == "Lomadee":
        if host != "lmdee.link":
            return "dominio_lomadee_inesperado"
        if not u.path.strip("/"):
            return "slug_lomadee_ausente"
    else:
        return "rede_desconhecida"
    return None


def auditar() -> int:
    falhas = []
    contagem = Counter()
    rede_contagem = Counter()
    for fonte, arquivo in FONTES.items():
        try:
            d = json.loads(arquivo.read_text(encoding="utf-8"))
            cards = d.get("cards")
            if not isinstance(cards, list):
                raise ValueError("cards ausentes ou invalidos")
        except (OSError, ValueError, TypeError) as exc:
            falhas.append({"fonte": fonte, "erro": type(exc).__name__})
            continue
        for p in cards:
            if not isinstance(p, dict) or p.get("tipo") == "sem_oferta":
                continue
            rede = p.get("rede") if fonte == "Paginas" else fonte
            rede_contagem[str(rede)] += 1
            contagem[fonte] += 1
            erro = problema(p.get("link"), str(rede))
            if erro:
                falhas.append({
                    "fonte": fonte,
                    "loja": str(p.get("loja") or "")[:70],
                    "id": str(p.get("id") or p.get("slug") or "")[:90],
                    "erro": erro,
                })
    print("SOL GARIMPA - auditoria de rastreamento (sem acessar os links)")
    print("Itens auditados:", dict(contagem))
    print("Por rede (incluindo paginas):", dict(rede_contagem))
    print("Inconsistencias:", len(falhas))
    for item in falhas[:30]:
        print(json.dumps(item, ensure_ascii=False))
    if len(falhas) > 30:
        print(f"... e mais {len(falhas)-30} registros.")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(auditar())
