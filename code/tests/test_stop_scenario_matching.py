import unittest

class ScenarioTests(unittest.TestCase):
    def test_curve_only_overlap_does_not_disable_integral(self):
        from scripts.stop_scenario_matching import apply_scenario
        w=[{'window_id':'a','matching_technical_available':'True','matching_curve_technical_available':'True'}]
        review=[{'window_id':'a','overlaps':{p:{'unknown_end_plusminus7':(['x'] if p=='curve' else [])} for p in ['preperiod','integral','curve']}}]
        r=apply_scenario(w,review,'unknown_end_plusminus7')
        self.assertEqual(r[0]['matching_technical_available'],'True')
        self.assertEqual(r[0]['matching_curve_technical_available'],'False')
        self.assertEqual(w[0]['matching_curve_technical_available'],'True')
    def test_preperiod_blocks_both_and_missing_is_error(self):
        from scripts.stop_scenario_matching import apply_scenario
        w=[{'window_id':'a','matching_technical_available':'True','matching_curve_technical_available':'True'}]
        review=[{'window_id':'a','overlaps':{p:{'unknown_end_plusminus30':(['x'] if p=='preperiod' else [])} for p in ['preperiod','integral','curve']}}]
        r=apply_scenario(w,review,'unknown_end_plusminus30')
        self.assertEqual(r[0]['matching_technical_available'],'False')
        self.assertEqual(r[0]['matching_curve_technical_available'],'False')
        with self.assertRaises(ValueError):apply_scenario(w,[],'unknown_end_plusminus30')
