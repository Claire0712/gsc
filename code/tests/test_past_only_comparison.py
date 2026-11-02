import importlib
import unittest

class PastComparisonTest(unittest.TestCase):
    def test_requires_explicit_past_only_ancestor(self):
        validate=importlib.import_module('scripts.run_past_only_comparison').validate_past_only
        validate({'past_only_sensitivity_computed':True})
        for summary in ({},{'past_only_sensitivity_computed':False},{'past_only_sensitivity_computed':'True'}):
            with self.assertRaises(ValueError):validate(summary)

if __name__=='__main__':unittest.main()
