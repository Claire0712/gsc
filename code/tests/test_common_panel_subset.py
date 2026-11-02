import unittest
from scripts.common_panel_subset import subset

class CommonSubsetTest(unittest.TestCase):
    def test_exact_three_signal_clean_and_matched_membership(self):
        rows=[dict(event_id=e,signal=s,full_observed_unconfounded=True,matched_integral=True) for e in ('a','b') for s in ('ping-slash24','bgp','merit-nt')]
        rows[-1]['matched_integral']=False
        self.assertEqual(len(subset(rows,'clean')),6)
        self.assertEqual({r['event_id'] for r in subset(rows,'matched')},{'a'})
        with self.assertRaises(ValueError):subset(rows,'unknown')
        rows[-1]['full_observed_unconfounded']=False
        self.assertEqual({r['event_id'] for r in subset(rows,'clean')},{'a'})
