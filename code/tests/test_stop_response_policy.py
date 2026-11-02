import unittest

class PolicyTests(unittest.TestCase):
    def test_unknown_end_sensitivity_retained_and_counted(self):
        from scripts.stop_response_policy import require_main_clear
        e={'main':{'heat':[],'control':[]},'unknown_end_plusminus7':{'heat':['2'],'control':[]},'unknown_end_plusminus30':{'heat':['2'],'control':['3']}}
        self.assertEqual(require_main_clear(e),{'unknown_end_plusminus7':True,'unknown_end_plusminus30':True})
        self.assertEqual(e['unknown_end_plusminus7']['heat'],['2'])
    def test_main_overlap_rejected(self):
        from scripts.stop_response_policy import require_main_clear
        with self.assertRaises(ValueError):require_main_clear({'main':{'heat':['1'],'control':[]}})
    def test_absent_main_is_not_clear(self):
        from scripts.stop_response_policy import require_main_clear
        with self.assertRaises(ValueError):require_main_clear({})
