import unittest,importlib.util
import numpy as np
class InferenceTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.curve_inference'),'implementation missing')
        from scripts.curve_inference import covariance,diagnostics
        return covariance,diagnostics
    def test_manual_scores(self):
        c,_=self.api();x=np.array([[1.,0],[1,1],[1,2],[1,3]]);u=np.array([.3,-.2,.1,-.2]);g=[0,0,1,1]
        scores=np.array([x[:2].T@u[:2],x[2:].T@u[2:]]);bread=np.linalg.inv(x.T@x)
        np.testing.assert_allclose(c(x,u,g),bread@scores.T@scores@bread)
    def test_single_group_rejected(self):
        c,_=self.api()
        with self.assertRaises(ValueError):c(np.eye(2),np.ones(2),[0,0])
    def test_indefinite_not_repaired(self):
        _,d=self.api();r=d(np.ones(2),np.array([[1.,2],[2,1]]),[0])
        self.assertFalse(r['psd']);self.assertIsNone(r['interval95']);self.assertIsNone(r['lead_test'])
    def test_joint(self):
        _,d=self.api();r=d(np.array([1.,2.]),np.eye(2),[0,1]);self.assertAlmostEqual(r['lead_test']['chi2'],5)
