"""Testes locais do monitor da planilha Rakuten. Nenhuma chamada externa."""
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import monitor_planilha_rakuten as m


class MonitorPlanilhaRakutenTests(unittest.TestCase):
    def test_rejeita_url_de_afiliado_alheio_e_url_privada(self):
        self.assertEqual(m.url_loja("https://click.linksynergy.com/deeplink?id=abc"), "")
        self.assertEqual(m.url_loja("https://127.0.0.1/abc"), "")
        self.assertEqual(m.url_loja("http://www.netshoes.com.br/p/abc"), "")
        self.assertEqual(m.url_loja("https://www.netshoes.com.br/p/abc"),
                         "https://www.netshoes.com.br/p/abc")

    def test_planilha_nao_publica_promocao_vencida(self):
        agora = datetime(2026, 10, 31, 12, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
        linhas = {
            "Ofertas": [["30/10/2026", "Netshoes", "Produto", "Tenis", "R$ 300",
                         "R$ 199", "33%", "30/10/2026", "https://www.netshoes.com.br/p/abc"]],
            "Cupons": [],
            "Lançamentos": [],
        }
        with patch.object(m, "baixar_aba", side_effect=lambda aba, gid, cols: linhas[aba]):
            r = m.linhas_ofertas(agora)
        self.assertEqual(len(r), 1)
        self.assertFalse(r[0]["elegivel"])

    def test_planilha_nova_oferta_valida(self):
        agora = datetime(2026, 10, 31, 12, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
        linhas = {
            "Ofertas": [["31/10/2026", "Netshoes", "Produto", "Tenis", "R$ 300",
                         "R$ 199", "33%", "02/11/2026", "https://www.netshoes.com.br/p/abc"]],
            "Cupons": [],
            "Lançamentos": [],
        }
        with patch.object(m, "baixar_aba", side_effect=lambda aba, gid, cols: linhas[aba]):
            r = m.linhas_ofertas(agora)
        self.assertEqual(len(r), 1)
        self.assertTrue(r[0]["elegivel"])
        self.assertEqual(r[0]["loja"], "Netshoes")

    def test_deep_link_apenas_oficial(self):
        valido = {"advertiser": {"deep_link": {
            "deep_link_url": "https://click.linksynergy.com/deeplink?id=teste"}}}
        with patch.object(m, "rakuten_request", return_value=json.dumps(valido).encode()):
            self.assertTrue(m.gerar_link("token", "43984", "https://www.netshoes.com.br/p/abc", "abc"))
        invalido = {"advertiser": {"deep_link": {
            "deep_link_url": "https://outro.example/afiliado"}}}
        with patch.object(m, "rakuten_request", return_value=json.dumps(invalido).encode()):
            self.assertEqual(m.gerar_link("token", "43984", "https://www.netshoes.com.br/p/abc", "abc"), "")

    def test_primeira_execucao_so_cria_linha_de_base(self):
        with tempfile.TemporaryDirectory() as pasta:
            item = {"id": "teste123", "elegivel": True}
            with (patch.object(m, "STATE_PATH", Path(pasta) / "vistos.json"),
                  patch.object(m, "linhas_ofertas", return_value=[item]),
                  patch.object(m, "make_access_token", side_effect=AssertionError("nao usar API")),
                  patch.object(m, "publicar", side_effect=AssertionError("nao publicar")),
                  patch.object(sys, "argv", ["monitor_planilha_rakuten.py"])):
                m.main()
                dados = json.loads(m.STATE_PATH.read_text())
            self.assertIn("teste123", dados["vistos"])


if __name__ == "__main__":
    unittest.main()
