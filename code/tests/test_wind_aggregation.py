import unittest
import numpy as np
from scipy import sparse
from scripts.aggregate_archived_wind import aggregate
from scripts import aggregate_archived_wind as core

class WindAggregation(unittest.TestCase):
    def test_pilot_compares_identically_limited_uv_dates(self):
        self.assertEqual(core.match_days([1],[1,2],1),[1])
        with self.assertRaises(ValueError):core.match_days([1],[2,3],1)
    def test_partial_support_normalizes_only_valid_mass(self):
        mean,support=aggregate(sparse.csr_matrix([[1.,3.],[0.,0.]]),np.array([2.,np.nan]))
        np.testing.assert_allclose(mean[0],2.)
        np.testing.assert_allclose(support[0],.25)
        self.assertTrue(np.isnan(mean[1]));self.assertTrue(np.isnan(support[1]))
    def test_zero_wind_and_negative_component_are_valid(self):
        mean,support=aggregate(sparse.csr_matrix([[1.,1.]]),np.array([0.,-2.]))
        self.assertEqual(mean[0],-1.)
        self.assertEqual(support[0],1.)
