import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sync_awin import attach_sol_page, whatsapp_message

class TestRouterLinks(unittest.TestCase):
    def test_slug_and_link(self):
        item={'id':'p-123','loja':'Nike BR','tipo':'produto','titulo':'Tênis Air Max 90',
              'preco':199.90,'preco_anterior':249.90,'cupom':None,
              'validade':None,'descricao':'','termos':'',
              'link':'https://www.awin1.com/pclick.php?p=123&a=3110826&m=1'}
        attach_sol_page(item)
        self.assertTrue(item['slug'].startswith('tenis-air-max-90-'))
        self.assertTrue(item['url_sol_garimpa'].startswith('https://www.ofertaspravc.com.br/oferta/'))
        self.assertIn(item['url_sol_garimpa'],whatsapp_message(item))
        self.assertNotIn(item['link'],whatsapp_message(item))
        self.assertEqual(item['slug'], attach_sol_page(item)['slug'])

    def test_no_offer_not_shared(self):
        self.assertIsNone(whatsapp_message({'tipo':'sem_oferta','link':None}))

if __name__ == '__main__':unittest.main()
