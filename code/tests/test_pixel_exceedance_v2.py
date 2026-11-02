import unittest
import numpy as np
from scripts.pixel_exceedance import pixel_thresholds as scalar_nan_path
from scripts.pixel_exceedance_v2 import pixel_thresholds
class FastThresholdTests(unittest.TestCase):
 def test_vectorized_partition_preserves_thresholds_and_missing_support(self):
  rng=np.random.default_rng(20261031);days=np.tile(np.arange(365),4);years=np.repeat(np.arange(2018,2022),365)
  v=rng.normal(size=(1460,8));v[:20,1]=np.nan;v[:365,2]=np.nan;v[::100,3]=np.inf
  a=scalar_nan_path(v,days,years,np.arange(365));b=pixel_thresholds(v,days,years,np.arange(365))
  for old,new in zip(a,b):np.testing.assert_allclose(old,new,atol=0,rtol=0,equal_nan=True)
if __name__=='__main__':unittest.main()
