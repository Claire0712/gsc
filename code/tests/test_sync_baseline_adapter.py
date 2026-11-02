import unittest
import numpy as np

class SyncBaselineAdapterTest(unittest.TestCase):
    def test_source_and_target_mask_preserve_raw_zero(self):
        from scripts.sync_baseline_adapter import remasked_baseline
        day=86400;t=np.arange(0,60*day,600,dtype=np.int64);v=np.full(len(t),10.)
        target=30*day;v[t==target]=0
        screen=np.array([target-7*day,target],dtype=np.int64)
        result=remasked_baseline(t,v,np.zeros(len(t),bool),np.ones(len(t),bool),
                                np.array([target,target+600]),screen,np.ones(2,bool))
        self.assertEqual(result['raw_target_values'][0],0)
        self.assertTrue(result['target_sync_candidate'][0])
        self.assertFalse(result['analysis_available'][0])
        self.assertEqual(result['reference_count'][0],7)
        self.assertEqual(int(result['reference_sync_candidate'][0].sum()),1)
        self.assertTrue(result['analysis_available'][1])
        self.assertEqual(v[t==target][0],0)
        other=remasked_baseline(t,v,np.zeros(len(t),bool),np.ones(len(t),bool),
                                np.array([target]),screen,np.zeros(2,bool))
        self.assertTrue(other['analysis_available'][0])
        self.assertEqual(other['target_values'][0],0)

if __name__=='__main__':unittest.main()
