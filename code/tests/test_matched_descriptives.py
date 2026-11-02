import unittest,importlib.util

class DescriptiveTests(unittest.TestCase):
    def test_pilot_option(self):
        import subprocess,sys
        r=subprocess.run([sys.executable,'-m','scripts.run_matched_descriptives','--help'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0);self.assertIn('--country',r.stdout)
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.matched_descriptives'),'implementation missing')
        from scripts.matched_descriptives import summary,paired
        return summary,paired
    def test_weighted_mean(self):
        s,_=self.api();r=s([1,3],[3,1]);self.assertEqual(r['mean'],1.5);self.assertEqual(r['variance'],.75)
    def test_missing_not_zero(self):
        s,_=self.api()
        with self.assertRaises(ValueError):s([1,None],[1,1])
    def test_equal_event_controls(self):
        _,p=self.api();self.assertEqual(p(10,[2,4]),7)
    def test_zero_variance(self):
        s,_=self.api();self.assertEqual(s([2,2],[1,1])['variance'],0)
    def test_empty_controls(self):
        _,p=self.api()
        with self.assertRaises(ValueError):p(1,[])
