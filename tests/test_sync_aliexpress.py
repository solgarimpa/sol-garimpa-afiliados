"""Testes offline para a vitrine AliExpress; nao usam credenciais."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "scripts" / "sync_aliexpress.py"
spec = importlib.util.spec_from_file_location("sync_aliexpress", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class AliExpressTests(unittest.TestCase):
    def test_signature_consistente(self):
        params = {"method": "m", "app_key": "123", "timestamp": "x"}
        self.assertEqual(mod.sign_top(params, "secret"), mod.sign_top(dict(reversed(list(params.items()))), "secret"))
        self.assertEqual(len(mod.sign_top(params, "secret")), 32)

    def test_bloqueia_urls_que_voltam_ao_wix(self):
        self.assertEqual(mod.promotional_url("https://www.ofertaspravc.com.br/aliexpress"), "")
        self.assertEqual(mod.promotional_url("https://s.click.aliexpress.com.evil.tld/e/123"), "")
        self.assertEqual(mod.promotional_url("javascript:alert(1)"), "")

    def test_aceita_url_promocional_individual(self):
        self.assertEqual(mod.promotional_url("https://s.click.aliexpress.com/e/_teste"), "https://s.click.aliexpress.com/e/_teste")
        self.assertEqual(mod.promotional_url("http://s.click.aliexpress.com/e/_teste"), "https://s.click.aliexpress.com/e/_teste")

    def test_so_publica_produto_com_link_da_api(self):
        def api(method, extra, app_key, app_secret):
            return {"products": {"product": [{
                "product_id": "123456789",
                "product_title": "Organizador de teste",
                "product_main_image_url": "https://ae01.alicdn.com/kf/a.jpg",
                "promotion_link": "https://s.click.aliexpress.com/e/_teste",
                "target_sale_price": "39.95",
                "target_sale_price_currency": "BRL",
            }]}}
        with patch.object(mod, "request_api", side_effect=api):
            products, errors = mod.collect("key", "secret", "default")
        self.assertFalse(errors)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["preco"], 39.95)
        self.assertEqual(products[0]["link"], "https://s.click.aliexpress.com/e/_teste")

    def test_falha_sem_links_validos(self):
        with patch.object(mod, "request_api", return_value={"products": {"product": [{
            "product_id": "123", "product_title": "Test",
            "product_main_image_url": "https://ae01.alicdn.com/kf/a.jpg",
            "promotion_link": "https://www.ofertaspravc.com.br/aliexpress",
            "product_detail_url": "https://www.ofertaspravc.com.br/aliexpress",
        }]}}):
            with self.assertRaises(RuntimeError):
                mod.collect("key", "secret", "default")

if __name__ == "__main__":
    unittest.main()
