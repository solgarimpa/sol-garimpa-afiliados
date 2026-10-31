"""Testes isolados do monitor do canal publico Lomadee."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import monitor_canal_lomadee as m


AMOSTRA = """
<html><body>
<div class="tgme_widget_message_wrap js-widget_message_wrap">
  <div class="tgme_widget_message js-widget_message" data-post="ofertaslomadee/1201">
    <a class="tgme_widget_message_photo_wrap" style="background-image:url('https://cdn1.telesco.pe/file/foto.jpg');"></a>
    <div class="tgme_widget_message_text js-message_text" dir="auto">
      <b>Lojas Rede</b><br>
      Saldão de beleza com até 59% off🔥<br>
      Não esqueça de gerar seu link na plataforma Lomadee<br>
      <a href="https://www.lojasrede.com.br/3422?map=abc">https://www.lojasrede.com.br/3422</a>
    </div>
    <div class="tgme_widget_message_footer"><time datetime="2026-10-31T12:50:00+00:00">09:50</time></div>
  </div>
</div>
<div class="tgme_widget_message_wrap">
  <div class="tgme_widget_message" data-post="ofertaslomadee/1202">
    <div class="tgme_widget_message_text">
      <b>Gazin</b><br>Lava e Seca em oferta<br>
      https://www.gazin.com.br/produto/abc
    </div>
    <time datetime="2026-10-31T13:00:00+00:00">10:00</time>
  </div>
</div>
</body></html>
"""


class MonitorLomadeeTests(unittest.TestCase):
    def test_parser_extrai_separadamente_e_guarda_imagem(self):
        p = m.MensagensTelegram()
        p.feed(AMOSTRA)
        self.assertEqual([x["id"] for x in p.mensagens], [1201, 1202])
        self.assertIn("Saldão de beleza", p.mensagens[0]["texto"])
        self.assertIn("https://www.lojasrede.com.br/3422", p.mensagens[0]["links"][0])
        self.assertIn("foto.jpg", p.mensagens[0]["foto"])
        self.assertEqual(p.mensagens[0]["data"], "2026-10-31T12:50:00+00:00")

    def test_nao_repassa_link_de_terceiros(self):
        self.assertEqual(m.loja_url("https://lmdee.link/abc"), "")
        self.assertEqual(m.loja_url("https://app.lomadee.com.br/brands/xyz"), "")
        self.assertEqual(m.loja_url("https://127.0.0.1/teste"), "")
        self.assertEqual(m.loja_url("https://www.lojasrede.com.br/p/teste"),
                         "https://www.lojasrede.com.br/p/teste")

    def test_identifica_loja_e_descricao(self):
        parser = m.MensagensTelegram()
        parser.feed(AMOSTRA)
        dados = m.extrair(parser.mensagens[0], {"lojasrede": [("123","Lojas Rede")]})
        self.assertEqual(dados["loja"], "Lojas Rede")
        self.assertEqual(dados["organizacao"], "123")
        self.assertEqual(dados["titulo"], "Saldão de beleza com até 59% off🔥")
        self.assertEqual(dados["destino"], "https://www.lojasrede.com.br/3422?map=abc")

    def test_sem_parceria_nao_publica(self):
        parser = m.MensagensTelegram()
        parser.feed(AMOSTRA)
        self.assertIsNone(m.extrair(parser.mensagens[0], {}))

    def test_api_tem_de_retornar_link_solgarimpa(self):
        resposta = {"data": [{"id": "canal", "name": "Sol Garimpa",
                              "shortUrls": ["https://lmdee.link/propria"]}]}
        with patch.object(m.lomadee, "request", return_value=resposta):
            with patch.object(m.lomadee, "CHANNEL_ID", ""):
                self.assertEqual(
                    m.link_solgarimpa("123", "https://www.lojasrede.com.br/p/abc"),
                    "https://lmdee.link/propria"
                )
        with patch.object(m.lomadee, "request", return_value={"data": []}):
            self.assertEqual(m.link_solgarimpa("123", "https://www.lojasrede.com.br/p/abc"), "")

    def test_primeiro_ciclo_cria_baseline_sem_publicar(self):
        parser = m.MensagensTelegram()
        parser.feed(AMOSTRA)
        with tempfile.TemporaryDirectory() as pasta:
            local = Path(pasta) / "historico.json"
            with (patch.object(m, "ESTADO", local),
                  patch.object(m, "pagina_publica", return_value=parser.mensagens),
                  patch.object(m, "buscar_anunciantes", side_effect=AssertionError("sem API")),
                  patch.object(m, "enviar_oferta", side_effect=AssertionError("nao enviar")),
                  patch.object(sys, "argv", ["monitor_canal_lomadee.py"])):
                m.executar()
            data = json.loads(local.read_text())
            self.assertEqual(len(data["vistos"]), 2)
            self.assertIn("1201", data["vistos"])


if __name__ == "__main__":
    unittest.main()
