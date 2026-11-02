import unittest
import numpy as np
from scripts.pixel_exceedance import pixel_thresholds, population_fraction

class PixelTests(unittest.TestCase):
 def test_threshold_support_and_strict_exceedance(self):
  days=np.tile(np.arange(31),4);years=np.repeat(np.arange(2018,2022),31)
  values=np.column_stack([np.arange(124.),np.ones(124)])
  q,n,ny=pixel_thresholds(values,days,years,[15])
  np.testing.assert_allclose(q,[[110.7,1.]])
  np.testing.assert_array_equal(n,[[124,124]]);np.testing.assert_array_equal(ny,[[4,4]])
  p,missing=population_fraction(np.array([[111.,1.],[110.,2.],[np.nan,2.]]),np.tile(q,(3,1)),[.25,.75])
  np.testing.assert_allclose(p[:2],[.25,.75]);self.assertTrue(np.isnan(p[2]));np.testing.assert_allclose(missing,[0,0,.25])
 def test_missing_reference_and_circular_window(self):
  days=np.tile(np.r_[np.arange(16),np.arange(350,365)],4);years=np.repeat(np.arange(2018,2022),31)
  a=np.ones((124,3));a[:13,0]=np.nan;a[:31,1]=np.nan;a[0,2]=np.nan
  q,n,ny=pixel_thresholds(a,days,years,[0])
  self.assertTrue(np.isnan(q[0,0]));self.assertTrue(np.isnan(q[0,1]));self.assertEqual(q[0,2],1)
  self.assertEqual(n[0,0],111);self.assertEqual(ny[0,1],3)
  with self.assertRaises(ValueError):population_fraction([[1,2]],[[1,2]],[.2,.2])
if __name__=='__main__':unittest.main()
