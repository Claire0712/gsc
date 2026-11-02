import importlib
import unittest
import numpy as np
from tests.test_connection_baseline_runner import BaselineRunnerTests as Fixture

class PastRunnerTest(unittest.TestCase):
    def test_runner_uses_four_past_references_and_separate_metadata(self):
        f=Fixture();f.setUp();self.addCleanup(f.doCleanups)
        f.m=importlib.import_module('scripts.run_past_only_baseline')
        report=f.run_stage();points=f.points()
        np.testing.assert_array_equal(points['reference_offsets_days'],[-28,-21,-14,-7])
        self.assertEqual(points['reference_exclusion_bits'].shape[1],4)
        self.assertTrue(np.all(points['after_count']==0))
        self.assertEqual(points['reference_count'][0],2)
        self.assertFalse(points['baseline_available'][0])
        self.assertTrue(report['past_only_sensitivity_computed'])
        self.assertFalse(report['final_sample_eligible'])

if __name__=='__main__':unittest.main()
