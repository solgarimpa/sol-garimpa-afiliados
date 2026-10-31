"""Testa envio com foto e fallback, sem acessar Telegram ou Rakuten."""
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, call
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import telegram_imagens as im
import monitor_planilha_rakuten as mr
import postar_telegram as pt


class TelegramImagensTests(unittest.TestCase):
    def test_sendphoto_quando_tem_imagem(self):
        with patch.object(im, "requisitar", return_value={"ok": True}) as req:
            modo = im.enviar_oferta("token_privado", "@solgarimpaofertas",
                                   "<b>Oferta</b> https://exemplo.com.br",
                                   "https://static.nike.com/produto.jpg")
        self.assertEqual(modo, "foto")
        self.assertEqual(req.call_count, 1)
        self.assertEqual(req.call_args.args[1], "sendPhoto")
        self.assertEqual(req.call_args.args[2]["photo"], "https://static.nike.com/produto.jpg")
        self.assertIn("Oferta", req.call_args.args[2]["caption"])

    def test_sem_imagem_continua_publicando_texto(self):
        with patch.object(im, "requisitar", return_value={"ok": True}) as req:
            modo = im.enviar_oferta("token_privado", "@solgarimpaofertas",
                                   "<b>Oferta</b>", "")
        self.assertEqual(modo, "texto")
        self.assertEqual(req.call_args.args[1], "sendMessage")

    def test_url_interna_recusada(self):
        self.assertEqual(im.imagem_publica("https://127.0.0.1/imagem.jpg"), "")
        self.assertEqual(im.imagem_publica("http://cdn.example.com/img.jpg"), "")
        self.assertEqual(im.imagem_publica("https://cdn.example.com/produto.jpg"),
                         "https://cdn.example.com/produto.jpg")

    def test_fallback_se_telegram_rejeita_foto(self):
        erro = HTTPError("https://api.telegram.org", 400, "Bad Request", {}, None)
        with patch.object(im, "requisitar", side_effect=[erro, {"ok": True}]) as req:
            modo = im.enviar_oferta("token_privado", "@solgarimpaofertas", "Oferta",
                                   "https://cdn.example.com/produto.jpg")
        self.assertEqual(modo, "texto")
        self.assertEqual([c.args[1] for c in req.call_args_list],
                         ["sendPhoto", "sendMessage"])

    def test_erro_incerto_nao_gera_segundo_envio(self):
        erro = HTTPError("https://api.telegram.org", 503, "Service Unavailable", {}, None)
        with patch.object(im, "requisitar", side_effect=erro) as req:
            with self.assertRaises(RuntimeError):
                im.enviar_oferta("token_privado", "@solgarimpaofertas", "Oferta",
                                "https://cdn.example.com/produto.jpg")
        self.assertEqual(req.call_count, 1)

    def test_publicador_pega_imagem_do_card(self):
        agora = datetime(2026, 10, 31, 12, tzinfo=ZoneInfo("America/Sao_Paulo"))
        data = {
            "gerado_em": agora.isoformat(),
            "cards": [{
                "id": "produto1", "slug": "rakuten-abc", "historico": False,
                "rede": "Rakuten", "tipo": "produto", "loja": "Nike BR",
                "titulo": "Meia Nike", "link": "https://click.linksynergy.com/deeplink?id=123",
                "imagem": "https://static.nike.com/meia.jpg",
                "moeda": "BRL", "preco": 49.99, "preco_anterior": 149.99,
                "ultima_confirmacao": agora.isoformat(),
            }]
        }
        resultado = pt.selecionar(data, set(), agora)
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado[1]["imagem"], "https://static.nike.com/meia.jpg")

    def test_planilha_usa_imagem_estritamente_correspondente(self):
        agora = datetime(2026, 10, 31, 12, tzinfo=ZoneInfo("America/Sao_Paulo"))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "docs"
            p.mkdir()
            (p / "paginas_ofertas.json").write_text(json.dumps({
                "gerado_em": agora.isoformat(),
                "cards": [{
                    "loja": "Nike BR", "titulo": "Meia Nike", "historico": False,
                    "imagem": "https://static.nike.com/meia.jpg"
                }, {
                    "loja": "Nike BR", "titulo": "Outro produto", "historico": False,
                    "imagem": "https://static.nike.com/outra.jpg"
                }]
            }), encoding="utf-8")
            with patch.object(mr, "ROOT", Path(d)):
                result = mr.imagens_do_catalogo(agora)
        self.assertEqual(result[("nikebr", "meianike")],
                         "https://static.nike.com/meia.jpg")
        self.assertNotIn(("outro", "meianike"), result)


if __name__ == "__main__":
    unittest.main()
