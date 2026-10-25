import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import sync_awin as s

class TestSync(unittest.TestCase):
  def test_22_stores(self):
    self.assertEqual(len(s.STORES),22)
    self.assertEqual(sum(x[1] for x in s.STORES),17)
    self.assertEqual(s.identify('KaBuM!'),'Kabum BR')
    self.assertEqual(s.identify("Sam's Club BR"),"Sam's Club BR")
    self.assertIsNone(s.identify('other stranger store'))
  def test_safe_affiliate(self):
    self.assertTrue(s.safe_url('https://www.awin1.com/pclick.php?p=123&a=3110826&m=4',True))
    self.assertFalse(s.safe_url('https://nike.com/shoes',True))
    self.assertFalse(s.safe_url('javascript:alert(1)',False))
    self.assertFalse(s.safe_url('https://example.org@evil.test/x',True))
  def test_price_and_product(self):
    self.assertEqual(s.money('R$ 1.234,50'),1234.50)
    self.assertEqual(s.money('1,234.50'),1234.50)
    p=s.product_candidate(dict(product_name='Tênis de teste',merchant_image_url='https://example.com/p.jpg',aw_deep_link='https://www.awin1.com/pclick.php?p=123&a=3110826&m=4',search_price='80',product_price_old='100',currency='BRL'),'Nike BR')
    self.assertEqual(p['desconto_pct'],20)
    self.assertEqual(p['loja'],'Nike BR')
    self.assertIsNone(s.product_candidate(dict(product_name='Tênis',merchant_image_url='https://example.com/p.jpg',aw_deep_link='https://nike.com/direto',search_price='80',currency='BRL'),'Nike BR'))
  def test_campaign(self):
    p=s.offer_candidate(dict(promotionId=3,type='voucher',advertiser={'name':'Havaianas BR','joined':True},title='Cupom teste',urlTracking='https://www.awin1.com/cread.php?awinmid=123&awinaffid=3110826',voucher={'code':'TESTE'}))
    self.assertEqual(p['cupom'],'TESTE')
    self.assertEqual(p['loja'],'Havaianas BR')
    self.assertIsNone(s.offer_candidate(dict(advertiser={'name':'Havaianas BR','joined':False},title='Cupom teste',urlTracking='https://www.awin1.com/cread.php?awinmid=123&awinaffid=3110826')))

if __name__=='__main__':unittest.main()
