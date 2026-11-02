import unittest
import importlib.util
import numpy as np

class PairedTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.paired_responses'), 'paired implementation missing')
        from scripts import paired_responses
        return paired_responses

    def test_daily(self):
        m=self.module(); t=np.arange(0,172800,600);v=np.r_[np.zeros(144),np.ones(144)*2]
        r=m.daily(t,v,np.ones(288),np.ones(288,dtype=bool),0,172800)
        self.assertEqual(r[0]['deficit'],1);self.assertEqual(r[0]['below95'],1)
        self.assertEqual(r[1]['signed'],1);self.assertEqual(r[1]['deficit'],0)

    def test_missing_rejected(self):
        m=self.module();t=np.arange(0,86400,600);a=np.ones(144,dtype=bool);a[7]=False
        with self.assertRaises(ValueError):m.daily(t,np.ones(144),np.ones(144),a,0,86400)

    def test_duplicate_time_rejected(self):
        m=self.module();t=np.zeros(144,dtype=int)
        with self.assertRaises(ValueError):m.daily(t,np.ones(144),np.ones(144),np.ones(144,dtype=bool),0,86400)

    def rows(self):
        return [dict(group_id=g,window_id=w,signal=s,purpose='curve',country_id='X',date_utc=d,role=role,base_weight=b) for g,w,s,d,role,b in [('a','c','ap',0,'control',.5),('b','d','ap',0,'control',1),('a','c','ap',86400,'control',.5),('a','h','ap',0,'heat',1),('a','e','bgp',0,'control',1)]]

    def test_partial_overlap_weights(self):
        r=self.module().weights(self.rows())
        self.assertAlmostEqual(r[0]['weight'],1/3);self.assertAlmostEqual(r[1]['weight'],2/3)
        self.assertEqual(r[2]['weight'],1);self.assertEqual(r[3]['weight'],1);self.assertEqual(r[4]['weight'],1)
        self.assertEqual(r[0]['control_date_uses'],2)

    def test_duplicate_rejected(self):
        m=self.module();r=self.rows()
        with self.assertRaises(ValueError):m.weights(r+[dict(r[0])])

    def test_purpose_isolation(self):
        m=self.module();r=self.rows();a=dict(r[0]);a['purpose']='integral';r.append(a)
        self.assertEqual(m.weights(r)[-1]['weight'],1)

    def test_driver_available(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.run_paired_responses'), 'driver missing')

if __name__=='__main__':unittest.main()
