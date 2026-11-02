import unittest
import numpy as np
from pyproj import Geod
from shapely.geometry import Polygon, MultiPolygon, box
from scripts.cyclone_distance import BoundaryIndex


class BoundaryTests(unittest.TestCase):
    def test_inside_and_outside(self):
        index = BoundaryIndex(box(-1,-1,1,1))
        self.assertEqual(index.classify(0,0)['within'], [True]*3)
        self.assertEqual(index.classify(20,0)['within'], [False]*3)
        # East edge is 1 degree away: 111.319 km on the equator.
        self.assertEqual(index.classify(2,0)['within'], [False,True,True])

    def test_hole(self):
        poly=Polygon([(-5,-5),(5,-5),(5,5),(-5,5)], holes=[[(-2,-2),(-2,2),(2,2),(2,-2)]])
        self.assertEqual(BoundaryIndex(poly).classify(0,0)['within'], [False,True,True])

    def test_dateline_split(self):
        poly=MultiPolygon([box(179,-1,180,1), box(-180,-1,-179,1)])
        index=BoundaryIndex(poly)
        for x in [-179.5,179.5]:
            self.assertEqual(index.classify(x,0)['within'], [True]*3)
        self.assertEqual(index.classify(178,0)['within'], [False,True,True])

    def test_reject_invalid_geometry(self):
        for poly in [Polygon(), Polygon([(179,0),(-179,0),(-179,1),(179,1)])]:
            with self.assertRaises(ValueError): BoundaryIndex(poly)

    def test_dateline_roundoff_only(self):
        index=BoundaryIndex(box(179,-1,180.0000000000001,1))
        self.assertGreater(index.roundoff_coordinates,0)
        self.assertEqual(index.classify(-179.5,0)['within'],[True]*3)
        with self.assertRaises(ValueError):
            BoundaryIndex(box(179,-1,180.000001,1))

    def test_equatorial_threshold(self):
        geod=Geod(ellps='WGS84')
        x,_,_=geod.fwd(1,0,90,300000)
        result=BoundaryIndex(box(-1,-1,1,1)).classify(x,0)
        self.assertIsNot(result['within'][1], False)
        self.assertEqual(result['within'][0],False)
        self.assertEqual(result['within'][2],True)

    def test_independent_dense_boundary(self):
        geod=Geod(ellps='WGS84')
        poly=Polygon([(10,65),(14,66),(13,69),(9,68)])
        index=BoundaryIndex(poly)
        coords=np.asarray(poly.exterior.coords)
        samples=np.concatenate([np.linspace(a,b,10001) for a,b in zip(coords[:-1],coords[1:])])
        for x,y in [(15,67),(18,70),(5,64)]:
            _,_,d=geod.inv(np.full(len(samples),x),np.full(len(samples),y),samples[:,0],samples[:,1])
            expected=[bool(d.min()<=r) for r in [100000,300000,500000]]
            self.assertEqual(index.classify(x,y)['within'],expected)


if __name__=='__main__': unittest.main()
