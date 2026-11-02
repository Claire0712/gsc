import importlib.util
import json
import gzip
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import prepare_ioda_quality as qa


class MaterializationTests(unittest.TestCase):
    def module(self):
        p = ROOT / 'scripts/materialize_ioda_10min.py'
        self.assertTrue(p.exists(), 'Materializer not implemented yet')
        spec = importlib.util.spec_from_file_location('materialize', p)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def grid(self, values, phase=0):
        grid = qa.SignalGrid(len(values))
        grid.phases.add(phase)
        grid.add_values(0, np.asarray(values, dtype=float), np.array([x is None for x in values]))
        return grid

    def test_ap_preserves_zero_and_missing(self):
        m = self.module()
        result, phase = m.ten_minute_values(self.grid([0, None, 5]), 'ping-slash24')
        np.testing.assert_allclose(result, [0, np.nan, 5], equal_nan=True)
        self.assertEqual(phase, 0)

    def test_five_minute_requires_two_complete_slots(self):
        m = self.module()
        result, phase = m.ten_minute_values(self.grid([0, 2, None, 4, 6, 8], 60), 'bgp')
        np.testing.assert_allclose(result, [1, np.nan, 7], equal_nan=True)
        self.assertEqual(phase, 60)

    def test_conflict_excludes_whole_pair(self):
        m = self.module()
        grid = self.grid([2, 4, 6, 8])
        grid.add_values(0, np.array([3.0]), np.array([False]))
        result, _ = m.ten_minute_values(grid, 'merit-nt')
        self.assertTrue(np.isnan(result[0]))
        self.assertEqual(result[1], 7)

    def test_incompatible_phase_fails(self):
        m = self.module()
        grid = self.grid([1, 2])
        grid.phases.add(60)
        with self.assertRaises(ValueError):
            m.ten_minute_values(grid, 'bgp')

    def test_negative_nonfinite_excluded_without_zero_fill(self):
        m = self.module()
        values, _ = m.ten_minute_values(self.grid([-1, float('inf'), 0]), 'ping-slash24')
        np.testing.assert_allclose(values, [np.nan, np.nan, 0], equal_nan=True)

    def test_empty_native_grid_stays_missing(self):
        m = self.module()
        values, phase = m.ten_minute_values(qa.SignalGrid(4), 'bgp')
        self.assertEqual(phase, -1)
        self.assertTrue(np.isnan(values).all())
        self.assertEqual(len(values), 2)

    def test_leap_quarter_and_parse(self):
        m = self.module()
        self.assertEqual(m.parse_quarter('2024Q1'), (2024, 1))
        start, end = qa.quarter_bounds(2024, 1)
        self.assertEqual((end-start)//600, 91*144)
        for value in ('2021Q1', '2024Q5', '../../x'):
            with self.assertRaises(ValueError):
                m.parse_quarter(value)

    def test_archive_audit_and_corrupt_resume(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'ioda_2024Q1_bgp.npz'
            provenance = {'script': 'abc', 'input': 'def'}
            m.write_archive(p, np.array([[1., np.nan]]), ['CN'], np.array([60]), np.array([0, 600]), provenance)
            self.assertTrue(m.valid_archive(p, provenance))
            self.assertFalse(m.valid_archive(p, {'script': 'changed'}))
            with p.open('ab') as f:
                f.write(b'corrupt')
            self.assertFalse(m.valid_archive(p, provenance))

    def test_qa_manifest_requires_clean_complete_and_hashes(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'summary.json').write_text('{"state":"completed","quality_pass":false}')
            with self.assertRaises(ValueError):
                m.load_qa(root)

    def test_exclusive_lock_blocks_second_run(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as td:
            with m.run_lock(Path(td)):
                with self.assertRaises(RuntimeError):
                    with m.run_lock(Path(td)):
                        self.fail('second writer acquired lock')

    def fixture(self, root):
        data = root / 'data'
        folder = data / 'ioda/raw_core_signals'
        folder.mkdir(parents=True)
        for quarter, phase in ((1, 0), (2, 60)):
            start, end = qa.quarter_bounds(2024, quarter)
            signal = {'entityType':'country','entityCode':'CN','datasource':'ping-slash24',
                      'step':600,'nativeStep':600,'from':start+phase,'until':start+phase+1800,
                      'values':[0, 2, None]}
            raw = {'requestParameters':{'from':start,'until':end},'data':[[signal]],'error':None}
            path = folder / f'q{quarter}.json.gz'
            path.write_bytes(gzip.compress(json.dumps(raw).encode()))
            meta = {'file':str(path.relative_to(data)), 'countries':['CN'], 'year':2024,
                    'quarter':quarter,'datasource':'ping-slash24',**qa.fingerprint(path)}
            (folder/f'q{quarter}.metadata.json').write_text(json.dumps(meta))
        qa_dir = root/'qa'
        qa.run(data, qa_dir)
        return data, qa_dir

    def test_end_to_end_and_resume_preserve_phase_review(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data, audit = self.fixture(root)
            out = root/'out'
            m.materialize(data, audit, out, ['2024Q1'])
            status = m.materialize(data, audit, out, ['2024Q1','2024Q2'], resume=True)
            self.assertEqual(status['phase_changes']['CN/ping-slash24'], [0,60])
            self.assertEqual(status['output_archives'], 6)
            with np.load(out/'ioda_2024Q1_ping-slash24.npz', allow_pickle=False) as bundle:
                self.assertEqual(bundle['values'].shape, (1,91*144))
                np.testing.assert_allclose(bundle['values'][0,:3], [0,2,np.nan], equal_nan=True)
            self.assertFalse(status['downstream_ready_for_baseline'])

    def test_changed_raw_input_fails_before_output(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data, audit = self.fixture(root)
            (data/'ioda/raw_core_signals/q1.json.gz').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                m.materialize(data, audit, root/'out', ['2024Q1'])
            self.assertEqual(json.loads((root/'out/status.json').read_text())['state'], 'failed')

    def test_failed_rerun_invalidates_completed_manifest(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data, audit = self.fixture(root)
            out = root/'out'
            m.materialize(data, audit, out, ['2024Q1'])
            (data/'ioda/raw_core_signals/q1.json.gz').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                m.materialize(data, audit, out, ['2024Q1'], resume=True)
            self.assertEqual(json.loads((out/'manifest.json').read_text())['state'], 'failed')


if __name__ == '__main__':
    unittest.main()
