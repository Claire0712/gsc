import unittest
from scripts.nonheat_placebo import subset

class NonheatPlacebo(unittest.TestCase):
 def test_earliest_nonoverlap_control_is_anchor_and_real_heat_never_enters(self):
  rows=[]
  for window,day,role in [('real',40,'heat'),('early',0,'control'),('overlap',7,'control'),('late',21,'control')]:
   for rel in range(-7,8):rows.append(dict(group_id='g',window_id=window,country_id='X',signal='bgp',purpose='curve',date_utc=(day+rel)*86400,relative_day=rel,role=role,signed=99 if role=='heat' else .1))
  got=subset(rows)
  self.assertEqual(len(got),30)
  self.assertEqual({r['window_id'] for r in got},{'early','late'})
  self.assertTrue(all(r['original_role']=='control' and r['signed']==.1 for r in got))
  self.assertEqual({r['role'] for r in got if r['window_id']=='early'},{'heat'})
  self.assertTrue(all(r['weight']==1 for r in got))
 def test_single_or_overlapping_control_does_not_supply_placebo(self):
  rows=[dict(group_id='g',window_id='one',country_id='X',signal='bgp',purpose='curve',date_utc=d*86400,relative_day=d,role='control') for d in range(-7,8)]
  self.assertEqual(subset(rows),[])
