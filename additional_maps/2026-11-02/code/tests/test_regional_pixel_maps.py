import unittest,numpy as np
from scripts.regional_pixel_maps import summarize_days
class RegionalSummaryTests(unittest.TestCase):
 def test_strict_threshold_zero_missing_and_conditional_support(self):
  dates=np.array(['2022-01-01','2023-01-01','2024-01-01','2025-01-01'],dtype='datetime64[D]');v=np.array([[35.,40],[36,40],[np.nan,0],[30,0]]);q=np.full((4,2),35.);a=summarize_days(v,q,dates,np.array([False,True,False,False]))
  self.assertTrue(np.isnan(a['absolute_days_per_year'][0]));self.assertEqual(a['absolute_days_per_year'][1],.5);self.assertEqual(a['relative_days_per_year'][1],.5);self.assertAlmostEqual(a['local_hot_on_national_nonhot_fraction'][1],1/3);self.assertTrue(np.isnan(a['local_hot_on_national_nonhot_fraction'][0]));self.assertEqual(a['annual_relative_percent'][0,0],0);self.assertTrue(np.isnan(a['annual_relative_percent'][2,0]))
 def test_missing_threshold_does_not_erase_absolute_metric(self):
  d=np.array(['2022-02-28','2024-02-29'],dtype='datetime64[D]');v=np.array([[0.],[40.]]);q=np.array([[np.nan],[39.]])
  a=summarize_days(v,q,d,np.array([False,False]));self.assertEqual(a['absolute_days_per_year'][0],.25);self.assertTrue(np.isnan(a['relative_days_per_year'][0]))
 def test_dates_and_shapes_checked(self):
  d=np.array(['2022-01-01','2022-01-01'],dtype='datetime64[D]')
  with self.assertRaises(ValueError):summarize_days(np.ones((2,1)),np.zeros((2,1)),d,np.array([False,False]))
 def test_numpy_tile_metadata_serialization(self):
  import json
  from scripts.regional_pixel_maps import json_scalar
  self.assertEqual(json.loads(json.dumps({'latitude_start':np.int32(121),'fraction':np.float32(.5)},default=json_scalar)),{'latitude_start':121,'fraction':.5})
  with self.assertRaises(TypeError):json.dumps({'unexpected':object()},default=json_scalar)
