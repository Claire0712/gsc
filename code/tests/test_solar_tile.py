import unittest
import numpy as np
from scripts.solar_day import extrema
from scripts.solar_tile import reduce_tile
class SolarTile(unittest.TestCase):
 def test_vector_equals_scalar_across_month_and_date_line(self):
  first=int(np.datetime64('2024-01-30').astype(int));times=(first*24+np.arange(120))*3600
  lon=np.array([-180.,-179.75,-15.,0.,.25,15.,179.75,180.]);v=273.15+np.random.default_rng(42).normal(size=(120,len(lon)));v[50,2]=np.nan;days=np.arange(first+1,first+4)
  expected=extrema(times,v,lon,days);got=reduce_tile(times,v,lon,days)
  for k in expected:np.testing.assert_allclose(got[k],expected[k],atol=1e-12,rtol=0,equal_nan=True)
 def test_missing_edge_is_missing_and_discontinuous_axis_rejected(self):
  t=np.arange(48)*3600;v=np.ones((48,2))*280;lon=np.array([-15.,15.]);got=reduce_tile(t,v,lon,[0,1]);self.assertTrue(np.isnan(got['tmin_c'][0,1]));self.assertTrue(np.isnan(got['tmax_c'][1,0]))
  with self.assertRaises(ValueError):reduce_tile(t[::2],v[::2],lon,[0])
