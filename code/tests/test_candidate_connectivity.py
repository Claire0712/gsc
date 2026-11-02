import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/audit_candidate_connectivity.py'


class CandidateConnectivityTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'candidate connectivity implementation missing')
        spec = importlib.util.spec_from_file_location('candidate_connectivity', SCRIPT)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pre = self.root / 'pre'
        self.conn = self.root / 'conn'
        self.out = self.root / 'out'
        self.pre.mkdir()
        self.conn.mkdir()
        self.events = [self.event('forward'), self.event('held'), self.event('cold', weather_candidate='False'), self.event('unmatched', country_id='BBB')]
        self.stop = [{'event_id': 'held', 'source_row': '1', 'review_only': '1'}]
        self.cross = [dict(ioda_iso2='AA', joint_country_id='AAA', joint_status='exact_joint_match')]
        self.write_pre()
        self.outputs = []
        for q in self.m.QUARTERS:
            start, end = self.m.quarter_bounds(q)
            for signal in self.m.SIGNALS:
                path = self.conn / f'ioda_{q}_{signal}.npz'
                np.savez_compressed(path, values=np.zeros((1, (end-start)//600), dtype=np.float64), country_ids=np.array(['AA']), native_phase_seconds=np.array([0]), interval_start_utc=np.arange(start, end, 600, dtype=np.int64))
                self.outputs.append(dict(file=path.name, sha256=self.sha(path), bytes=path.stat().st_size))
        self.write_conn_manifest()

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def event(self, eid, **kwargs):
        return dict(dict(event_id=eid, country_id='AAA', start_date='2023-12-31', end_exclusive_utc='2024-01-02T00:00:00Z', weather_candidate='True', network_screened='0', review_window_start_utc='2023-12-31T00:00:00Z', review_window_end_exclusive_utc='2024-01-05T00:00:00Z', review_only='1'), **kwargs)

    def write_pre(self):
        outputs = {}
        for name, rows, fields in [('event_review_windows.csv', self.events, list(self.events[0])), ('joint_crosswalk.csv', self.cross, list(self.cross[0])), ('stop_event_review.csv', self.stop, ['event_id', 'source_row', 'review_only'])]:
            with (self.pre / name).open('w', newline='') as f:
                w = csv.DictWriter(f, fields)
                w.writeheader()
                w.writerows(rows)
            outputs[name] = dict(sha256=self.sha(self.pre / name))
        (self.pre / 'manifest.json').write_text(json.dumps(dict(outputs=outputs)))
        (self.pre / 'status.json').write_text(json.dumps(dict(status='completed')))

    def write_conn_manifest(self):
        (self.conn / 'manifest.json').write_text(json.dumps(dict(state='complete', quarters=self.m.QUARTERS, outputs=self.outputs)))

    def mutate(self, q='2024Q1', signal='bgp', **changes):
        path = self.conn / f'ioda_{q}_{signal}.npz'
        with np.load(path) as data:
            arrays = {k: data[k] for k in data.files}
        arrays.update(changes)
        np.savez_compressed(path, **arrays)
        next(o for o in self.outputs if o['file'] == path.name).update(sha256=self.sha(path), bytes=path.stat().st_size)
        self.write_conn_manifest()

    def run_stage(self):
        return self.m.main(['--preflight-dir', str(self.pre), '--connection-dir', str(self.conn), '--output-dir', str(self.out)])

    def rows(self, name):
        with (self.out / name).open() as f:
            return list(csv.DictReader(f))

    def test_routes_and_complete_zero_windows_cross_year(self):
        self.assertEqual(self.run_stage(), 0)
        self.assertEqual({r['event_id']: r['route'] for r in self.rows('event_routing.csv')}, dict(forward='forward', held='held_stop_review', cold='not_weather_candidate', unmatched='unmatched_country'))
        for row in self.rows('signal_window_audit.csv'):
            self.assertEqual(int(row['expected_core_slots']), 288)
            self.assertEqual(int(row['expected_full_slots']), 720)
            self.assertEqual(int(row['zero_full_slots']), 720)
            self.assertEqual(row['complete_full'], 'True')
            self.assertEqual(float(row['unmasked_potential_reference_fraction']), 1)
            self.assertEqual(row['downstream_ready_for_baseline'], 'False')
        manifest = json.loads((self.out / 'manifest.json').read_text())
        for name, metadata in manifest['outputs'].items():
            self.assertEqual(metadata['sha256'], self.sha(self.out / name))
        self.assertEqual(manifest['script_sha256'], self.sha(SCRIPT))
        self.assertEqual(manifest['observed_native_phase_seconds']['AA/bgp'], 0)
        self.assertEqual(self.run_stage(), 1)

    def test_missing_is_not_zero(self):
        start, end = self.m.quarter_bounds('2024Q1')
        values = np.zeros((1, (end-start)//600))
        values[0, 0] = np.nan
        self.mutate(values=values)
        self.assertEqual(self.run_stage(), 0)
        row = next(r for r in self.rows('signal_window_audit.csv') if r['signal'] == 'bgp')
        self.assertEqual(int(row['valid_full_slots']), 719)
        self.assertEqual(int(row['zero_full_slots']), 719)
        self.assertEqual(row['complete_full'], 'False')

    def test_reference_rule_requires_four_and_both_directions(self):
        valid = np.array([[1, 1, 1], [1, 1, 1], [1, 0, 0], [1, 0, 0], [0, 1, 1], [0, 1, 0], [0, 0, 0], [0, 0, 0]], dtype=bool)
        np.testing.assert_array_equal(self.m.reference_gate(valid), [False, True, False])

    def test_boundary_truncation(self):
        self.events[0] = self.event('forward', start_date='2021-12-31', end_exclusive_utc='2022-01-02T00:00:00Z', review_window_start_utc='2021-12-31T00:00:00Z', review_window_end_exclusive_utc='2022-01-05T00:00:00Z')
        self.write_pre()
        self.assertEqual(self.run_stage(), 0)
        for row in self.rows('signal_window_audit.csv'):
            self.assertEqual(row['analysis_boundary_truncated'], 'True')
            self.assertEqual(row['complete_full'], 'False')
            self.assertEqual(int(row['valid_full_slots']), 576)

    def test_missing_country_explicit(self):
        self.mutate(country_ids=np.array(['BB']))
        self.assertEqual(self.run_stage(), 0)
        row = next(r for r in self.rows('signal_window_audit.csv') if r['signal'] == 'bgp')
        self.assertEqual(row['missing_country'], 'True')

    def test_corruption_failure_and_no_outputs(self):
        path = self.conn / self.outputs[0]['file']
        path.write_bytes(b'corrupt')
        self.assertEqual(self.run_stage(), 1)
        self.assertEqual(json.loads((self.out / 'status.json').read_text())['status'], 'failed')
        self.assertFalse((self.out / 'event_routing.csv').exists())

    def test_invalid_shape_and_phase(self):
        self.mutate(native_phase_seconds=np.array([600]))
        self.assertEqual(self.run_stage(), 1)

    def test_phase_change_fails_stage(self):
        self.mutate(native_phase_seconds=np.array([1]))
        self.assertEqual(self.run_stage(), 1)
        self.assertIn('phase', json.loads((self.out / 'status.json').read_text())['error'])

    def test_no_phase_cannot_contain_values(self):
        self.mutate(native_phase_seconds=np.array([-1]))
        self.assertEqual(self.run_stage(), 1)

    def test_invalid_dimensions(self):
        self.mutate(values=np.ones((1, 2)))
        self.assertEqual(self.run_stage(), 1)

    def test_strict_bool_and_unknown_stop(self):
        self.events[0]['weather_candidate'] = 'yes'
        self.write_pre()
        self.assertEqual(self.run_stage(), 1)

    def test_unknown_stop(self):
        self.stop[0]['event_id'] = 'unknown'
        self.write_pre()
        self.assertEqual(self.run_stage(), 1)

    def test_exclusive_lock(self):
        lock = self.root / '.out.lock'
        lock.write_text('existing')
        self.assertEqual(self.run_stage(), 1)
        self.assertEqual(lock.read_text(), 'existing')
        self.assertFalse(self.out.exists())

    def test_progress_and_input_stat_guard(self):
        updates = []
        stamps = self.m.connection_stats(self.conn)
        self.m.validate_archives(self.conn, progress=lambda **kw: updates.append(kw))
        self.assertEqual(updates[-1]['validated_archives'], 48)
        cache = self.m.QuarterCache(self.conn, 'bgp', stamps)
        path = self.conn / 'ioda_2024Q1_bgp.npz'
        path.touch()
        with self.assertRaisesRegex(ValueError, 'changed'):
            cache.sample('AA', np.array([self.m.quarter_bounds('2024Q1')[0]]))

    def test_preflight_hash_and_duplicate_event(self):
        self.events.append(dict(self.events[0]))
        self.write_pre()
        self.assertEqual(self.run_stage(), 1)

    def test_preflight_mutation_after_hashes_rejected(self):
        original = self.m.verify_outputs
        def mutate_after_verification(directory, entries):
            result = original(directory, entries)
            if directory == self.conn.resolve():
                self.events[0]['weather_candidate'] = 'False'
                self.write_pre()
            return result
        self.m.verify_outputs = mutate_after_verification
        self.assertEqual(self.run_stage(), 1)
        self.assertIn('changed', json.loads((self.out / 'status.json').read_text())['error'])

    def test_manifest_mutation_during_audit_rejected(self):
        original = self.m.audit_events
        def mutate_after_audit(*args, **kwargs):
            result = original(*args, **kwargs)
            path = self.conn / 'manifest.json'
            path.write_text(path.read_text() + '\n')
            return result
        self.m.audit_events = mutate_after_audit
        self.assertEqual(self.run_stage(), 1)
        self.assertIn('changed', json.loads((self.out / 'status.json').read_text())['error'])

    def test_audit_chronology_preserves_routing_order(self):
        early = self.event('early', start_date='2023-01-01', end_exclusive_utc='2023-01-02T00:00:00Z', review_window_start_utc='2023-01-01T00:00:00Z', review_window_end_exclusive_utc='2023-01-05T00:00:00Z')
        self.events.append(early)
        self.write_pre()
        self.assertEqual(self.run_stage(), 0)
        self.assertEqual([r['event_id'] for r in self.rows('event_routing.csv')], [r['event_id'] for r in self.events])
        self.assertEqual([r['event_id'] for r in self.rows('signal_window_audit.csv') if r['signal'] == 'bgp'], ['early', 'forward'])


if __name__ == '__main__':
    unittest.main()
