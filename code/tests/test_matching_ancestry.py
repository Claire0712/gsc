from pathlib import Path
import unittest

class AncestryTests(unittest.TestCase):
    def test_relative_and_absolute_same_identity(self):
        from scripts.run_variant_matching import ancestry_entry
        p=Path('analysis/example/manifest.json')
        expected={'sha256':'abc','bytes':4}
        self.assertEqual(ancestry_entry({str(p):expected},p.resolve()),expected)
        self.assertEqual(ancestry_entry({str(p.resolve()):expected},p),expected)

    def test_missing_or_ambiguous_rejected(self):
        from scripts.run_variant_matching import ancestry_entry
        p=Path('analysis/example/manifest.json')
        with self.assertRaises(ValueError):ancestry_entry({},p)
        with self.assertRaises(ValueError):ancestry_entry({str(p):{},str(p.resolve()):{}},p)
