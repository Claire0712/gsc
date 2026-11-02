import importlib
from pathlib import Path
import unittest

class AncestryTest(unittest.TestCase):
    def test_relative_absolute_and_ambiguous_paths(self):
        lookup=importlib.import_module('scripts.run_variant_matched_descriptives').ancestry_entry
        path=Path('analysis/example/manifest.json');entry={'sha256':'abc','bytes':3}
        self.assertEqual(lookup({str(path):entry},path.resolve()),entry)
        self.assertEqual(lookup({str(path.resolve()):entry},path),entry)
        with self.assertRaises(ValueError):lookup({},path)
        with self.assertRaises(ValueError):lookup({str(path):entry,str(path.resolve()):entry},path)

if __name__=='__main__':unittest.main()
