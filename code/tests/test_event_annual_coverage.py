import calendar
from contextlib import redirect_stderr
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/screen_event_annual_coverage.py'
SIGNALS = {'ping-slash24': 600, 'bgp': 300, 'merit-nt': 300}


def csv_bytes(rows):
    f = io.StringIO(newline='')
    writer = csv.DictWriter(f, list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return f.getvalue().encode()


def digest(data):
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


def annual(year=2023, signal='bgp', valid=None):
    n = (366 if calendar.isleap(year) else 365) * 86400 // SIGNALS[signal]
    valid = n if valid is None else valid
    return dict(country_id='US', year=year, signal=signal, expected_points=n,
                valid_points=valid, candidate_80pct=5 * valid >= 4 * n)


def event(signal='bgp', start='2023-12-31T00:00:00Z', end='2024-01-02T00:00:00Z'):
    return dict(event_id='e1', country_id='US', ioda_iso2='US', signal=signal,
                core_start_utc=start, full_end_exclusive_utc=end, complete_full=True,
                unmasked_potential_reference_all_slots=True, original_extra='keep me')


class AnnualScreenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = None
        if SCRIPT.exists():
            spec = importlib.util.spec_from_file_location('annual_screen', SCRIPT)
            cls.mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.mod)

    def setUp(self):
        self.assertIsNotNone(self.mod, 'annual screening implementation must exist')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.q, self.c, self.out = [self.root / p for p in ('quality', 'candidate', 'out')]
        self.q.mkdir()
        self.c.mkdir()

    def setup_inputs(self, annuals=None, events=None, quality_pass=True):
        annuals = annuals if annuals is not None else [annual(2023), annual(2024)]
        events = events if events is not None else [event()]
        qfiles = {'coverage_annual.csv': csv_bytes(annuals),
                  'coverage_quarterly.csv': b'unconsumed,but verified\n',
                  'summary.json': json.dumps({'quality_pass': quality_pass}).encode()}
        cfiles = {'signal_window_audit.csv': csv_bytes(events), 'summary.json': b'{}'}
        for directory, files in ((self.q, qfiles), (self.c, cfiles)):
            for name, data in files.items():
                (directory / name).write_bytes(data)
        (self.q / 'manifest.json').write_text(json.dumps({'state': 'completed', 'outputs': [dict(file=n, **digest(d)) for n, d in qfiles.items()]}))
        (self.c / 'manifest.json').write_text(json.dumps({'outputs': {n: dict(digest(d), **({'rows': len(events)} if n.endswith('.csv') else {})) for n, d in cfiles.items()}}))
        (self.c / 'status.json').write_text('{"status":"completed"}')

    def run_stage(self):
        with redirect_stderr(io.StringIO()):
            return self.mod.run(self.q, self.c, self.out)

    def rows(self):
        return list(csv.DictReader(io.StringIO((self.out / 'annual_event_screen.csv').read_text())))

    def test_integration_preserves_fields_and_records_hashes(self):
        self.setup_inputs(events=[event(s) for s in SIGNALS], annuals=[annual(y, s) for y in (2023, 2024) for s in SIGNALS])
        self.assertEqual(self.run_stage(), 0)
        row = self.rows()[0]
        self.assertEqual(list(row)[:len(event())], list(event()))
        self.assertEqual(row['original_extra'], 'keep me')
        self.assertEqual(row['annual_years'], '2023;2024')
        self.assertEqual(row['final_sample_eligible'], 'False')
        summary = json.loads((self.out / 'summary.json').read_text())
        self.assertEqual(summary['common_events_all_three_signals_provisional'], 1)
        self.assertEqual(summary['cross_year_events'], 1)
        self.assertFalse(summary['downstream_ready_for_baseline'])
        manifest = json.loads((self.out / 'manifest.json').read_text())
        for name, meta in manifest['outputs'].items():
            self.assertEqual(digest((self.out / name).read_bytes()), {k: meta[k] for k in ('sha256', 'bytes')})
        self.assertEqual(manifest['inputs']['quality']['outputs']['coverage_annual.csv'], digest((self.q / 'coverage_annual.csv').read_bytes()))
        self.assertEqual(manifest['script_sha256'], digest(SCRIPT.read_bytes())['sha256'])
        self.assertEqual(json.loads((self.out / 'status.json').read_text())['status'], 'completed')

    def test_threshold_leap_crossyear_start_vs_all(self):
        a = annual(2024)
        a['valid_points'] = a['expected_points'] * 4 // 5 - 1
        a['candidate_80pct'] = False
        self.setup_inputs(annuals=[annual(2023, valid=105120 * 4 // 5), a])
        self.assertEqual(self.run_stage(), 0)
        row = self.rows()[0]
        self.assertEqual(row['annual_start_year_pass'], 'True')
        self.assertEqual(row['annual_all_window_years_pass'], 'False')
        self.assertEqual(row['annual_failed_years'], '2024')

    def test_january_first_exclusive_end(self):
        self.setup_inputs(annuals=[annual()], events=[event(end='2024-01-01T00:00:00Z')])
        self.assertEqual(self.run_stage(), 0)
        self.assertEqual(self.rows()[0]['annual_years'], '2023')
        self.assertEqual(self.rows()[0]['annual_all_window_years_pass'], 'True')

    def test_missing_year_explicit_failure(self):
        self.setup_inputs(annuals=[annual()])
        self.assertEqual(self.run_stage(), 0)
        self.assertEqual(self.rows()[0]['annual_missing_years'], '2024')
        self.assertEqual(self.rows()[0]['provisional_full_refs_and_annual'], 'False')

    def test_reject_invalid_annuals(self):
        variants = [dict(valid_points=-1), dict(valid_points=9999999), dict(expected_points=1),
                    dict(candidate_80pct='true'), dict(candidate_80pct=False), dict(year=2021),
                    dict(signal='unknown'), dict(valid_points='1.5')]
        for variant in variants:
            with self.subTest(variant=variant):
                self.setup_inputs(annuals=[dict(annual(), **variant)])
                self.out = self.root / ('out' + str(len(list(self.root.iterdir()))))
                self.assertEqual(self.run_stage(), 1)

    def test_duplicate_keys(self):
        for annuals, events in (([annual(), annual()], [event()]), ([annual()], [event(), event()])):
            self.setup_inputs(annuals, events)
            self.out = self.root / ('out' + str(len(list(self.root.iterdir()))))
            self.assertEqual(self.run_stage(), 1)

    def test_bad_candidate_fields(self):
        for changes in [dict(core_start_utc='2023-12-31T00:00:00'), dict(core_start_utc='2023-12-31T00:01:00Z'),
                        dict(core_start_utc='2023-12-31T00:00:00+01:00'), dict(full_end_exclusive_utc='2023-01-01T00:00:00Z'),
                        dict(signal='bad'), dict(complete_full='yes'), dict(unmasked_potential_reference_all_slots='')]:
            with self.subTest(changes=changes):
                self.setup_inputs(events=[dict(event(), **changes)])
                self.out = self.root / ('out' + str(len(list(self.root.iterdir()))))
                self.assertEqual(self.run_stage(), 1)

    def test_rejects_submicrosecond_nonzero_fraction_before_datetime_truncation(self):
        self.setup_inputs(events=[event(end='2024-01-01T00:00:00.0000001Z')])
        self.assertEqual(self.run_stage(), 1)
        self.assertFalse((self.out / 'manifest.json').exists())

    def test_quality_failure(self):
        self.setup_inputs(quality_pass=False)
        self.assertEqual(self.run_stage(), 1)

    def test_hash_tamper_even_unconsumed_file(self):
        self.setup_inputs()
        (self.q / 'coverage_quarterly.csv').write_bytes(b'tampered')
        self.assertEqual(self.run_stage(), 1)

    def test_preserves_nonempty_output(self):
        self.setup_inputs()
        self.out.mkdir()
        (self.out / 'existing').write_bytes(b'keep')
        self.assertEqual(self.run_stage(), 1)
        self.assertEqual(list(self.out.iterdir()), [self.out / 'existing'])

    def test_malformed_csv(self):
        for data in (b'a,a\n1,2\n', csv_bytes([annual()]) + b'extra,fields\n', b'country_id,year,signal,expected_points,valid_points,candidate_80pct\n"unterminated'):
            self.setup_inputs()
            (self.q / 'coverage_annual.csv').write_bytes(data)
            m = json.loads((self.q / 'manifest.json').read_text())
            m['outputs'][0].update(digest(data))
            (self.q / 'manifest.json').write_text(json.dumps(m))
            self.out = self.root / ('out' + str(len(list(self.root.iterdir()))))
            self.assertEqual(self.run_stage(), 1)

    def test_reject_manifest_paths_duplicates_symlinks_and_missing_consumed(self):
        for mode in ('path', 'duplicate', 'symlink', 'missing'):
            self.setup_inputs()
            m = json.loads((self.q / 'manifest.json').read_text())
            if mode == 'path':
                m['outputs'][0]['file'] = '../escape'
            elif mode == 'duplicate':
                m['outputs'].append(m['outputs'][0])
            elif mode == 'missing':
                m['outputs'].pop(0)
            else:
                p = self.q / 'coverage_annual.csv'
                p.rename(self.q / 'real.csv')
                p.symlink_to('real.csv')
            (self.q / 'manifest.json').write_text(json.dumps(m))
            self.out = self.root / ('out' + str(len(list(self.root.iterdir()))))
            self.assertEqual(self.run_stage(), 1)
            if mode == 'symlink':
                (self.q / 'coverage_annual.csv').unlink()

    def test_source_mutation_before_publish(self):
        self.setup_inputs()
        original = self.mod.screen
        def mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            (self.q / 'summary.json').write_bytes(b'changed')
            return result
        with patch.object(self.mod, 'screen', side_effect=mutate):
            self.assertEqual(self.run_stage(), 1)
        self.assertFalse((self.out / 'manifest.json').exists())
        self.assertEqual(json.loads((self.out / 'status.json').read_text())['status'], 'failed')

    def test_reads_every_source_once(self):
        self.setup_inputs()
        counts = {}
        original = Path.read_bytes
        def counted(path):
            counts[path] = counts.get(path, 0) + 1
            return original(path)
        with patch.object(Path, 'read_bytes', counted):
            self.assertEqual(self.run_stage(), 0)
        self.assertTrue(counts)
        self.assertTrue(all(n == 1 for n in counts.values()))

    def test_source_mutation_during_read(self):
        self.setup_inputs()
        original = Path.read_bytes
        def changed(path):
            data = original(path)
            if path.name == 'coverage_annual.csv':
                path.write_bytes(data + b'\n')
            return data
        with patch.object(Path, 'read_bytes', changed):
            self.assertEqual(self.run_stage(), 1)
        self.assertFalse((self.out / 'manifest.json').exists())

    def test_upstream_states_and_row_count(self):
        for mode in ('quality', 'candidate', 'rows', 'duplicate_json'):
            self.setup_inputs()
            if mode == 'quality':
                p = self.q / 'manifest.json'
                m = json.loads(p.read_text())
                m['state'] = 'running'
                p.write_text(json.dumps(m))
            elif mode == 'candidate':
                (self.c / 'status.json').write_text('{"status":"failed"}')
            elif mode == 'rows':
                p = self.c / 'manifest.json'
                m = json.loads(p.read_text())
                m['outputs']['signal_window_audit.csv']['rows'] = 2
                p.write_text(json.dumps(m))
            else:
                (self.c / 'status.json').write_text('{"status":"failed","status":"completed"}')
            self.out = self.root / ('out' + str(len(list(self.root.iterdir()))))
            self.assertEqual(self.run_stage(), 1)

    def test_provisional_conditions_and_no_reference_year_gate(self):
        self.setup_inputs(annuals=[annual()], events=[event(start='2023-01-01T00:00:00Z', end='2023-01-02T00:00:00Z')])
        self.out.mkdir()
        self.assertEqual(self.run_stage(), 0)
        self.assertEqual(self.rows()[0]['provisional_full_refs_and_annual'], 'True')
        for changes in (dict(complete_full=False), dict(unmasked_potential_reference_all_slots=False)):
            self.setup_inputs(events=[dict(event(), **changes)])
            self.out = self.root / ('out' + str(len(list(self.root.iterdir()))))
            self.assertEqual(self.run_stage(), 0)
            self.assertEqual(self.rows()[0]['provisional_full_refs_and_annual'], 'False')

    def test_annual_join_uses_ioda_iso2_preserving_boundary_country(self):
        self.setup_inputs(annuals=[dict(annual(y), country_id='AD') for y in (2023, 2024)],
                          events=[dict(event(), country_id='AND', ioda_iso2='AD')])
        self.assertEqual(self.run_stage(), 0)
        row = self.rows()[0]
        self.assertEqual(row['country_id'], 'AND')
        self.assertEqual(row['ioda_iso2'], 'AD')
        self.assertEqual(row['annual_all_window_years_pass'], 'True')


if __name__ == '__main__':
    unittest.main()
