"""Frozen heat-event definitions: synthetic calendar and catalogue regression checks."""
import hashlib
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/build_heat_event_catalogue.py'


def module():
    assert SCRIPT.exists(), 'Heat catalogue implementation is not present'
    spec = importlib.util.spec_from_file_location('heat_catalogue', SCRIPT)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def daily(values, start='2022-06-01'):
    n = len(values)
    return pd.DataFrame(dict(country_id=['CHN'] * n, date=pd.date_range(start, periods=n),
                             tmax_c=values, tmin_c=np.zeros(n), dewpoint_c=np.zeros(n),
                             q90_tmax_c=np.ones(n), q90_tmin_c=np.ones(n)))


class DefinitionTests(unittest.TestCase):
    def setUp(self):
        self.m = module()

    def test_calendar_and_leap_threshold(self):
        self.assertEqual(self.m.calendar_day(pd.Timestamp('2020-03-01')), 59)
        self.assertEqual(self.m.calendar_day(pd.Timestamp('2019-03-01')), 59)
        self.assertIsNone(self.m.calendar_day(pd.Timestamp('2020-02-29')))
        q = pd.DataFrame({'calendar_day': np.arange(365), 'q90_tmax_c': np.arange(365),
                          'q90_tmin_c': np.arange(365)})
        attached = self.m.attach_thresholds(daily([2], '2024-02-29').drop(columns=['q90_tmax_c', 'q90_tmin_c']), q)
        self.assertEqual(attached.q90_tmax_c.iloc[0], 58.5)

    def test_circular_threshold_and_reference_gate(self):
        d = daily(np.ones(1461), '2018-01-01')
        d.loc[d.date.dt.month == 12, 'tmax_c'] = 10
        q = self.m.build_thresholds(d)
        self.assertEqual(q.iloc[0].q90_tmax_c, 10)
        self.assertEqual(q.iloc[0].tmax_reference_n, 124)
        d.loc[(d.date.dt.year == 2018) & ((d.date.dt.month == 12) | (d.date.dt.month == 1)), 'tmax_c'] = np.nan
        self.assertTrue(np.isnan(self.m.build_thresholds(d).iloc[0].q90_tmax_c))

    def test_ninety_percent_gate_exactly_112_valid_samples(self):
        d = daily(np.ones(1461), '2018-01-01')
        affected = d.index[(d.date.dt.year == 2018) & (d.date.dt.month == 1) & (d.date.dt.day <= 12)]
        d.loc[affected, 'tmax_c'] = np.nan
        self.assertEqual(self.m.build_thresholds(d).iloc[0].q90_tmax_c, 1)
        d.loc[(d.date.dt.year == 2018) & (d.date.dt.month == 1) & (d.date.dt.day == 13), 'tmax_c'] = np.nan
        self.assertTrue(np.isnan(self.m.build_thresholds(d).iloc[0].q90_tmax_c))

    def test_warm_season_tie_and_wrap(self):
        d = daily(np.ones(1461), '2018-01-01')
        self.assertEqual(self.m.warm_season(d)['warm_season_start_month'], 1)
        d.loc[d.date.dt.month.isin([12, 1, 2]), 'tmax_c'] = 10
        self.assertEqual(self.m.warm_season(d)['warm_season_start_month'], 12)
        self.assertEqual(self.m.warm_season(d)['loyo_agreement_fraction'], 1)

    def test_two_day_strict_run_and_one_day_bridge(self):
        raw, process, analysis, flags = self.m.catalogue_country(daily([1, 2, 2, 0, 2, 2, 1]), 6)
        self.assertEqual(len(raw), 2)
        self.assertEqual(len(process), 1)
        self.assertEqual(analysis.iloc[0].hot_days, 4)
        self.assertEqual(analysis.iloc[0].bridge_days, 1)
        self.assertEqual(analysis.iloc[0].hd_c_days, 4)

    def test_six_and_seven_nonhot_gaps(self):
        for gap, expected in [(1, 1), (6, 1), (7, 2)]:
            result = self.m.catalogue_country(daily([2, 2] + [0] * gap + [2, 2]), 6)
            self.assertEqual(len(result[2]), expected)

    def test_singleton_resets_gap_and_contributes_dose(self):
        a = self.m.catalogue_country(daily([2, 2] + [0] * 4 + [3] + [0] * 4 + [2, 2]), 6)[2]
        self.assertEqual(len(a), 1)
        self.assertEqual(a.iloc[0].hot_days, 5)
        self.assertEqual(a.iloc[0].hd_c_days, 6)

    def test_missing_is_barrier_and_tmin_cannot_move_boundaries(self):
        d = daily([2, 2, np.nan, 2, 2])
        a = self.m.catalogue_country(d, 6)[2]
        self.assertEqual(len(a), 2)
        d.tmin_c = 100
        b = self.m.catalogue_country(d, 6)[2]
        self.assertEqual(a.start_date.tolist(), b.start_date.tolist())
        self.assertEqual(a.end_date.tolist(), b.end_date.tolist())
        d.loc[0, 'tmin_c'] = np.nan
        self.assertTrue(np.isnan(self.m.catalogue_country(d, 6)[2].iloc[0].ntrd_c_days))

    def test_cross_year_and_complete_window(self):
        a = self.m.catalogue_country(daily([0, 2, 2, 2, 0], '2021-12-30'), 12)[2]
        self.assertEqual(a.iloc[0].start_date, '2021-12-31')
        self.assertEqual(a.iloc[0].end_exclusive_utc, '2022-01-03T00:00:00Z')
        self.assertTrue(a.iloc[0].left_analysis_boundary)
        self.assertFalse(a.iloc[0].complete_analysis_window)

    def test_isolation_checks_other_recovery_and_full_calendar_window(self):
        d = daily([0] * 10 + [2, 2] + [0] * 7 + [2, 2] + [0] * 10)
        a = self.m.catalogue_country(d, 6)[2]
        self.assertTrue(a.complete_analysis_window.all())
        self.assertTrue(a.complete_weather_window.all())
        self.assertFalse(a.isolated_weather_event.iloc[1])
        self.assertFalse(a.weather_candidate.iloc[1])
        self.assertFalse(a.network_screened.any())

    def test_output_must_not_overlap_input_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for output in [root, root / 'catalogue']:
                with self.assertRaisesRegex(ValueError, 'overlap|inside'):
                    self.m.main(['--country-daily', str(root), '--output-dir', str(output)])
            self.assertFalse((root / 'progress.json').exists())

    def test_inputs_require_complete_months_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, '96|missing'):
                self.m.load_inputs(root)
            for month in pd.period_range('2018-01', '2025-12', freq='M'):
                path = root / f'era5_country_daily_{month.strftime("%Y%m")}.csv'
                d = daily(np.zeros(month.days_in_month), str(month.start_time.date()))
                d['total_population'] = 100
                d.to_csv(path, index=False)
                path.with_suffix('.audit.json').write_text(json.dumps({'output_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))
            data, sources, exclusions = self.m.load_inputs(root)
            self.assertEqual(len(data), 2922)
            self.assertEqual(len(sources), 96)
            out = root.parent / (root.name + '_catalogue')
            self.addCleanup(__import__('shutil').rmtree, out, True)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.m.main(['--country-daily', str(root), '--output-dir', str(out)]), 0)
            manifest = json.loads((out / 'manifest.json').read_text())
            self.assertEqual(manifest['state'], 'complete')
            for name in ['progress.json', 'summary.json', 'manifest.json']:
                status = json.loads((out / name).read_text())
                self.assertGreater(status['pid'], 0)
                self.assertTrue(status['updated_utc'].endswith('Z'))
            self.assertFalse((out / '.catalogue.lock').exists())
            for name, info in manifest['outputs'].items():
                self.assertEqual(hashlib.sha256((out / name).read_bytes()).hexdigest(), info['sha256'])
            self.assertEqual(len(pd.read_csv(out / 'analysis_events.csv')), 0)
            (out / '.catalogue.lock').write_text('existing')
            with self.assertRaisesRegex(RuntimeError, 'lock'):
                self.m.main(['--country-daily', str(root), '--output-dir', str(out)])
            self.assertEqual((out / '.catalogue.lock').read_text(), 'existing')
            (out / '.catalogue.lock').unlink()
            path.write_text('corrupted')
            with self.assertRaisesRegex(ValueError, 'hash'):
                self.m.load_inputs(root)
            with self.assertRaisesRegex(ValueError, 'hash'):
                self.m.main(['--country-daily', str(root), '--output-dir', str(out)])
            self.assertEqual(json.loads((out / 'progress.json').read_text())['state'], 'failed')
            self.assertEqual(json.loads((out / 'manifest.json').read_text())['state'], 'failed')
            for name in ['summary.json', 'progress.json', 'manifest.json']:
                status = json.loads((out / name).read_text())
                self.assertEqual(status['state'], 'failed')
                self.assertGreater(status['pid'], 0)
                self.assertTrue(status['updated_utc'].endswith('Z'))


if __name__ == '__main__':
    unittest.main()
