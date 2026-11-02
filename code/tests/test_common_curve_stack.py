import unittest
from pathlib import Path
from scripts import common_curve_stack
from scripts.common_curve_stack import restrict

class CommonStack(unittest.TestCase):
    def test_manifest_relative_and_absolute_entries_resolve_same_file(self):
        self.assertEqual(common_curve_stack.input_entry({'analysis/x.json':{'sha256':'a'}},Path('analysis/x.json').resolve()),{'sha256':'a'})
    def test_filter_recounts_controls_and_weights(self):
        support=[dict(purpose='curve',event_id='e',heat_id='h',common_controls=['a'])]
        rows=[]
        for s in ('ping-slash24','bgp','merit-nt'):
            for wid,role in [('h','heat'),('a','control'),('b','control')]:
                rows.append(dict(signal=s,purpose='curve',group_id='e',window_id=wid,
                    role=role,country_id='X',date_utc='0',relative_day='0',base_weight='.5'))
        got=restrict(rows,support)
        self.assertEqual(len(got),6)
        self.assertTrue(all(r['weight']==1 and r['matched_controls']==1 for r in got))

    def test_missing_signal_slot_rejected(self):
        support=[dict(purpose='curve',event_id='e',heat_id='h',common_controls=['a'])]
        with self.assertRaises(ValueError):restrict([],support)
