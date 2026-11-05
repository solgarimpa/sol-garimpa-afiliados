"""Testes sem credenciais das fontes complementares oficiais."""
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from segunda_camada import awin_store_links, https_url, rakuten_creatives


class TestSegundaCamada(unittest.TestCase):
    def test_rakuten_link_locator_criativo_valido(self):
        xml = b"""<getTextLinksResponse xmlns="http://example.com/ns">
          <return><mid>88</mid><linkID>2</linkID>
            <textDisplay>Campanha Oficial</textDisplay>
            <clickURL>https://click.linksynergy.com/deeplink?id=abc</clickURL>
            <startDate>11012026</startDate><endDate>12312026</endDate>
          </return></getTextLinksResponse>"""
        calls = []

        def request(path, token):
            self.assertEqual(token, "token")
            calls.append(path)
            return xml if "getTextLinks" in path else b"<getBannerLinksResponse/>"

        items, warnings = rakuten_creatives(
            "token", {"mid": "88", "loja": "Loja Teste"}, request,
            lambda *p: "-".join(p),
            now=datetime(2026, 11, 5, tzinfo=timezone.utc)
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["titulo"], "Campanha Oficial")
        self.assertEqual(items[0]["tipo"], "promocao")
        self.assertIsNone(items[0]["preco"])
        self.assertEqual(items[0]["origem"], "rakuten_link_locator")
        self.assertIn("getTextLinks/88/-1///-1/1", calls[0])
        self.assertFalse(warnings)

    def test_rakuten_recusa_expirado_sem_link(self):
        xml = b"""<getTextLinksResponse>
          <return><mid>3</mid><linkName>Antigo</linkName>
          <clickURL>https://click.linksynergy.com/x</clickURL>
          <endDate>01012025</endDate></return>
          <return><mid>3</mid><linkName>Inseguro</linkName>
          <clickURL>http://example.com</clickURL></return>
        </getTextLinksResponse>"""

        def request(path, token):
            return xml if "getTextLinks" in path else b"<getBannerLinksResponse/>"

        cards, _ = rakuten_creatives(
            "x", {"mid": "3", "loja": "Outra"}, request,
            lambda *args: "test",
            now=datetime(2026, 11, 5, tzinfo=timezone.utc)
        )
        self.assertEqual(cards, [])
        self.assertIsNone(https_url("https://fake.com@evil.com"))
        self.assertIsNone(https_url("javascript:alert(1)"))

    def test_awin_so_retorna_links_rastreaveis_aprovados(self):
        def request(url, method, token, body, timeout):
            self.assertEqual(method, "POST")
            self.assertIn("generate-batch", url)
            self.assertEqual(body["requests"], [
                {"advertiserId": 42}, {"advertiserId": 43}
            ])
            return io.BytesIO(json.dumps({
                "responses": [
                    {"status": 200, "body": {
                        "request": {"advertiserId": 42},
                        "url": "https://www.awin1.com/cread.php?awinmid=42"
                    }},
                    {"status": 200, "body": {
                        "request": {"advertiserId": 43},
                        "url": "https://loja.com/sem-tracking"
                    }}
                ]
            }).encode("utf-8"))

        def tracking(url, tracking=False):
            if not tracking:
                return ""
            from urllib.parse import urlparse
            u = urlparse(url)
            return url if u.hostname == "www.awin1.com" else ""

        links = awin_store_links(
            "token", [("Loja 1", 42), ("Loja 2", 43), ("Invalida", None)],
            request, 3110826, tracking
        )
        self.assertEqual(set(links), {"Loja 1"})
        self.assertIn("awinmid=42", links["Loja 1"])


if __name__ == "__main__":
    unittest.main()
