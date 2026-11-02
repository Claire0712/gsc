import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

class RunTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(Path('scripts/run_matching.py').exists(),'implementation missing')
        from scripts.run_matching import run
        self.run=run
    def test_existing_output_rejected(self):
        with TemporaryDirectory() as p:
            with self.assertRaises(FileExistsError):self.run(SimpleNamespace(output=p))
    def test_missing_stage_no_output(self):
        with TemporaryDirectory() as p:
            out=Path(p)/'out'
            with self.assertRaises(FileNotFoundError):self.run(SimpleNamespace(output=str(out),comparison=str(Path(p)/'missing')))
            self.assertFalse(out.exists())
