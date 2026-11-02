"""Build a descriptive UTC-day pilot without imputing inputs or estimating effects."""
import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import json
import math
from pathlib import Path
import re


METRICS = {
    ('t2m', 'daily_minimum'): ('tmin_degC', 'degC'),
    ('t2m', 'daily_maximum'): ('tmax_degC', 'degC'),
    ('t2m', 'daily_mean'): ('tmean_degC', 'degC'),
    ('d2m', 'daily_mean'): ('dewpoint_degC', 'degC'),
    ('u10', 'daily_mean'): ('u10_m_s', 'm s**-1'),
    ('v10', 'daily_mean'): ('v10_m_s', 'm s**-1'),
    ('tp', 'daily_total_previous_UTC_day'): ('precip_m', 'm'),
}
WB = {
    'IT.NET.USER.ZS': 'internet_use_percent',
    'EG.ELC.ACCS.ZS': 'electricity_access_percent',
    'SP.URB.TOTL.IN.ZS': 'urban_population_percent',
    'NY.GDP.PCAP.PP.KD': 'gdp_per_capita_ppp_constant',
    'SP.POP.TOTL': 'population_worldbank',
}
SIGNALS = {'ping-slash24': 'ap', 'bgp': 'bgp', 'merit-nt': 'telescope'}
SIGNAL_FIELDS = ['mean_raw', 'valid_n', 'expected_slots', 'valid_fraction',
                 'zero_fraction_valid', 'native_step_seconds']


def number(value):
    if value is None or str(value).strip() == '':
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_rows(path):
    opener = gzip.open if path.name.endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f)


def climate_files(root):
    pattern = re.compile(r'(tmin|tmax|weather|precip)_2024_\d{2}\.csv\.gz$')
    return sorted(p for folder in ['era5_land/country_day', 'weather_controls/country_day']
                  for p in (root / folder).glob('*.csv.gz') if pattern.fullmatch(p.name))


def load_climate(root):
    panel, used, nrows, per_file, outside_year = {}, set(), 0, [], 0
    boundary_iso = {}
    for path in climate_files(root):
        dates, count, outside_file = set(), 0, 0
        for row in read_rows(path):
            day = dt.date.fromisoformat(row['date'])
            if row['day_definition'] != 'UTC' or row['weight_year'] != '2025':
                raise ValueError('Unexpected day definition/weight year: ' + str(path))
            dates.add(row['date'])
            count += 1
            if day.year != 2024:
                outside_file += 1
                continue
            boundary, iso3 = row['boundary_code'], row['iso3']
            if not boundary or (iso3 and not re.fullmatch('[A-Z]{3}', iso3)):
                raise ValueError('Invalid boundary or ISO code')
            if boundary in boundary_iso and boundary_iso[boundary] != iso3:
                raise ValueError('Inconsistent ISO label for boundary ' + boundary)
            boundary_iso[boundary] = iso3
            definition = METRICS.get((row['variable'], row['statistic']))
            if definition is None:
                raise ValueError('Unknown climate variable/statistic: ' + repr(row))
            metric, unit = definition
            if row['unit'] != unit:
                raise ValueError('Unexpected unit for ' + metric)
            key = (boundary, row['date'])
            if key + (metric,) in used:
                raise ValueError('Duplicate country-day metric: ' + repr(key + (metric,)))
            used.add(key + (metric,))
            value, fraction = number(row['value']), number(row['valid_population_fraction'])
            if fraction is not None and not -1e-8 <= fraction <= 1 + 1e-8:
                raise ValueError('Population coverage outside [0,1]')
            entry = panel.setdefault(key, {'boundary_code': boundary, 'iso3': iso3,
                                           'date_utc': row['date'], 'weight_year': 2025,
                                           'day_definition': 'UTC'})
            assigned = number(row['population_assigned'])
            if 'population_assigned' in entry and assigned != entry['population_assigned']:
                raise ValueError('Inconsistent assigned population')
            entry['population_assigned'] = assigned
            entry[metric] = value
            entry[metric + '_population_fraction'] = fraction
        nrows += count
        outside_year += outside_file
        per_file.append({'path': str(path.relative_to(root)), 'sha256': sha(path), 'rows': count,
                         'date_min': min(dates) if dates else None,
                         'date_max': max(dates) if dates else None, 'unique_dates': len(dates),
                         'rows_outside_2024': outside_file})
    if not per_file:
        raise ValueError('No final monthly climate files found')
    for row in panel.values():
        lo, hi = row.get('tmin_degC'), row.get('tmax_degC')
        if lo is not None and hi is not None and lo > hi + 1e-6:
            raise ValueError('Tmin exceeds Tmax: ' + repr(row))
    return panel, {'source_rows': nrows, 'rows_outside_2024': outside_year, 'files': per_file}


