import unittest
import numpy as np
from scripts.country_solar import circular_longitudes, fixed_offset_extrema
from scripts.solar_day import extrema
class CountrySolarTests(unittest.TestCase):
 def test_circular_mean_does_not_cancel_dateline(self):
  w=np.array([[.5,.5,0,0],[0,0,.25,.75],[0,0,0,0],[0,0,.5,.5]])
  longitude=np.array([170,-170,0,180.])
  lon,resultant=circular_longitudes(w,longitude)
  self.assertAlmostEqual(abs(lon[0]),180);self.assertAlmostEqual(abs(lon[1]),180)
  self.assertTrue(np.isnan(lon[2]));self.assertTrue(np.isnan(lon[3]));self.assertAlmostEqual(resultant[1],.5)
 def test_fixed_slots_equal_actual_country_solar_labels(self):
  times=np.arange(-86400,4*86400,3600,dtype=np.int64);values=np.arange(len(times)*3,dtype=float).reshape(-1,3)+270
  values[35,1]=np.nan
  for lon in (-179.5,-105.,0.,103.4,179.5):
   expected=extrema(times,values,np.repeat(lon,3),np.arange(4));actual=fixed_offset_extrema(times,values,int(np.ceil(-lon/15)),np.arange(4))
   for key in expected:np.testing.assert_allclose(actual[key],expected[key],rtol=0,atol=1e-12,equal_nan=True)
if __name__=='__main__':unittest.main()
