import unittest,importlib.util
class DesignTests(unittest.TestCase):
    def test_reference_and_interaction(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.run_event_curve'),'driver missing')
        from scripts.run_event_curve import design
        rows=[dict(group_id='g',window_id=w,country_id='A',date_utc=str(86400*(20+k)),relative_day=str(k),role=role,weight='1',dewpoint=2) for w,role in [('h','heat'),('c','control')] for k in range(-7,8)]
        x,z,w=design(rows)
        self.assertEqual(x.shape,(30,15));self.assertEqual(float(x[6,:14].sum()),0)
        self.assertEqual(float(x[7,:14].sum()),1);self.assertEqual(float(x[15:,:14].sum()),0)
        self.assertTrue((x[:,-1]==2).all());self.assertEqual(z.shape[0],30)
