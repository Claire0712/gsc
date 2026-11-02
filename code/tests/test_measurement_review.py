import unittest
from pathlib import Path
import numpy as np

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(Path('scripts/measurement_review.py').exists(),'implementation missing')
        from scripts.measurement_review import diagnose
        self.d=diagnose;self.v=np.full(1440,100.);self.t=np.arange(1440)*600
    def run_case(self):return self.d(self.t,self.v,self.t<604800)
    def test_stable(self):self.assertEqual(self.run_case()['flags'],[])
    def test_nearzero(self):
        self.v[1100:1244]=1
        r=self.run_case();self.assertEqual(r['longest_nearzero_slots'],144);self.assertIn('nearzero_24h',r['flags'])
    def test_missing_break(self):
        self.v[1100:1244]=0;self.v[1170]=np.nan
        self.assertNotIn('nearzero_24h',self.run_case()['flags'])
    def test_levelshift(self):
        self.v[-144:]=200
        self.assertIn('level_change_candidate',self.run_case()['flags'])
    def test_nonpositive_pre(self):
        self.v[:1008]=0
        self.assertFalse(self.run_case()['normalized_diagnostics_available'])
    def test_iqr(self):
        self.v[:504]=1;self.v[504:1008]=300
        self.assertIn('pre_variability_candidate',self.run_case()['flags'])
    def test_grid(self):
        self.t[-1]+=1
        with self.assertRaises(ValueError):self.run_case()

class DriverTests(unittest.TestCase):
    def test_existing_output(self):
        self.assertTrue(Path('scripts/run_measurement_review.py').exists(),'driver missing')
        from scripts.run_measurement_review import run
        from types import SimpleNamespace
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as d:
            with self.assertRaises(FileExistsError):run(SimpleNamespace(output=d))
