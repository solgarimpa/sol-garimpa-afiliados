"""Revezamento das 3 redes, com dados artificiais e nenhuma chamada externa."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import postar_telegram as p

AGORA = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)


def card(rede, titulo, preco=100, anterior=None):
    return {
        "rede": rede, "historico": False, "tipo": "produto",
        "slug": rede.lower() + "-" + titulo.lower().replace(" ", "-"),
        "titulo": titulo, "loja": "Loja " + rede,
        "link": "https://www.exemplo.com.br/" + rede.lower(),
        "imagem": "https://cdn.exemplo.com.br/" + rede.lower() + ".jpg",
        "moeda": "BRL", "preco": preco,
        "preco_anterior": anterior, "ultima_confirmacao": AGORA.isoformat(),
        "validade": None,
    }


class PublicarTelegramRedesTests(unittest.TestCase):
    def setUp(self):
        self.catalogo = {
            "gerado_em": AGORA.isoformat(),
            "cards": [
                card("Rakuten", "Oferta alta", 10, 100),
                card("Awin", "Oferta media", 50, 100),
                card("Lomadee", "Oferta sem preco", None, None),
            ],
        }
        self.historico = [
            {"rede": "Awin", "publicado_em": (AGORA - timedelta(hours=9)).isoformat()},
            {"rede": "Rakuten", "publicado_em": (AGORA - timedelta(hours=3)).isoformat()},
        ]

    def test_lomadee_sem_envios_anteriores_e_a_primeira(self):
        escolhido = p.selecionar(self.catalogo, set(), AGORA, self.historico)
        self.assertEqual(escolhido[1]["rede"], "Lomadee")

    def test_rodizio_prioriza_rede_ha_mais_tempo_sem_postar(self):
        hist = self.historico + [
            {"rede": "Lomadee", "publicado_em": (AGORA - timedelta(hours=1)).isoformat()}
        ]
        self.assertEqual(
            p.selecionar(self.catalogo, set(), AGORA, hist)[1]["rede"], "Awin"
        )

    def test_pode_forcar_awin_em_execucao_manual(self):
        escolhido = p.selecionar(self.catalogo, set(), AGORA, self.historico,
                                rede_desejada="Awin")
        self.assertEqual(escolhido[1]["rede"], "Awin")

    def test_prioriza_desconto_dentro_da_rede_selecionada(self):
        self.catalogo["cards"].append(card("Lomadee", "Oferta 70 por cento", 30, 100))
        self.assertEqual(
            p.selecionar(self.catalogo, set(), AGORA, self.historico)[1]["titulo"],
            "Oferta 70 por cento"
        )

    def test_nao_republica_oferta_ja_registrada(self):
        primeiro = p.selecionar(self.catalogo, set(), AGORA, self.historico)
        escolhido = p.selecionar(self.catalogo, {primeiro[0]}, AGORA, self.historico)
        self.assertEqual(escolhido[1]["rede"], "Awin")

    def test_sem_historico_todas_as_redes_tambem_tem_vez(self):
        escolhido = p.selecionar(self.catalogo, set(), AGORA, [])
        self.assertEqual(escolhido[1]["rede"], "Lomadee")

    def test_sem_oferta_da_rede_escolhida_nao_inventa(self):
        self.assertIsNone(p.selecionar(
            {"gerado_em": AGORA.isoformat(), "cards": [card("Rakuten", "Tenis")]},
            set(), AGORA, self.historico, rede_desejada="Lomadee"
        ))


if __name__ == "__main__":
    unittest.main()
