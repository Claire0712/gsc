import unittest
from scripts import common_control_support as core

def row(signal,control='a',event='e',purpose='integral'):
    return dict(parent_event_id=event,heat_id='heat:'+event,country_id='X',
                signal=signal,control_id=control,purpose=purpose,selected=True,supported=True)

class CommonControls(unittest.TestCase):
    def test_identical_event_without_identical_control_is_not_common(self):
        rows=[row(s,c) for s,c in zip(core.SIGNALS,['a','b','c'])]
        result=core.audit(rows)
        self.assertEqual(result['summary']['integral']['all_signal_events'],1)
        self.assertEqual(result['summary']['integral']['common_control_events'],0)

    def test_intersection_preserves_all_common_controls_and_separates_purpose(self):
        rows=[row(s,c) for s in core.SIGNALS for c in ['a','b']]
        rows += [row('bgp','c'),row('bgp','a',purpose='curve')]
        result=core.audit(rows)
        self.assertEqual(result['events'][0]['common_controls'],['a','b'])
        self.assertEqual(result['summary']['integral']['common_pairs'],2)
        self.assertEqual(result['summary']['curve']['common_control_events'],0)

    def test_duplicate_or_inconsistent_identity_rejected(self):
        with self.assertRaises(ValueError):core.audit([row('bgp'),row('bgp')])
        x=row('ping-slash24');x['country_id']='Y'
        with self.assertRaises(ValueError):core.audit([row('bgp'),x])
