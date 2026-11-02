import unittest
import numpy as np

class RecoveryQualificationDefinitionTest(unittest.TestCase):
    def test_threshold_and_future_confound_censor_without_removing_membership(self):
        from scripts.recovery_definition_qualification import qualify
        start=1704067200;end=start+86400
        t=np.arange(start,end+72*3600,600,dtype=np.int64)
        a=dict(target_timestamps=t,target_values=np.r_[np.full(144,.94),np.ones(432)],
               baseline=np.ones(576),analysis_available=np.ones(576,dtype=bool),
               target_exclusion_bits=np.zeros(576,dtype=np.uint8))
        self.assertFalse(qualify(a,start,end,.9,24)['risk_eligible'])
        for threshold,slots in ((.98,24),(.95,12),(.95,36)):
            q=qualify(a,start,end,threshold,slots)
            self.assertTrue(q['risk_eligible'])
            self.assertEqual(q['recovery']['confirmation_hours'],slots/6)
        a['target_exclusion_bits'][150]=4
        q=qualify(a,start,end,.95,12)
        self.assertTrue(q['risk_eligible'])
        self.assertEqual(q['recovery']['status'],'missingness_censored')
        self.assertEqual(q['recovery']['followup_hours'],1)
        self.assertEqual(q['censor_cause'],'cyclone_candidate')
        a['target_exclusion_bits'][143]=2
        self.assertFalse(qualify(a,start,end,.95,12)['risk_eligible'])

if __name__=='__main__':unittest.main()
