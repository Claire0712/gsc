import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/serve_heat_dashboard.py'


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'Dashboard backend not implemented')
        spec = importlib.util.spec_from_file_location('dashboard', SCRIPT)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.era = self.root / 'era'
        self.prep = self.root / 'prep'
        self.assets = self.root / 'assets'
        for p in (self.era / 'country_daily', self.era / 'weights', self.prep, self.assets):
            p.mkdir(parents=True)
        (self.era / 'weights/country_metadata.csv').write_text('country_id,country_name,total_population\nCHN,China,100\nATA,Antarctica,0\n')
        (self.assets / 'index.html').write_text('hello')
        self.app = self.m.Dashboard(self.era, self.prep, self.assets)

    def month(self, audited=True):
        path = self.era / 'country_daily/era5_country_daily_202401.csv'
        path.write_text('country_id,date,tmax_c,tmin_c,dewpoint_c\nCHN,2024-01-01,30,20,15\nCHN,2024-01-02,nan,0,\n')
        if audited:
            path.with_suffix('.audit.json').write_text(json.dumps({'output_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))
        return path

    def test_allowlist_blocks_arbitrary_paths(self):
        for path in ('/../status.json', '/%2e%2e/status.json', '/scripts/serve_heat_dashboard.py', '/api/unknown'):
            self.assertEqual(self.app.route(path)[0], 404)
        self.assertEqual(self.app.route('/')[0], 200)

    def test_validates_country_year_and_duplicate_query(self):
        for query in ('country=../../x&year=2024', 'country=CHN&year=2026', 'country=CHN&year=no', 'country=CHN&year=2024&year=2023'):
            self.assertEqual(self.app.route('/api/climate?' + query)[0], 400)

    def test_only_completed_months_and_no_fake_zero(self):
        self.month(False)
        self.assertEqual(self.app.climate('CHN', 2024)['rows'], [])
        self.month(True)
        result = self.app.climate('CHN', 2024)
        self.assertEqual(result['available_months'], ['202401'])
        self.assertFalse(result['complete_year'])
        self.assertEqual(result['rows'][0]['tmax_c'], 30)
        self.assertIsNone(result['rows'][1]['tmax_c'])
        self.assertEqual(result['rows'][1]['tmin_c'], 0)

    def test_changed_csv_rejected_by_audit_hash(self):
        p = self.month()
        p.write_text(p.read_text().replace(',30,', ',99,'))
        with self.assertRaises(ValueError):
            self.app.climate('CHN', 2024)
        self.assertEqual(self.app.status()['era5']['completed_months'], 0)
        self.assertEqual(self.app.status()['era5']['invalid_months'], ['202401'])

    def test_missing_jobs_and_events_remain_pending(self):
        status = self.app.status()
        self.assertEqual(status['ioda']['state'], 'pending')
        self.assertEqual(status['analysis']['state'], 'pending')
        code, mime, body = self.app.route('/api/events?country=CHN&year=2024')
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)['events'], [])

    def test_failed_progress_takes_precedence_over_old_summary(self):
        d = self.prep / 'ioda'
        d.mkdir()
        (d / 'summary.json').write_text('{"state":"completed","updated_utc":"2026-10-01T00:00:00+00:00"}')
        (d / 'progress.json').write_text('{"state":"failed","updated_utc":"2026-10-02T00:00:00+00:00"}')
        self.assertEqual(self.app.status()['ioda']['state'], 'failed')

    def test_dead_process_not_reported_running(self):
        d = self.prep / 'ioda'
        d.mkdir()
        (d / 'progress.json').write_text('{"state":"running","pid":999999999}')
        self.assertEqual(self.app.status()['ioda']['state'], 'interrupted')

    def test_completed_progress_keeps_summary_counts(self):
        d = self.prep / 'auxiliary'
        d.mkdir()
        (d / 'summary.json').write_text('{"state":"complete","updated_utc":"2026-10-02T00:00:00+00:00","stop":{"rows":2102}}')
        (d / 'progress.json').write_text('{"state":"complete","updated_utc":"2026-10-02T00:00:01+00:00"}')
        self.assertEqual(self.app.status()['auxiliary']['stop']['rows'], 2102)


if __name__ == '__main__':
    unittest.main()
