import unittest
from scripts.precip_curve import subset

class PrecipCurve(unittest.TestCase):
    def test_zero_rain_retained_bad_control_removed_and_weights_recounted(self):
        rows=[dict(country_id='X',date=d,date_utc=d,window_id=w,role=r,group_id='e',signal='bgp',purpose='curve') for d,w,r in [('a','h','heat'),('b','c','control'),('x','bad','control')]]
        lookup={('X',d):dict(precip_mm=0.,precip_mm_population_fraction=1.) for d in ('a','b')}
        got=subset(rows,lookup,.95)
        self.assertEqual([r['window_id'] for r in got],['h','c'])
        self.assertTrue(all(r['base_weight']==r['weight']==1 for r in got))
        lookup['X','a']['precip_mm_population_fraction']=.94
        self.assertEqual(subset(rows,lookup,.95),[])
