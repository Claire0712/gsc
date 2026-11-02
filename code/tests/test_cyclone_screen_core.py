import math
import unittest
from pyproj import Geod
from scripts.cyclone_screen_core import candidate_boxes, merge_point_windows


class CycloneCoreTests(unittest.TestCase):
    def test_equator_and_zero(self):
        self.assertEqual(candidate_boxes(0, 0, 0), [(0, 0, 0, 0)])
        self.assertEqual(candidate_boxes(360, 0, 0), candidate_boxes(0, 0, 0))
        self.assertEqual(len(candidate_boxes(0, 0, 300000)), 1)

    def test_dateline(self):
        self.assertEqual(len(candidate_boxes(179.9, 0, 300000)), 2)
        self.assertEqual(len(candidate_boxes(-179.9, 0, 300000)), 2)

    def test_poles(self):
        for lat in [-90, -89, 89, 90]:
            box = candidate_boxes(120, lat, 300000)[0]
            self.assertEqual((box[0], box[2]), (-180, 180))

    def test_independent_ellipsoid_enclosure(self):
        geod = Geod(ellps='WGS84')
        for lon in [-180, -179.9, 0, 179.9, 180]:
            for lat in [-90, -89, -70, -30, 0, 30, 70, 89, 90]:
                for radius in [100000, 300000, 500000]:
                    boxes = candidate_boxes(lon, lat, radius)
                    for azimuth in range(0, 360, 10):
                        for fraction in [.5, 1.0]:
                            x, y, _ = geod.fwd(lon, lat, azimuth, radius*fraction)
                            self.assertTrue(any(a-1e-9 <= x <= c+1e-9 and b-1e-9 <= y <= d+1e-9 for a,b,c,d in boxes), (lon,lat,radius,x,y))

    def test_invalid_spatial_inputs(self):
        for args in [(0, 91, 1), (0, -91, 1), (0, 0, -1), (math.nan, 0, 1), (0, 0, math.inf), (True,0,1)]:
            with self.assertRaises(ValueError):
                candidate_boxes(*args)

    def test_windows_sort_merge_and_endpoint(self):
        self.assertEqual(merge_point_windows([100, 0, 20, 100], 10), [(-10,30),(90,110)])
        self.assertEqual(merge_point_windows([0, 21], 10), [(-10,10),(11,31)])
        self.assertEqual(merge_point_windows([100,100], 0), [(100,100)])

    def test_empty_windows(self):
        self.assertEqual(merge_point_windows([],86400), [])

    def test_invalid_windows(self):
        for times,width in [([True],1),([1.0],1),([1],-1),([1],1.0),([],True)]:
            with self.assertRaises(ValueError):
                merge_point_windows(times,width)


if __name__ == '__main__':
    unittest.main()
