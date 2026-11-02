import unittest
from scripts.weather_pair_support import valid_controls

class PairSupport(unittest.TestCase):
    def test_bad_control_does_not_remove_good_pair(self):
        rows=[dict(country_id='X',date=d,window_id=w,role=r) for d,w,r in [('a','h','heat'),('b','c1','control'),('c','c2','control')]]
        lookup={('X',d):dict(v=0,v_population_fraction=1) for d in ('a','b')}
        self.assertEqual(valid_controls(rows,lookup,('v',),0),['c1'])
    def test_missing_heat_removes_all_controls(self):
        rows=[dict(country_id='X',date='a',window_id='h',role='heat'),dict(country_id='X',date='b',window_id='c',role='control')]
        lookup={('X','b'):dict(v=1,v_population_fraction=1)}
        self.assertEqual(valid_controls(rows,lookup,('v',),0),[])
