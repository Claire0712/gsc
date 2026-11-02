import unittest
import copy
from scripts.event_panel import build

def fixture():
    h=dict(event_id='e',country_id='A',start_date='2022-01-01',end_exclusive_utc='2022-01-03T00:00:00Z',span_days='2',hot_days='2',bridge_days='0',hd_c_days='4',mean_hot_excess_c='2',peak_excess_c='3',absolute_tmax_c='35',ntrd_c_days='1',dewpoint_mean_c='20')
    r=dict(event_id='e',country_id='A',signal='bgp',full_observed_unconfounded=False,metrics=dict(event_start=1640995200,event_end_exclusive=1641168000,core_complete=True,full_window_complete=False,core_end_state='damaged_at_end',state='insufficient_observation',recovery=dict(survival_eligible_from_core=True,status='missingness_censored',followup_hours=2,confirmation_hours=None)))
    return r,h

class PanelTest(unittest.TestCase):
    def test_censor_retained(self):
        r,h=fixture();p=build([r],[h],set())[0]
        self.assertEqual(p['survival_time_hours'],2);self.assertFalse(p['recovery_observed']);self.assertFalse(p['matched_integral'])
    def test_healthy_has_no_survival_time(self):
        r,h=fixture();r['metrics']['core_end_state']='no_core_deficit';r['metrics']['recovery'].update(survival_eligible_from_core=False,status='not_applicable',followup_hours=None)
        self.assertIsNone(build([r],[h],set())[0]['survival_time_hours'])
    def test_confirmed(self):
        r,h=fixture();r['metrics']['recovery'].update(status='confirmed',followup_hours=4,confirmation_hours=4)
        self.assertTrue(build([r],[h],{('e','bgp')})[0]['recovery_observed'])
    def test_mismatch_and_duplicates(self):
        r,h=fixture()
        for key,value in [('country_id','B'),('span_days','3'),('hd_c_days','5'),('end_exclusive_utc','2022-01-04T00:00:00Z')]:
            bad=copy.deepcopy(h);bad[key]=value
            with self.assertRaises(ValueError):build([r],[bad],set())
        with self.assertRaises(ValueError):build([r,r],[h],set())
        with self.assertRaises(ValueError):build([r],[h,h],set())

if __name__=='__main__':unittest.main()
