import unittest
from shapely.geometry import box,MultiPolygon
from scripts.regional_map_display_geometry import normalize_outline
class OutlineRegression(unittest.TestCase):
 def test_nested_shells_regression_unions_land_instead_of_making_a_hole(self):
  x=MultiPolygon([box(0,0,4,4),box(1,1,2,2)]);self.assertFalse(x.is_valid);y=normalize_outline(x);self.assertTrue(y.is_valid);self.assertEqual(y.area,16);self.assertEqual(y.bounds,x.bounds)
 def test_valid_outline_stays_byte_identical(self):
  x=MultiPolygon([box(0,0,1,1),box(2,2,3,3)]);self.assertEqual(normalize_outline(x).wkb,x.wkb)
if __name__=='__main__':unittest.main()
