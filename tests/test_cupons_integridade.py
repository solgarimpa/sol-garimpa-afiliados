"""Testes offline: nenhum voucher inventado, promocao Rakuten com/sem codigo."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_rakuten import coupon_from_xml
from build_cupons_central import normalizar
from sync_cupons_marketplaces import actual_code, record, process, MARKETS, NOW, amazon_official_url, parse_amazon_manual


class CupomIntegridade(unittest.TestCase):
    def test_rakuten_codigo_real_mantido(self):
        xml = ET.fromstring("""
        <link><advertiserid>88</advertiserid>
        <offerdescription>Desconto para compradores</offerdescription>
        <clickurl>https://click.linksynergy.com/deeplink?id=88</clickurl>
        <couponcode>ECONOMIZE10</couponcode>
        <couponrestriction>Pedido minimo de R$ 100</couponrestriction>
        <offerenddate>2099-01-01T00:00Z</offerenddate></link>""")
        item = coupon_from_xml(xml, {"88": {"loja": "Loja Teste"}})
        self.assertEqual(item["tipo"], "cupom")
        self.assertEqual(item["cupom"], "ECONOMIZE10")
        self.assertEqual(item["descricao"], "Pedido minimo de R$ 100")
        agregado = normalizar(item, "Rakuten", datetime.now(timezone.utc))
        self.assertEqual(agregado["cupom"], "ECONOMIZE10")

    def test_rakuten_promocao_sem_codigo_nao_vira_voucher(self):
        xml = ET.fromstring("""
        <link><advertiserid>88</advertiserid>
        <offerdescription>Desconto aplicado no carrinho</offerdescription>
        <clickurl>https://click.linksynergy.com/deeplink?id=88</clickurl>
        <offerenddate>2099-01-01T00:00Z</offerenddate></link>""")
        item = coupon_from_xml(xml, {"88": {"loja": "Loja Teste"}})
        self.assertEqual(item["tipo"], "promocao")
        self.assertEqual(item["cupom"], "")
        agregado = normalizar(item, "Rakuten", datetime.now(timezone.utc))
        self.assertEqual(agregado["tipo"], "promocao")

    def test_placeholder_do_worker_nao_vira_codigo(self):
        item = record("Cupom Amazon 35% de desconto", "OFERTANOLINK", "",
                      "Worker existente", "https://exemplo.com")
        self.assertIsNotNone(item)
        self.assertEqual(item["couponCode"], "")
        self.assertEqual(actual_code("OFERTANOLINK Copiar"), "")

    def test_codigo_valido_nao_e_removido(self):
        item = record("Cupom Shopee R$ 20 OFF", "TESTE20", "",
                      "Meliuz", "https://exemplo.com")
        self.assertEqual(item["couponCode"], "TESTE20")

    def test_origem_do_cupom_preservada_no_json_sem_exibir_fonte(self):
        origem = "https://www.meliuz.com.br/desconto/cupom-ifood"
        item = record("Cupom iFood 10% de desconto", "TESTE1234", "", "Meliuz", origem)
        self.assertIsNotNone(item)
        with TemporaryDirectory() as pasta:
            with patch("sync_cupons_marketplaces.OUTPUT", Path(pasta)), \
                 patch("sync_cupons_marketplaces.parse_site", return_value=[item]), \
                 patch("sync_cupons_marketplaces.parse_worker", return_value=[]), \
                 patch("sync_cupons_marketplaces.parse_seletronic_ifood", return_value=[]):
                self.assertTrue(process("ifood", MARKETS["ifood"]))
            dados = json.loads((Path(pasta) / "ifood-cupons.json").read_text(encoding="utf-8"))
            self.assertEqual(dados["coupons"][0]["sourceUrl"], origem)
            self.assertEqual(dados["coupons"][0]["sources"], [])

    def test_textos_de_botao_nao_viram_codigos_amazon(self):
        for placeholder in ("CUPOMAUTOMATICO", "PROMONOLINK", "PEGUEAQUI",
                            "CONFIRANOLINK", "GANHEAQUI", "ATIVEAPROMO",
                            "APROVEITEAQUI", "DESCONTOJAATIVO", "CLIQUEEGANHE"):
            with self.subTest(placeholder=placeholder):
                item = record("Desconto Amazon de 10% para produtos", placeholder,
                              "Confira as condições", "Meliuz", "https://exemplo.com")
                self.assertEqual(item["couponCode"], "")

    def test_amazon_sem_codigo_quando_desconto_resgatado_no_produto(self):
        item = record("Cupom Amazon R$ 50 OFF", "CUPOMPS5",
                      "Não é necessário inserir código, basta ativar no produto.",
                      "Meliuz", "https://exemplo.com")
        self.assertEqual(item["couponCode"], "")

    def test_link_especifico_so_aceita_amazon_brasil(self):
        self.assertTrue(amazon_official_url("https://www.amazon.com.br/dp/B012345678"))
        for url in ("https://www.amazon.com.br.evil.example/dp/B01",
                    "https://www.meliuz.com.br/desconto/amazon",
                    "http://www.amazon.com.br/dp/B01",
                    "https://www.amazon.com.br/"):
            self.assertEqual(amazon_official_url(url), "")

    def test_cadastro_manual_exibe_link_amazon_sem_alegar_validacao(self):
        with TemporaryDirectory() as pasta:
            destino = Path(pasta) / "docs" / "central"
            destino.mkdir(parents=True)
            (destino / "amazon-ofertas-oficiais.json").write_text(
                json.dumps({"offers": [{
                    "title": "Oferta Amazon R$ 20 OFF em produtos selecionados",
                    "couponCode": "TESTE20",
                    "description": "Oferta localizada no site oficial",
                    "checkedAt": NOW.isoformat(),
                    "offerUrl": "https://www.amazon.com.br/dp/B012345678"
                }]}), encoding="utf-8")
            with patch("sync_cupons_marketplaces.ROOT", Path(pasta)):
                items = parse_amazon_manual()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["status"], "unverified")
        self.assertEqual(items[0]["offerUrl"], "https://www.amazon.com.br/dp/B012345678")


if __name__ == "__main__":
    unittest.main()
