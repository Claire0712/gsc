import unittest,copy,numpy as np
from scripts.proposal_interactions import interaction_design
from scripts.heat_associations import estimate,design
class InteractionTests(unittest.TestCase):
 def rows(self):return [dict(country_id='A' if i<4 else 'B',year_month='2022-01',exposure=dict(hd_c_days=float(i),span_days=3.,dewpoint_mean_c=20.+i*2,ntrd_c_days=float(i*i))) for i in range(8)]
 def test_product_and_immutable_originals(self):
  rows=self.rows();old=copy.deepcopy(rows);base,z,names,_=design(rows,'A','M2')
  x,zz,nn,meta=interaction_design(rows,'ntrd')
  np.testing.assert_array_equal(x[:,:4],base);np.testing.assert_array_equal(zz.toarray(),z.toarray());self.assertEqual(nn[:4],names)
  np.testing.assert_array_equal(x[:,-1],(np.arange(8)-3.5)*(np.arange(8)**2-17.5));self.assertEqual(rows,old);self.assertEqual(meta['modifier_mean'],17.5)
  y,_,_,_=interaction_design(rows,'dewpoint');np.testing.assert_array_equal(y[:,-1],(np.arange(8)-3.5)*(np.arange(8)*2-7))
 def test_no_residual_df_retained(self):
  rows=self.rows()[:3]
  for i,r in enumerate(rows):r['country_id']=str(i)
  x,z,_,_=interaction_design(rows,'ntrd');f=estimate(x,np.arange(3.),z,['0','1','2'],True);self.assertFalse(f['estimable']);self.assertEqual(f['reason'],'No residual degrees of freedom')
 def test_unknown_kind(self):
  with self.assertRaises(ValueError):interaction_design(self.rows(),'search')
