import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/prepare_analysis_preflight.py'


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'preflight implementation is missing')
        spec = importlib.util.spec_from_file_location('preflight', SCRIPT)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / 'out'
        self.cross = [dict(ioda_iso2='AA', ioda_name='Alpha', worldbank_iso3='AAA', worldbank_name='Alpha', mapping_status='exact_iso2_match'), dict(ioda_iso2='ZZ', ioda_name='Unknown', worldbank_iso3='', worldbank_name='', mapping_status='unmatched')]
        self.countries = [dict(country_id='AAA', total_population='100', country_name='Alpha'), dict(country_id='BBB', total_population='0', country_name='Beta')]
        self.events = [dict(event_id='e1', country_id='AAA', start_date='2022-01-01', end_exclusive_utc='2022-01-02T00:00:00Z', weather_candidate='1', network_screened='0')]
        self.stop = [self.stop_row()]

    def stop_row(self, **changes):
        row = dict(source_row='2', normalized_start_date='2022-01-04', normalized_end_date='2022-01-04', date_interval_status='complete', bounded_interval_eligible='1', normalized_geo_scope='local', matched_worldbank_iso3='AAA', country_match_status='exact_name_match', qa_flags='', shutdown_extent='Service-based', area_name='Town')
        row.update(changes)
        return row

    def run_job(self):
        args = []
        for name, rows in [('crosswalk', self.cross), ('countries', self.countries), ('events', self.events), ('stop', self.stop)]:
            path = self.root / (name + '.csv')
            with path.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            args.extend(['--' + name, str(path)])
        return self.m.main(args + ['--output-dir', str(self.out)])

    def rows(self, name):
        with (self.out / name).open(newline='') as handle:
            return list(csv.DictReader(handle))

    def test_exact_and_unmatched_preserved_with_boundary_coverage(self):
        self.assertEqual(self.run_job(), 0)
        rows = self.rows('joint_crosswalk.csv')
        self.assertEqual([r['joint_status'] for r in rows], ['exact_joint_match', 'source_not_exact'])
        self.assertEqual(self.rows('boundary_coverage.csv')[1]['coverage_status'], 'nonpositive_or_invalid_population')
        self.assertFalse(json.loads((self.out / 'summary.json').read_text())['downstream_ready_for_baseline'])

    def test_many_to_one_both_unmapped(self):
        self.cross.append(dict(self.cross[0], ioda_iso2='AB'))
        self.assertEqual(self.run_job(), 0)
        mapped = [r for r in self.rows('joint_crosswalk.csv') if r['ioda_iso2'] in ('AA', 'AB')]
        self.assertTrue(all(r['joint_status'] == 'ambiguous_many_to_one' and not r['joint_country_id'] for r in mapped))

    def test_duplicate_source_boundary_and_event_identifiers_rejected(self):
        for kind in ('cross', 'countries', 'events', 'stop'):
            with self.subTest(kind=kind):
                rows = getattr(self, kind)
                rows.append(dict(rows[0]))
                self.out = self.root / kind
                self.assertNotEqual(self.run_job(), 0)
                self.assertEqual(json.loads((self.out / 'status.json').read_text())['status'], 'failed')
                rows.pop()

    def test_unknown_event_country_rejected(self):
        self.events[0]['country_id'] = 'QQQ'
        self.assertNotEqual(self.run_job(), 0)

    def test_utc_right_open_boundary_and_review_only_scope(self):
        self.stop.append(self.stop_row(source_row='3', normalized_start_date='2022-01-05', normalized_end_date='2022-01-05'))
        self.assertEqual(self.run_job(), 0)
        reviews = self.rows('stop_event_review.csv')
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]['source_row'], '2')
        self.assertEqual(reviews[0]['review_only'], '1')
        self.assertEqual(reviews[0]['normalized_geo_scope'], 'local')
        self.assertEqual(reviews[0]['shutdown_extent'], 'Service-based')
        self.assertEqual(reviews[0]['source_timezone'], 'unknown')
        self.assertEqual(reviews[0]['stop_end_exclusive_utc'], '2022-01-05T00:00:00Z')

    def test_missing_end_known_day_and_later_uncertainty(self):
        self.stop = [self.stop_row(normalized_start_date='2021-01-01', normalized_end_date='', date_interval_status='incomplete', bounded_interval_eligible='0')]
        self.assertEqual(self.run_job(), 0)
        review = self.rows('stop_event_review.csv')[0]
        self.assertEqual(review['review_reason'], 'open_ended_uncertainty')
        self.assertEqual(review['stop_end_exclusive_utc'], '2021-01-02T00:00:00Z')
        self.assertEqual(len(self.rows('stop_unresolved.csv')), 1)

    def test_missing_end_start_day_only(self):
        self.stop = [self.stop_row(normalized_start_date='2022-01-01', normalized_end_date='', date_interval_status='incomplete', bounded_interval_eligible='0')]
        self.assertEqual(self.run_job(), 0)
        self.assertEqual(self.rows('stop_event_review.csv')[0]['review_reason'], 'known_start_day_overlap')

    def test_invalid_reversed_unknown_start_and_unmatched_retained(self):
        self.stop = [self.stop_row(source_row='2', normalized_start_date='bad'), self.stop_row(source_row='3', normalized_end_date='2021-01-01'), self.stop_row(source_row='4', normalized_start_date='', normalized_end_date='', date_interval_status='incomplete', bounded_interval_eligible='0'), self.stop_row(source_row='5', country_match_status='unmatched_exact_name', matched_worldbank_iso3='')]
        self.assertEqual(self.run_job(), 0)
        self.assertEqual(len(self.rows('stop_unresolved.csv')), 4)
        reviews = self.rows('stop_event_review.csv')
        self.assertTrue(any(r['source_row'] == '4' and r['review_reason'] == 'unknown_start_uncertainty' for r in reviews))
        self.assertFalse(any(r['source_row'] == '5' for r in reviews))

    def test_hash_manifest_and_fresh_directory(self):
        self.assertEqual(self.run_job(), 0)
        manifest = json.loads((self.out / 'manifest.json').read_text())
        for name, meta in manifest['outputs'].items():
            self.assertEqual(meta['sha256'], hashlib.sha256((self.out / name).read_bytes()).hexdigest())
        self.assertEqual(len(manifest['sources']), 4)
        self.assertEqual(manifest.get('script_sha256'), hashlib.sha256(SCRIPT.read_bytes()).hexdigest())
        self.assertEqual(manifest['schema_version'], 1)
        status = json.loads((self.out / 'status.json').read_text())
        self.assertGreater(status['pid'], 0)
        self.assertIn('updated_utc', status)
        before = (self.out / 'status.json').read_bytes()
        self.assertNotEqual(self.run_job(), 0)
        self.assertEqual((self.out / 'status.json').read_bytes(), before)

    def test_overlap_rejected_without_touching_inputs(self):
        self.out = self.root
        self.assertNotEqual(self.run_job(), 0)
        self.assertTrue((self.root / 'crosswalk.csv').exists())

    def test_lock_is_exclusive(self):
        lock = self.root / '.out.lock'
        lock.write_text('other process')
        self.assertNotEqual(self.run_job(), 0)
        self.assertEqual(lock.read_text(), 'other process')
        self.assertFalse(self.out.exists())

    def test_nonpositive_country_cannot_join(self):
        self.cross.append(dict(self.cross[0], ioda_iso2='BB', worldbank_iso3='BBB'))
        self.assertEqual(self.run_job(), 0)
        row = self.rows('joint_crosswalk.csv')[-1]
        self.assertEqual(row['joint_status'], 'nonpositive_or_invalid_population')
        self.assertEqual(row['joint_country_id'], '')

    def test_normalization_invalid_end_is_not_open_ended(self):
        self.stop = [self.stop_row(normalized_end_date='', qa_flags='end_date_invalid', date_interval_status='incomplete', bounded_interval_eligible='0')]
        self.assertEqual(self.run_job(), 0)
        review = self.rows('stop_event_review.csv')[0]
        self.assertEqual(review['review_reason'], 'invalid_interval_uncertainty')
        self.assertEqual(review['stop_end_exclusive_utc'], '')

    def test_generated_field_collision_rejected(self):
        for row in self.cross:
            row['joint_status'] = 'untrusted source value'
        self.assertNotEqual(self.run_job(), 0)

    def test_noncalendar_iso_week_event_date_rejected(self):
        self.events[0]['start_date'] = '2021-W52-6'
        self.assertNotEqual(self.run_job(), 0)

    def test_unclosed_quote_must_not_swallow_next_csv_record(self):
        path = self.root / 'malformed.csv'
        path.write_text('country_id,total_population,country_name\nAAA,100,"Alpha\nBBB,200,Beta\n')
        with self.assertRaises(csv.Error):
            self.m.read_source(path, self.m.SCHEMAS['countries'])

    def test_missing_start_known_end_right_open_boundary(self):
        self.stop = [self.stop_row(normalized_start_date='', normalized_end_date='2021-12-31', date_interval_status='incomplete', bounded_interval_eligible='0')]
        self.events.append(dict(self.events[0], event_id='before', start_date='2021-12-31', end_exclusive_utc='2022-01-01T00:00:00Z'))
        self.events.append(dict(self.events[0], event_id='after', start_date='2022-01-02', end_exclusive_utc='2022-01-03T00:00:00Z'))
        self.assertEqual(self.run_job(), 0)
        self.assertEqual([(r['event_id'], r['review_reason']) for r in self.rows('stop_event_review.csv')], [('before', 'unknown_start_uncertainty')])
        self.assertEqual(len(self.rows('stop_unresolved.csv')), 1)

    def test_invalid_start_does_not_claim_known_end_resolves_uncertainty(self):
        self.stop = [self.stop_row(normalized_start_date='invalid', normalized_end_date='2021-12-31'), self.stop_row(source_row='3', normalized_start_date='', normalized_end_date='2021-12-31', qa_flags='start_date_invalid')]
        self.assertEqual(self.run_job(), 0)
        self.assertEqual([r['review_reason'] for r in self.rows('stop_event_review.csv')], ['invalid_interval_uncertainty', 'invalid_interval_uncertainty'])


if __name__ == '__main__':
    unittest.main()
