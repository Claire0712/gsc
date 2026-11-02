import unittest
import numpy as np
from scripts.solar_day import extrema
class SolarDay(unittest.TestCase):
 def test_longitude_midnight_and_utc(self):
  t=np.arange(72)*3600;a=np.tile(np.arange(72.)[:,None],(1,2))+273.15
  r=extrema(t,a,np.array([0.,15.]),[1])
  np.testing.assert_allclose(r['tmin_c'],[[24,23]])
  np.testing.assert_allclose(r['tmax_c'],[[47,46]])
  np.testing.assert_allclose(r['mean_c'],[[35.5,34.5]])
 def test_missing_hour_and_negative_longitude(self):
  t=np.arange(72)*3600;a=np.tile(np.arange(72.)[:,None],(1,2))+273.15;a[30,0]=np.nan
  r=extrema(t,a,np.array([0.,-15.]),[1]);self.assertTrue(np.isnan(r['tmin_c'][0,0]));self.assertAlmostEqual(r['tmin_c'][0,1],25)
