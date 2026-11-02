import csv
import gzip
import importlib.util
import contextlib
import io
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/build_climate_pilot.py'


def module():
    spec = importlib.util.spec_from_file_location('climate_pilot', SCRIPT)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


FIELDS = ['boundary_code', 'iso3', 'date', 'variable', 'statistic', 'value', 'unit',
          'population_with_valid_climate', 'population_assigned', 'valid_population_fraction',
          'weight_year', 'day_definition']


def row(date='2024-02-29', value='0', statistic='daily_minimum', variable='t2m', unit='degC'):
    return dict(zip(FIELDS, ['AAA', 'AAA', date, variable, statistic, value, unit,
                            '100', '100', '1', '2025', 'UTC']))


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, 'wt', newline='') as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)


class ClimatePilotTests(unittest.TestCase):
    def test_missing_is_not_zero(self):
        m = module()
        self.assertIsNone(m.number('nan'))
        self.assertIsNone(m.number(''))
        self.assertIsNone(m.number('inf'))
        self.assertEqual(m.number('0'), 0.0)

    def test_final_file_selection_excludes_segment_and_preliminary(self):
        m = module()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            folder = root / 'era5_land/country_day'
            for name in ['tmin_2024_02.csv.gz', 'tmin_2024_02.csv.segment0.csv.gz',
                         'tmin_2024_07_preliminary_boundary_labels.csv.gz']:
                write_csv(folder / name, [row()])
            files = m.climate_files(root)
            self.assertEqual([p.name for p in files], ['tmin_2024_02.csv.gz'])

    def test_leap_day_zero_and_corrected_precip_date_are_preserved(self):
        m = module()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_csv(root / 'era5_land/country_day/tmin_2024_02.csv.gz', [row()])
            write_csv(root / 'weather_controls/country_day/precip_2024_07.csv.gz',
                      [row('2024-06-30', '0.002', 'daily_total_previous_UTC_day', 'tp', 'm')])
            panel, audit = m.load_climate(root)
            self.assertEqual(panel['AAA', '2024-02-29']['tmin_degC'], 0)
            self.assertEqual(panel['AAA', '2024-06-30']['precip_m'], .002)
            self.assertNotIn(('AAA', '2024-07-01'), panel)
            self.assertEqual(audit['source_rows'], 2)

    def test_duplicate_country_day_metric_rejected(self):
        m = module()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_csv(root / 'era5_land/country_day/tmin_2024_02.csv.gz', [row(), row()])
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                m.load_climate(root)

    def test_wrong_units_rejected(self):
        m = module()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_csv(root / 'era5_land/country_day/tmin_2024_02.csv.gz', [row(unit='K')])
            with self.assertRaisesRegex(ValueError, 'unit'):
                m.load_climate(root)

    def test_inconsistent_iso_rejected(self):
        m = module()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a, b = row(), row(value='20', statistic='daily_maximum')
            b['iso3'] = 'BBB'
            write_csv(root / 'era5_land/country_day/tmin_2024_02.csv.gz', [a, b])
            with self.assertRaisesRegex(ValueError, 'ISO'):
                m.load_climate(root)

    def test_previous_year_precip_boundary_is_counted_and_skipped(self):
        m = module()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_csv(root / 'weather_controls/country_day/precip_2024_01.csv.gz',
                      [row('2023-12-31', '0.002', 'daily_total_previous_UTC_day', 'tp', 'm'),
                       row('2024-01-01', '0', 'daily_total_previous_UTC_day', 'tp', 'm')])
            panel, audit = m.load_climate(root)
            self.assertEqual(list(panel), [('AAA', '2024-01-01')])
            self.assertEqual(audit['rows_outside_2024'], 1)
            self.assertEqual(audit['source_rows'], 2)

    def test_exact_join_missing_wb_and_zero_signal_survive_full_build(self):
        m = module()
        with tempfile.TemporaryDirectory() as d:
            root, out = Path(d) / 'data', Path(d) / 'output'
            a, b = row(), row(value='10', statistic='daily_maximum')
            write_csv(root / 'era5_land/country_day/tmin_2024_02.csv.gz', [a, b])
            (root / 'metadata').mkdir()
            (root / 'metadata/ioda_worldbank_climate_join_audit.csv').write_text(
                'ioda_iso2,worldbank_iso3,boundary_code,boundary_name,join_status\n'
                'AA,AAA,AAA,Country A,exact_three_source_join\n')
            (root / 'worldbank').mkdir()
            with (root / 'worldbank/country_year_indicators_2018_2025.csv').open('w', newline='') as f:
                w = csv.DictWriter(f, ['iso3', 'year'] + list(m.WB))
                w.writeheader()
                w.writerow({'iso3': 'AAA', 'year': '2024', 'IT.NET.USER.ZS': 0})
                w.writerow({'iso3': 'AAA', 'year': '2025', 'IT.NET.USER.ZS': 90})
            ip = Path(d) / 'ioda.csv'
            with ip.open('w', newline='') as f:
                fields = ['country_code', 'signal', 'date_utc'] + m.SIGNAL_FIELDS
                w = csv.DictWriter(f, fields)
                w.writeheader()
                w.writerow(dict(country_code='AA', signal='ping-slash24', date_utc='2024-02-29',
                                mean_raw=0, valid_n=144, expected_slots=144, valid_fraction=1,
                                zero_fraction_valid=1, native_step_seconds=600))
            with contextlib.redirect_stdout(io.StringIO()):
                result = m.build(root, out, ip)
            self.assertEqual(result['rows'], 1)
            with gzip.open(out / 'country_day_pilot_2024.csv.gz', 'rt') as f:
                record = next(csv.DictReader(f))
            self.assertEqual(float(record['ap_mean_raw']), 0)
            self.assertEqual(float(record['internet_use_percent']), 0)
            self.assertEqual(record['population_worldbank'], '')
            self.assertEqual(record['bgp_mean_raw'], '')
            self.assertEqual(record['inferential_ready'], '0')
            self.assertEqual(record['worldbank_year'], '2024')


if __name__ == '__main__':
    unittest.main()
