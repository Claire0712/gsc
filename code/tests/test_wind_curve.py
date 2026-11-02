import unittest
from scripts.wind_curve import subset

class WindCurve(unittest.TestCase):
    def test_same_rows_for_nested_models_and_recounts_control(self):
        rows=[dict(country_id='X',date=d,date_utc=d,window_id=w,role=r,group_id='e',signal='bgp',purpose='curve') for d,w,r in [('a','h','heat'),('b','c','control'),('x','bad','control')]]
        lookup={('X',d):dict(u10_m_s=0,v10_m_s=1,u10_m_s_population_fraction=1,v10_m_s_population_fraction=1) for d in ('a','b')}
        got=subset(rows,lookup,.95)
        self.assertEqual([r['window_id'] for r in got],['h','c'])
        self.assertTrue(all(r['base_weight']==r['weight']==1 for r in got))
    def test_bad_heat_cannot_be_rescued_by_control(self):
        rows=[dict(country_id='X',date='a',date_utc='a',window_id='h',role='heat',group_id='e',signal='bgp',purpose='curve')]
        self.assertEqual(subset(rows,{},.95),[])
