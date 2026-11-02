import unittest
from pathlib import Path
import math

class MatchTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(Path('scripts/match_windows.py').exists(),'implementation missing')
        from scripts.match_windows import match
        self.match=match
        common=dict(parent_event_id='e',country_id='TON',ioda_iso2='TO',signal='bgp',matching_technical_available='True',matching_curve_technical_available='True',raw_pre_normalized_features_available='True',raw_pre_level='100',raw_pre_mad_over_median='0.02',raw_pre_slope_per_day_over_median='0')
        self.h=dict(common,window_id='heat:e',role='heat',start='1719792000',end='1719964800')
        self.c=dict(common,window_id='control:e:7',role='control',start=str(1719792000+604800),end=str(1719964800+604800))
    def weather(self,rows):
        return [dict((k,r[k]) for k in ('window_id','parent_event_id','role','country_id','ioda_iso2','start','end'))|dict(tmax_mean_c=30,tmin_mean_c=None,dewpoint_mean_c=20) for r in rows]
    def run_case(self,rows=None,weather=None,multiplier=1):
        rows=rows or [self.h,self.c]
        return self.match(rows,weather or self.weather(rows),multiplier)
    def test_match_both_purposes(self):
        p,s=self.run_case();self.assertEqual(len(s),2)
        self.assertAlmostEqual(s[0]['distance'],7/45)
    def test_outcome_invariance(self):
        a=self.run_case()
        self.c['dhrd']=99999;self.h['recovery']=0
        self.assertEqual(a,self.run_case())
    def test_other_country_rejected(self):
        self.c['country_id']='FJI'
        with self.assertRaises(ValueError):self.run_case()
    def test_weather_identity_rejected(self):
        w=self.weather([self.h,self.c]);w[1]['start']='0'
        with self.assertRaises(ValueError):self.run_case(weather=w)
    def test_zero_level(self):
        self.c['raw_pre_level']='0'
        p,s=self.run_case();self.assertFalse(s);self.assertIn('nonpositive_level',p[0]['reasons'])
    def test_missing_weather(self):
        w=self.weather([self.h,self.c]);w[1]['dewpoint_mean_c']=None
        p,s=self.run_case(weather=w);self.assertFalse(s)
    def test_caliper_and_sensitivity(self):
        self.c['raw_pre_slope_per_day_over_median']='0.01'
        self.assertEqual(len(self.run_case()[1]),2)
        self.assertFalse(self.run_case(multiplier=.5)[1])
    def test_purpose_separation(self):
        self.c['matching_curve_technical_available']='False'
        p,s=self.run_case();self.assertEqual([r['purpose'] for r in s],['integral'])
    def test_top_three_deterministic(self):
        rows=[self.h]+[dict(self.c,window_id='control:'+str(i)) for i in range(4)]
        p,s=self.run_case(rows)
        self.assertEqual([r['control_id'] for r in s if r['purpose']=='integral'],['control:0','control:1','control:2'])
    def test_duplicate_signal_window(self):
        with self.assertRaises(ValueError):self.run_case([self.h,self.c,self.c])
