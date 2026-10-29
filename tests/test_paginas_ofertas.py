"""Testes do catálogo de páginas — executados sem rede e sem credenciais."""
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_paginas_ofertas", ROOT / "scripts" / "build_paginas_ofertas.py"
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class TestPaginasOfertas(unittest.TestCase):
    def setUp(self):
        self.agora = datetime.now(timezone.utc)

    def card(self, **extras):
        item = {
            "id": "produto-1", "tipo": "produto", "loja": "Loja de teste",
            "titulo": "Produto de teste",
            "link": "https://example.com/afiliado?publisher=sol",
            "preco": 59.90, "preco_anterior": 120.00,
        }
        item.update(extras)
        return item

    def test_link_rastreado_preservado(self):
        card = self.card()
        saida = mod.normalizar("Rakuten", card, self.agora)
        self.assertEqual(saida["link"], card["link"])
        self.assertTrue(saida["url_sol_garimpa"].startswith(
            "https://www.ofertaspravc.com.br/oferta/rakuten-"
        ))

    def test_oferta_vencida_rejeitada(self):
        vencido = (self.agora - timedelta(minutes=5)).isoformat()
        self.assertIsNone(mod.normalizar(
            "Lomadee", self.card(validade=vencido), self.agora
        ))

    def test_nao_converter_moeda_estrangeira_em_reais(self):
        saida = mod.normalizar("Rakuten", self.card(moeda="USD"), self.agora)
        self.assertEqual(saida["moeda"], "USD")
        self.assertIsNone(saida["preco"])
        self.assertIsNone(saida["preco_anterior"])

    def test_descarta_http_e_links_sem_titulo(self):
        self.assertIsNone(mod.normalizar(
            "Awin", self.card(link="http://example.com"), self.agora
        ))
        self.assertIsNone(mod.normalizar(
            "Awin", self.card(titulo=""), self.agora
        ))

    def test_desatualizado_duplicado_e_tres_redes(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            origens = {}
            for rede in ("Awin", "Rakuten", "Lomadee"):
                destino = raiz / (rede + ".json")
                atualizado = (
                    self.agora - timedelta(days=4)
                    if rede == "Awin" else self.agora
                )
                cards = [self.card(), self.card()]
                destino.write_text(json.dumps({
                    "atualizado_em": atualizado.isoformat(),
                    "cards": cards,
                }), encoding="utf-8")
                origens[rede] = destino
            saida = raiz / "saida.json"
            with patch.object(mod, "FONTES", origens), patch.object(
                mod, "OUTPUT", saida
            ):
                mod.gerar()
            dados = json.loads(saida.read_text(encoding="utf-8"))
            self.assertEqual(dados["total"], 2)
            self.assertEqual(len(dados["cards"]), 2)
            self.assertEqual(dados["redes"]["Awin"], "desatualizado")
            self.assertEqual(dados["redes"]["Rakuten"], 1)
            self.assertEqual(dados["redes"]["Lomadee"], 1)


if __name__ == "__main__":
    unittest.main()
