import unittest
import numpy as np
from scripts.geographic_common_support import joint_support,arm_counts,regional_design
from scripts.heat_associations_v2 import estimate
class GeographicSupportTest(unittest.TestCase):
 def test_joint_not_marginal_overlap(self):
  x=np.array([[0.,0.],[1.,1.],[0.,1.],[1.,0.]])
  mask,peer,d=joint_support(x,np.array([0,0,1,1]),np.ones(2),.5)
  self.assertFalse(mask.any());self.assertEqual(peer.tolist(),[-1]*4)
 def test_zero_constant_missing_and_peer(self):
  x=np.array([[0.,2.],[0.,2.],[0.,3.],[np.nan,2.]])
  mask,peer,d=joint_support(x,np.array([0,1,1,1]),np.array([0.,0.]),.5)
  self.assertEqual(mask.tolist(),[True,True,False,False]);self.assertEqual(peer[:2].tolist(),[1,0]);self.assertEqual(d[0],0)
 def test_counts_require_country_support(self):
  r=[{'country_id':'A'}]*10+[{'country_id':str(i)} for i in range(10)]
  self.assertEqual(arm_counts(r,np.array([1]*10+[0]*10)),[{'events':10,'countries':10},{'events':10,'countries':1}])
 def test_known_conditional_slope_interaction(self):
  rng=np.random.default_rng(451);rows=[];group=[];features=[];y=[]
  for c in range(20):
   for j in range(20):
    hd,span,dew,ntrd,tmax,pre,mad=rng.uniform(1,5,7);g=int(c<10)
    rows.append(dict(country_id=str(c),year_month=str(j%5),exposure=dict(hd_c_days=hd,span_days=span,dewpoint_mean_c=dew,ntrd_c_days=ntrd,absolute_tmax_c=tmax)))
    group.append(g);features.append([hd,tmax,span,pre,mad,1.]);y.append(.01*hd+.02*hd*g+.03*span+.01*dew+.02*ntrd+.005*tmax+.002*pre+.001*mad+c*.001+j%5*.002)
  x,z,names=regional_design(rows,np.array(features),np.array(group));result=estimate(x,np.array(y),z,[r['country_id'] for r in rows],False)
  self.assertTrue(result['estimable']);self.assertAlmostEqual(result['beta'][names.index('hd_x_region')],.02,places=9)
if __name__=='__main__':unittest.main()
