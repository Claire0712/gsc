import unittest
import numpy as np
from scripts.run_heat_inference import marginal_p

class InferenceTest(unittest.TestCase):
    def test_normal(self):
        self.assertAlmostEqual(marginal_p(1.959963984540054,1),.05)
        self.assertEqual(marginal_p(0,1),1)
    def test_degenerate_not_evidence(self):
        self.assertIsNone(marginal_p(2,0))
        with self.assertRaises(ValueError):marginal_p(1,-1)
        with self.assertRaises(ValueError):marginal_p(np.nan,1)

if __name__=='__main__':unittest.main()