def load_join(root):
    path = root / 'metadata/ioda_worldbank_climate_join_audit.csv'
    by_boundary, countries = {}, set()
    for row in read_rows(path):
        code = row['ioda_iso2']
        if code in countries:
            raise ValueError('Duplicate IODA country in crosswalk')
        countries.add(code)
        if row['boundary_code']:
            boundary = row['boundary_code']
            if boundary in by_boundary:
                raise ValueError('Duplicate boundary in crosswalk')
            if row['join_status'] != 'exact_three_source_join' or not row['worldbank_iso3']:
                raise ValueError('Nonexact mapping for boundary')
            by_boundary[boundary] = row
    return by_boundary, path


def load_wb(root):
    path = root / 'worldbank/country_year_indicators_2018_2025.csv'
    data, keys = {}, set()
    for row in read_rows(path):
        key = (row['iso3'], row['year'])
        if key in keys:
            raise ValueError('Duplicate World Bank country-year')
        keys.add(key)
        if row['year'] == '2024':
            data[row['iso3']] = {label: number(row[indicator]) for indicator, label in WB.items()}
    return data, path


def load_ioda(path, wanted_dates, wanted_codes):
    data = {}
    for row in read_rows(path):
        if row['date_utc'] not in wanted_dates or row['country_code'] not in wanted_codes:
            continue
        if row['signal'] not in SIGNALS:
            continue
        key = (row['country_code'], row['date_utc'], row['signal'])
        if key in data:
            raise ValueError('Duplicate IODA country-signal-day')
        converted = {field: number(row[field]) for field in SIGNAL_FIELDS}
        coverage = converted['valid_fraction']
        if coverage is not None and not 0 <= coverage <= 1:
            raise ValueError('IODA valid fraction outside [0,1]')
        data[key] = converted
    return data


