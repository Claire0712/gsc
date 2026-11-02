import unittest
from scripts.calendar_block_placebo import translated
class CalendarBlocks(unittest.TestCase):
 def test_exact_translation_preserves_order_and_reweights(self):
  rows=[dict(group_id='g',window_id=w,country_id='X',role=role,relative_day=k,date_utc=(start+k)*86400,signal='bgp',purpose='curve') for w,role,start in [('h','heat',100),('a','control',200),('b','control',300)] for k in range(-7,8)]
  lookup={('X',r['date_utc']+28*86400):dict(signed=r['relative_day'],deficit=0.,below95=0.,dewpoint=20.) for r in rows if r['window_id']!='b'}
  got=translated(rows,28,lookup);self.assertEqual(len(got),30)
  self.assertEqual([r['signed'] for r in got[:15]],list(range(-7,8)))
  self.assertTrue(all(r['source_date_utc']==r['date_utc']==r['original_date_utc']+28*86400 for r in got))
  self.assertTrue(all(r['weight']==1. for r in got))
 def test_missing_anchor_never_wraps_or_fills(self):
  row=dict(group_id='g',window_id='h',country_id='X',role='heat',relative_day=0,date_utc=0,signal='bgp',purpose='curve')
  self.assertEqual(translated([row],-28,{}),[])
