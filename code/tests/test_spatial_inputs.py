import unittest,math
from scripts.spatial_inputs import signed_grid_longitude,supported_country_day,country_threshold
class SpatialInputTests(unittest.TestCase):
 def test_actual_grid_origin_and_flattened_rows(self):
  self.assertEqual(signed_grid_longitude(0,[-180,-90,0,90]),-180)
  self.assertEqual(signed_grid_longitude(4,[-180,-90,0,90]),-180)
  self.assertEqual(signed_grid_longitude(0,[0,90,180,270]),0)
  self.assertEqual(signed_grid_longitude(3,[0,90,180,270]),-90)
 def test_zero_fraction_is_observed_but_missing_population_skips_threshold_lookup(self):
  rows=[('X',0.,20.),('missing',float('nan'),float('nan'))];q={('X',0):19.}
  selected=[country_threshold(c,'2024-01-01',q) for c,p,t in rows if supported_country_day(p,t)]
  self.assertEqual(selected,[19.]);self.assertEqual(country_threshold('X','2024-02-29',{('X',58):20.,('X',59):22.}),21)
if __name__=='__main__':unittest.main()
