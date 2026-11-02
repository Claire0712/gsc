import unittest
import numpy as np

class HealthTests(unittest.TestCase):
    def test_regular_fit_accepted(self):
        from scripts.cox_fit_health import assess
        self.assertIsNone(assess(np.array([.1]),np.array([1e-10]),np.eye(1),np.eye(1),[]))
    def test_flat_separated_fit_not_rescued_by_small_score(self):
        from scripts.cox_fit_health import assess
        self.assertIn('information',assess(np.array([200.]),np.array([1e-12]),np.eye(1),np.array([[1e-12]]),[]))
    def test_nonconvergence_and_invalid_covariance(self):
        from scripts.cox_fit_health import assess
        self.assertIn('converg',assess(np.array([.1]),np.zeros(1),np.eye(1),np.eye(1),['Maximum Likelihood optimization failed to converge.']))
        self.assertIsNotNone(assess(np.array([.1]),np.zeros(1),np.array([[np.nan]]),np.eye(1),[]))
        self.assertIsNotNone(assess(np.array([.1]),np.zeros(1),-np.eye(1),np.eye(1),[]))
