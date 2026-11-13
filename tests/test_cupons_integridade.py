"""Testes offline: nenhum voucher inventado, promocao Rakuten com/sem codigo."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_rakuten import coupon_from_xml
from build_cupons_central import normalizar
from sync_cupons_marketplaces import actual_code, record


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


if __name__ == "__main__":
    unittest.main()
