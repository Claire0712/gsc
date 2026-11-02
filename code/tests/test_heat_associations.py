import unittest
import numpy as np
from scipy import sparse
from scripts.heat_associations_v2 import design, estimate

class HeatTest(unittest.TestCase):
    def test_roundoff_not_boundary_violation(self):
        rng=np.random.default_rng(12);x=rng.normal(size=(60,1));z=sparse.csr_matrix(np.ones((60,1)))
        r=estimate(x,np.ones(60)*(1+1e-14),z,[str(i%6) for i in range(60)],True)
        self.assertEqual(r['predicted_outside_unit_interval'],0)
    def test_design(self):
        rows=[dict(country_id='A',year_month='2022-01',exposure=dict(hd_c_days=4,span_days=3,peak_excess_c=2,hot_days=2,bridge_days=1,dewpoint_mean_c=20,ntrd_c_days=5))]
        a,_,names,_=design(rows,'A','M2');self.assertEqual(names,['hd_c_days','span_days','dewpoint_mean_c','ntrd_c_days']);np.testing.assert_array_equal(a,[[4,3,20,5]])
        b,_,names,_=design(rows,'B','M1');self.assertNotIn('span_days',names);self.assertIn('bridge_days',names)
        rows[0]['exposure']['bridge_days']=0
        _,_,names,omitted=design(rows,'B','M1');self.assertNotIn('bridge_days',names);self.assertEqual(omitted,['bridge_days:identically_zero'])
    def test_saturated(self):
        r=estimate(np.ones((3,1)),np.arange(3.),sparse.eye(3),['A','B','C'],False)
        self.assertFalse(r['estimable']);self.assertIn('reason',r)
    def test_joint(self):
        rng=np.random.default_rng(93);x=rng.normal(size=(90,2));z=np.eye(3)[np.arange(90)%3];y=x@np.array([.3,-.8])+z@np.array([1,2,3])+rng.normal(size=90)*.1
        r=estimate(x,y,sparse.csr_matrix(z),[str(i%9) for i in range(90)],False)
        self.assertTrue(r['estimable']);np.testing.assert_allclose(r['beta'],np.linalg.lstsq(np.column_stack([x,z]),y,rcond=None)[0][:2],atol=1e-10)

if __name__=='__main__':unittest.main()