def build(data_root, output_dir, ioda_path=None):
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError('Output directory is not empty; use a new directory')
    panel, audit = load_climate(data_root)
    crosswalk, crosswalk_path = load_join(data_root)
    wb, wb_path = load_wb(data_root)
    rows = [r for r in panel.values() if 'tmin_degC' in r or 'tmax_degC' in r]
    rows.sort(key=lambda r: (r['boundary_code'], r['date_utc']))
    wanted_dates = {r['date_utc'] for r in rows}
    wanted_codes = {r['ioda_iso2'] for r in crosswalk.values()}
    ioda = load_ioda(ioda_path, wanted_dates, wanted_codes) if ioda_path else {}
    unmatched = {}
    for row in rows:
        mapping = crosswalk.get(row['boundary_code'])
        if mapping and row['iso3'] != mapping['worldbank_iso3']:
            raise ValueError('Climate/crosswalk ISO mismatch')
        row['ioda_iso2'] = mapping['ioda_iso2'] if mapping else ''
        row['join_status'] = 'exact_three_source_join' if mapping else 'no_exact_ioda_climate_join'
        row['country_name'] = mapping['boundary_name'] if mapping else ''
        if not mapping:
            unmatched[row['boundary_code']] = row['iso3']
        values = wb.get(row['iso3'], {})
        for label in WB.values():
            row[label] = values.get(label)
        row['worldbank_year'] = 2024 if row['iso3'] in wb else None
        row['worldbank_imputed'] = 0
        row['temperature_complete'] = int(all(row.get(x) is not None for x in ['tmin_degC', 'tmax_degC']))
        row['controls_complete'] = int(all(row.get(x) is not None for x in
                                         ['tmean_degC', 'dewpoint_degC', 'u10_m_s', 'v10_m_s', 'precip_m']))
        for signal, prefix in SIGNALS.items():
            signal_values = ioda.get((row['ioda_iso2'], row['date_utc'], signal), {})
            for field in SIGNAL_FIELDS:
                row[prefix + '_' + field] = signal_values.get(field)
        row['exclusions_applied'] = 0
        row['inferential_ready'] = 0
    fields = ['boundary_code', 'iso3', 'ioda_iso2', 'country_name', 'join_status', 'date_utc',
              'weight_year', 'day_definition', 'population_assigned']
    for metric, _ in METRICS.values():
        fields += [metric, metric + '_population_fraction']
    fields += list(WB.values()) + ['worldbank_year', 'worldbank_imputed', 'temperature_complete',
                                  'controls_complete']
    fields += [prefix + '_' + field for prefix in SIGNALS.values() for field in SIGNAL_FIELDS]
    fields += ['exclusions_applied', 'inferential_ready']
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / 'country_day_pilot_2024.csv.gz'
    with gzip.open(output, 'wt', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        writer.writerows(rows)
    monthly = []
    for month in sorted({r['date_utc'][:7] for r in rows}):
        group = [r for r in rows if r['date_utc'].startswith(month)]
        matched = [r for r in group if r['ioda_iso2']]
        monthly.append({'month': month, 'rows_all_boundaries': len(group),
                        'unique_dates': len({r['date_utc'] for r in group}),
                        'rows_exact_join': len(matched),
                        'complete_temperature_rows_exact_join': sum(r['temperature_complete'] for r in matched),
                        'complete_controls_rows_exact_join': sum(r['controls_complete'] for r in matched),
                        'ap_daily_coverage_at_least_80pct_rows_exact_join':
                            sum((r['ap_valid_fraction'] or 0) >= .8 for r in matched) if ioda_path else None})
    sources = {str(p.relative_to(data_root)): sha(p) for p in [crosswalk_path, wb_path]}
    if ioda_path:
        sources[str(ioda_path)] = sha(ioda_path)
    report = {'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'status': 'descriptive_pilot_not_inferential', 'data_root': str(data_root),
              'script_sha256': sha(Path(__file__)), 'rows': len(rows),
              'boundaries': len({r['boundary_code'] for r in rows}),
              'exact_join_countries': len({r['ioda_iso2'] for r in rows if r['ioda_iso2']}),
              'date_count': len(wanted_dates), 'date_min': min(wanted_dates), 'date_max': max(wanted_dates),
              'unmatched_boundaries_retained': unmatched, 'monthly': monthly,
              'missing_by_column': {k: sum(r.get(k) is None for r in rows) for k in fields if
                                    k.endswith(('degC', 'm_s', 'precip_m', 'mean_raw', 'valid_fraction')) or k in WB.values()},
              'climate_input_audit': audit, 'other_source_sha256': sources,
              'ioda_daily_joined': ioda_path is not None, 'output_sha256': sha(output),
              'limitations': [
                  'UTC daily climate is not local-night or hourly heat exposure.',
                  'No 1991-2020 threshold climatology; NTRD, DHD and heat events not calculated.',
                  'IODA daily raw means support QA only; DHRD/recovery need native signals and event-specific baselines.',
                  'Intentional shutdown, cyclone and global measurement anomaly masks have not been applied.',
                  'World Bank values are from 2024 only; missing values stay missing.',
                  'Daily 80% IODA flag is descriptive and does not establish annual/event observability.',
                  'Only final monthly climate files used; preliminary labels and segment files excluded.',
                  'Precipitation uses the corrected date column without an additional one-day shift.',
                  'Population weights are fixed to 2025; each variable retains its valid population fraction.'
              ]}
    (output_dir / 'pilot_summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    dictionary = {'key': ['boundary_code', 'date_utc'], 'missing_numeric': 'empty CSV cell',
                  'scope': '2024 months with available final Tmin/Tmax aggregates, including unmatched boundaries',
                  'units': {metric: unit for metric, unit in METRICS.values()},
                  'population_fraction': 'Fraction of assigned 2025 population with valid climate; not national population share.',
                  'ioda_prefixes': SIGNALS, 'ioda_means': 'Original signal units; never add across signals.',
                  'worldbank_columns': WB, 'inferential_ready': 'Always 0 in this pilot.',
                  'temperature_complete': 'Both temperature values are finite; no population coverage threshold applied.',
                  'controls_complete': 'All five control values are finite; no population coverage threshold applied.',
                  'exclusions_applied': '0 means pending, not no shutdown or cyclone.'}
    (output_dir / 'data_dictionary.json').write_text(json.dumps(dictionary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['status', 'rows', 'boundaries', 'exact_join_countries',
                                            'date_count', 'monthly', 'ioda_daily_joined']}, indent=2))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--ioda-daily', type=Path)
    args = p.parse_args()
    build(args.data_root.resolve(), args.output_dir.resolve(), args.ioda_daily)
