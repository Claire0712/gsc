import importlib.util
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/run_era5_existing_data.py'


class RunTests(unittest.TestCase):
    def module(self):
        self.assertTrue(SCRIPT.exists(), 'The ERA5 run coordinator is not implemented yet')
        spec = importlib.util.spec_from_file_location('era5_run', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_success_status_contains_all_completed_steps(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = module.execute_steps(root, [('pilot', [sys.executable, '-c', 'print(123)'])], 0.01)
            self.assertEqual(code, 0)
            state = json.loads((root / 'status.json').read_text())
            self.assertEqual(state['state'], 'complete')
            self.assertEqual(state['completed_stages'], ['pilot'])

    def test_failed_pilot_prevents_full_run(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / 'must_not_exist'
            steps = [('pilot', [sys.executable, '-c', 'raise SystemExit(3)']),
                     ('full', [sys.executable, '-c', f'from pathlib import Path; Path({str(marker)!r}).touch()'])]
            self.assertEqual(module.execute_steps(root, steps, 0.01), 3)
            self.assertFalse(marker.exists())
            state = json.loads((root / 'status.json').read_text())
            self.assertEqual(state['state'], 'failed')
            self.assertEqual(state['stage'], 'pilot')
            self.assertEqual(state['exit_code'], 3)

    def test_lock_blocks_duplicate_launch(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            with module.run_lock(Path(directory)):
                with self.assertRaises(RuntimeError):
                    with module.run_lock(Path(directory)):
                        self.fail('Duplicate acquired the lock')

    def test_pilot_gate_rejects_missing_or_inverted_temperatures(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'validate_pilot'), 'Pilot gate is not implemented')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = {'missing_hour_count': 0, 'country_count': 1, 'day_count': 31, 'rows': 31}
            (root / 'era5_country_daily_201801.audit.json').write_text(json.dumps(audit))
            fields = ['country_id', 'date', 'total_population', 'tmin_c', 'tmax_c', 'dewpoint_c', 'hours_present', 'pop_valid_fraction']
            rows = [dict(zip(fields, ['AAA', f'2018-01-{d:02d}', 100, 20, 30, 15, 24, 1])) for d in range(1, 32)]
            def save():
                with (root / 'era5_country_daily_201801.csv').open('w') as handle:
                    writer = csv.DictWriter(handle, fields)
                    writer.writeheader()
                    writer.writerows(rows)
            save()
            module.validate_pilot(root, '201801')
            rows[0]['tmin_c'] = 'nan'
            save()
            with self.assertRaises(ValueError):
                module.validate_pilot(root, '201801')
            rows[0]['tmin_c'] = 35
            save()
            with self.assertRaises(ValueError):
                module.validate_pilot(root, '201801')


if __name__ == '__main__':
    unittest.main()
