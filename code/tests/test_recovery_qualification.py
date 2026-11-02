import unittest
import numpy as np
from scripts.recovery_qualification import qualify

class RecoveryTest(unittest.TestCase):
    def fixture(self):
        t=np.arange(0,86400+259200,600);v=np.ones(len(t));v[:144]=.8
        return dict(target_timestamps=t,target_values=v,baseline=np.ones(len(t)),analysis_available=np.ones(len(t),dtype=bool),target_exclusion_bits=np.zeros(len(t),dtype=np.uint8))
    def test_future_flag_does_not_remove_confirmed(self):
        a=self.fixture();a['target_exclusion_bits'][200]=4
        r=qualify(a,0,86400);self.assertTrue(r['risk_eligible']);self.assertEqual(r['recovery']['confirmation_hours'],4)
    def test_prefix_flag_censors(self):
        a=self.fixture();a['target_exclusion_bits'][150]=2
        r=qualify(a,0,86400);self.assertEqual(r['recovery']['status'],'missingness_censored');self.assertEqual(r['recovery']['followup_hours'],1);self.assertEqual(r['censor_cause'],'stop_candidate')
    def test_core_flag_excludes(self):
        a=self.fixture();a['target_exclusion_bits'][3]=8
        self.assertFalse(qualify(a,0,86400)['risk_eligible'])

if __name__=='__main__':unittest.main()
