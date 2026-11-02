import importlib
import unittest

class ConsistencyTest(unittest.TestCase):
    def test_baseline_scenario_must_match(self):
        validate=importlib.import_module('scripts.run_stop_scenario_comparison').validate_scenario
        for scenario in ('unknown_end_plusminus7','unknown_end_plusminus30'):
            validate({'stop_scenario':scenario,'reference_remasking':True},scenario)
            for summary in ({}, {'stop_scenario':'main','reference_remasking':True},
                            {'stop_scenario':scenario,'reference_remasking':False}):
                with self.assertRaises(ValueError):validate(summary,scenario)
        with self.assertRaises(ValueError):validate({'stop_scenario':'other','reference_remasking':True},'other')

if __name__=='__main__':unittest.main()
