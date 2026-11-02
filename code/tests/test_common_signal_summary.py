import unittest
from scripts.common_signal_summary import select

class CommonTest(unittest.TestCase):
    def test_complete_intersection(self):
        rows=[dict(event_id='e',signal=s,full_observed_unconfounded=True,matched_integral=s!='bgp') for s in ('bgp','ping-slash24','merit-nt')]
        self.assertEqual(len(select(rows,False)),3);self.assertEqual(select(rows,True),[])
        rows[1]['full_observed_unconfounded']=False;self.assertEqual(select(rows,False),[])
    def test_duplicate_rejected(self):
        r=dict(event_id='e',signal='bgp',full_observed_unconfounded=True,matched_integral=True)
        with self.assertRaises(ValueError):select([r,r],False)

if __name__=='__main__':unittest.main()
