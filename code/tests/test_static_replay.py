import unittest
import numpy as np
from scripts.build_static_replay import hourly

class ReplayTest(unittest.TestCase):
    def test_missing_hour_not_filled(self):
        t=np.arange(12)*600;v=np.ones(12);v[1]=np.nan
        rows=hourly(t,v,np.ones(12),np.ones(12,dtype=bool),0)
        self.assertIsNone(rows[0][1]);self.assertEqual(rows[1],[1,1])
    def test_zero_is_observed(self):
        rows=hourly(np.arange(6)*600,np.zeros(6),np.ones(6),np.ones(6,dtype=bool),0)
        self.assertEqual(rows,[[0,0]])

if __name__=='__main__':unittest.main()
