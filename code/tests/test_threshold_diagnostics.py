import unittest
import numpy as np
from scripts.threshold_diagnostics import quantile
class ThresholdTests(unittest.TestCase):
    def test_linear_and_year_coverage(self):
        self.assertEqual(quantile(np.arange(124.),np.repeat([2018,2019,2020,2021],31),.9)[0],110.7)
        self.assertIsNone(quantile(np.arange(93.),np.repeat([2018,2019,2020],31),.9)[0])
        self.assertIsNone(quantile(np.arange(93.),np.repeat([2018,2019,2020],31),.9,2019)[0])
        self.assertAlmostEqual(quantile(np.arange(124.),np.repeat([2018,2019,2020,2021],31),.9,2019)[0],113.8)
    def test_missing_coverage_not_zero(self):
        self.assertIsNone(quantile(np.array([np.nan]*124),np.repeat([2018,2019,2020,2021],31),.9)[0])
