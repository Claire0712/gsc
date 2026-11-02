#!/usr/bin/env python3
"""Freeze 2018–2021 relative thresholds and 2022–2025 Tmax event catalogues.

No network data are read here. Weather candidates are never final network-eligible
events. Seven consecutive complete nonhot days separate analysis events; isolated
hot days reset that counter and contribute exposure within a merged event.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

import numpy as np
import pandas as pd

ANALYSIS_START = pd.Timestamp('2022-01-01')
ANALYSIS_STOP = pd.Timestamp('2026-01-01')
EVENT_COLUMNS = ['country_id', 'event_id', 'start_date', 'end_date', 'end_exclusive_utc',
                 'warm_season_start_month', 'in_warm_season', 'hot_days', 'longest_hot_run',
                 'bridge_days', 'span_days', 'hd_c_days', 'peak_excess_c', 'mean_hot_excess_c',
                 'absolute_tmax_c', 'ntrd_c_days', 'tmin_hot_fraction', 'dewpoint_mean_c',
                 'dewpoint_max_c', 'left_analysis_boundary', 'right_analysis_boundary',
                 'left_source_boundary', 'right_source_boundary', 'complete_analysis_window',
                 'complete_weather_window', 'isolated_weather_event', 'weather_candidate',
                 'network_screened']


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def atomic(path, value):
    """Replace a single output only after its complete contents have been written."""
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    os.close(fd)
    try:
        if isinstance(value, pd.DataFrame):
            value.to_csv(temporary, index=False, compression='gzip' if path.suffix == '.gz' else None)
        else:
            value = {**value, 'pid': os.getpid(),
                     'updated_utc': dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')}
            Path(temporary).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def calendar_day(date):
    """Zero-based day on a 365-day circular calendar; Feb 29 has no index."""
    if date.month == 2 and date.day == 29:
        return None
    return pd.Timestamp(2001, date.month, date.day).dayofyear - 1


def build_thresholds(data):
    ref = data.loc[data.date.dt.year.between(2018, 2021)].copy()
    ref['calendar_day'] = ref.date.map(calendar_day)
    ref = ref.loc[ref.calendar_day.notna()]
    days = ref.calendar_day.to_numpy(dtype=int)
    years = ref.date.dt.year.to_numpy()
    rows = []
    for day in range(365):
        window = np.minimum((days - day) % 365, (day - days) % 365) <= 15
        row = {'calendar_day': day, 'month_day': pd.Timestamp('2001-01-01').__add__(pd.Timedelta(days=day)).strftime('%m-%d')}
        for metric in ['tmax', 'tmin']:
            values = ref[f'{metric}_c'].to_numpy(dtype=float)
            valid = window & np.isfinite(values)
            n, ny = int(valid.sum()), len(np.unique(years[valid]))
            row[f'{metric}_reference_n'] = n
            row[f'{metric}_reference_years'] = ny
            row[f'q90_{metric}_c'] = float(np.quantile(values[valid], .9, method='linear')) if n >= 112 and ny == 4 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def attach_thresholds(data, thresholds):
    result = data.copy()
    days = result.date.map(calendar_day)
    for metric in ['tmax', 'tmin']:
        name = f'q90_{metric}_c'
        mapping = thresholds.set_index('calendar_day')[name]
        result[name] = days.map(mapping)
        result.loc[days.isna(), name] = (mapping.loc[58] + mapping.loc[59]) / 2
    return result


def warm_season(data):
    ref = data.loc[data.date.dt.year.between(2018, 2021)]

    def choose(frame):
        scores = []
        for start in range(1, 13):
            months = [(start - 1 + i) % 12 + 1 for i in range(3)]
            values = frame.loc[frame.date.dt.month.isin(months), 'tmax_c'].to_numpy(float)
            scores.append(float(np.mean(values[np.isfinite(values)])) if np.isfinite(values).any() else np.nan)
        if not np.isfinite(scores).any():
            return None, scores
        return int(np.nanargmax(scores)) + 1, scores

    start, scores = choose(ref)
    leave = [choose(ref.loc[ref.date.dt.year != year])[0] for year in range(2018, 2022)]
    return {'warm_season_start_month': start,
            'warm_season_mean_tmax_c': scores[start - 1] if start else None,
            'loyo_start_months': json.dumps(leave),
            'loyo_agreement_fraction': sum(item == start for item in leave) / 4 if start else None,
            'reference_valid_fraction': float(np.isfinite(ref.tmax_c).mean())}


def runs(mask):
    padded = np.r_[False, np.asarray(mask, bool), False].astype(int)
    return list(zip(np.flatnonzero(np.diff(padded) == 1), np.flatnonzero(np.diff(padded) == -1) - 1))


def longest(mask):
    return max((b - a + 1 for a, b in runs(mask)), default=0)


def catalogue_country(data, season):
    d = data.sort_values('date').reset_index(drop=True).copy()
    if d.date.duplicated().any() or not d.date.diff().dropna().eq(pd.Timedelta(days=1)).all():
        raise ValueError('Country dates must be unique and complete daily sequence')
    hot = (d.tmax_c > d.q90_tmax_c).to_numpy()
    valid = (np.isfinite(d.tmax_c) & np.isfinite(d.q90_tmax_c)).to_numpy()
    raw = [(a, b) for a, b in runs(hot) if b - a + 1 >= 2]

    def merge(events, mode):
        result = []
        for a, b in events:
            if result:
                prev = result[-1][1]
                gap = slice(prev + 1, a)
                can_merge = valid[gap].all() and ((a - prev == 2 and not hot[prev + 1]) if mode == 'process' else longest(~hot[gap]) < 7)
                if can_merge:
                    result[-1] = (result[-1][0], b)
                    continue
            result.append((a, b))
        return result

    processes = merge(raw, 'process')
    analysis = merge(processes, 'analysis')
    dates = d.date
    country = str(d.country_id.iloc[0])
    output = []
    for level, intervals in [('raw', raw), ('process', processes), ('analysis', analysis)]:
        rows = []
        labels = np.full(len(d), '', dtype=object)
        for a, b in intervals:
            start, end = dates.iloc[a], dates.iloc[b]
            stop = end + pd.Timedelta(days=1)
            event_id = f'{country}_{level}_{start:%Y%m%d}'
            labels[a:b + 1] = event_id
            if stop <= ANALYSIS_START or start >= ANALYSIS_STOP:
                continue
            core = d.iloc[a:b + 1]
            corehot = hot[a:b + 1]
            excess = np.maximum(core.tmax_c.to_numpy() - core.q90_tmax_c.to_numpy(), 0)
            night = core.tmin_c.to_numpy() - core.q90_tmin_c.to_numpy()
            dew = core.dewpoint_c.to_numpy()
            window_start = start - pd.Timedelta(days=7)
            window_stop = max(start + pd.Timedelta(days=8), stop + pd.Timedelta(days=3))
            isolated = True
            for oa, ob in analysis:
                # At analysis level this is the event itself; lower levels belong
                # to this analysis core and do not count their containing event.
                if oa <= a and ob >= b:
                    continue
                if dates.iloc[oa] < window_stop and dates.iloc[ob] + pd.Timedelta(days=4) > window_start:
                    isolated = False
                    break
            complete = window_start >= ANALYSIS_START and window_stop <= ANALYSIS_STOP
            available = window_start >= dates.iloc[0] and window_stop <= dates.iloc[-1] + pd.Timedelta(days=1)
            mask = (dates >= window_start) & (dates < window_stop)
            weather_complete = bool(available and valid[mask.to_numpy()].all())
            in_season = bool(season and start.month in [(season - 1 + i) % 12 + 1 for i in range(3)])
            rows.append(dict(country_id=country, event_id=event_id, start_date=str(start.date()), end_date=str(end.date()),
                             end_exclusive_utc=stop.strftime('%Y-%m-%dT00:00:00Z'), warm_season_start_month=season,
                             in_warm_season=in_season, hot_days=int(corehot.sum()), longest_hot_run=longest(corehot),
                             bridge_days=int((~corehot).sum()), span_days=b - a + 1, hd_c_days=float(excess.sum()),
                             peak_excess_c=float(excess.max()), mean_hot_excess_c=float(excess[corehot].mean()),
                             absolute_tmax_c=float(core.tmax_c.max()),
                             ntrd_c_days=float(np.maximum(night, 0).sum()) if np.isfinite(night).all() else np.nan,
                             tmin_hot_fraction=float((night > 0).mean()) if np.isfinite(night).all() else np.nan,
                             dewpoint_mean_c=float(dew.mean()) if np.isfinite(dew).all() else np.nan,
                             dewpoint_max_c=float(dew.max()) if np.isfinite(dew).all() else np.nan,
                             left_analysis_boundary=bool(start < ANALYSIS_START), right_analysis_boundary=bool(stop >= ANALYSIS_STOP),
                             left_source_boundary=bool(a == 0), right_source_boundary=bool(b == len(d) - 1),
                             complete_analysis_window=bool(complete), complete_weather_window=weather_complete,
                             isolated_weather_event=isolated, weather_candidate=bool(in_season and complete and weather_complete and isolated),
                             network_screened=False))
        d[f'{level}_event_id'] = labels
        d[f'{level}_bridge_day'] = (labels != '') & ~hot
        output.append(pd.DataFrame(rows, columns=EVENT_COLUMNS))
    d['tmax_valid'] = valid
    d['tmax_hot'] = pd.array(np.where(valid, hot.astype(float), np.nan), dtype='Float64')
    d['tmin_hot'] = pd.array(np.where(np.isfinite(d.tmin_c) & np.isfinite(d.q90_tmin_c), (d.tmin_c > d.q90_tmin_c).astype(float), np.nan), dtype='Float64')
    output.append(d)
    return tuple(output)


def load_inputs(directory, countries=None):
    directory = Path(directory)
    months = pd.period_range('2018-01', '2025-12', freq='M')
    paths = [directory / f'era5_country_daily_{month.strftime("%Y%m")}.csv' for month in months]
    missing = [str(path) for path in paths if not path.is_file() or not path.with_suffix('.audit.json').is_file()]
    if missing:
        raise ValueError(f'All 96 monthly CSV/audit pairs required; missing: {missing[:5]}')
    frames, sources, expected_countries = [], [], None
    required = {'country_id', 'date', 'tmax_c', 'tmin_c', 'dewpoint_c', 'total_population'}
    for month, path in zip(months, paths):
        audit_path = path.with_suffix('.audit.json')
        audit = json.loads(audit_path.read_text())
        digest = sha256(path)
        if digest != audit.get('output_sha256'):
            raise ValueError(f'Input hash mismatch: {path}')
        frame = pd.read_csv(path, dtype={'country_id': str})
        if not required <= set(frame.columns):
            raise ValueError(f'Missing columns: {required - set(frame.columns)} in {path}')
        frame['date'] = pd.to_datetime(frame.date, format='%Y-%m-%d', errors='raise')
        if frame.country_id.isna().any() or frame.duplicated(['country_id', 'date']).any():
            raise ValueError(f'Duplicate or missing country/date in {path}')
        found = set(frame.country_id)
        if expected_countries is None:
            expected_countries = found
        if found != expected_countries:
            raise ValueError(f'Country set changed in {path}')
        expected_dates = set(pd.date_range(month.start_time, month.end_time.normalize()))
        if any(set(g.date) != expected_dates for _, g in frame.groupby('country_id')):
            raise ValueError(f'Incomplete or unexpected dates in {path}')
        for name in ['tmax_c', 'tmin_c', 'dewpoint_c', 'total_population']:
            frame[name] = pd.to_numeric(frame[name], errors='raise')
            if np.isinf(frame[name]).any():
                raise ValueError(f'Infinite {name} in {path}')
        if frame.total_population.isna().any() or (frame.total_population < 0).any():
            raise ValueError(f'Invalid population in {path}')
        frames.append(frame)
        sources.append({'month': month.strftime('%Y%m'), 'path': str(path.resolve()), 'sha256': digest,
                        'audit_sha256': sha256(audit_path), 'rows': len(frame)})
    all_data = pd.concat(frames, ignore_index=True)
    exclusions = []
    keep = []
    for country, frame in all_data.groupby('country_id'):
        if frame.total_population.nunique() != 1:
            raise ValueError(f'Fixed population changes for {country}')
        if (frame.total_population == 0).all():
            exclusions.append({'country_id': country, 'reason': 'zero_population',
                               'all_temperature_missing': bool(frame[['tmax_c', 'tmin_c', 'dewpoint_c']].isna().all().all())})
        else:
            keep.append(country)
    if countries is not None:
        if set(countries) - expected_countries:
            raise ValueError(f'Unknown requested countries: {set(countries) - expected_countries}')
        keep = sorted(set(keep) & set(countries))
    return all_data.loc[all_data.country_id.isin(keep)].copy(), sources, exclusions


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--country-daily', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--countries', help='Comma-separated pilot subset; all inputs still validated')
    args = parser.parse_args(argv)
    out = args.output_dir.resolve()
    source = args.country_daily.resolve()
    if out == source or source in out.parents or out in source.parents:
        raise ValueError('Input and output directories must not overlap or be inside each other')
    out.mkdir(parents=True, exist_ok=True)
    lock = out / '.catalogue.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError(f'Catalogue lock exists: {lock}; inspect running process before removing stale lock')
    with os.fdopen(fd, 'w') as handle:
        handle.write(str(os.getpid()))
    started = time.time()
    try:
        atomic(out / 'manifest.json', {'state': 'building', 'script_sha256': sha256(__file__),
                                      'started_epoch': started, 'network_screened': False})
        atomic(out / 'progress.json', {'state': 'validating', 'pid': os.getpid()})
        data, sources, exclusions = load_inputs(args.country_daily, args.countries.split(',') if args.countries else None)
        groups = list(data.groupby('country_id', sort=True))
        thresholds, seasons, daily, raw, process, analysis = [], [], [], [], [], []
        for number, (country, frame) in enumerate(groups, 1):
            q = build_thresholds(frame)
            q.insert(0, 'country_id', country)
            thresholds.append(q)
            season = warm_season(frame)
            seasons.append({'country_id': country, **season})
            flagged = attach_thresholds(frame.loc[frame.date >= '2021-01-01'], q)
            r, p, a, f = catalogue_country(flagged, season['warm_season_start_month'])
            raw.append(r); process.append(p); analysis.append(a); daily.append(f)
            atomic(out / 'progress.json', {'state': 'building', 'country_id': country, 'countries_done': number,
                                           'countries_total': len(groups), 'elapsed_seconds': time.time() - started})
        if not groups:
            raise ValueError('No positive-population requested countries')
        tables = {'thresholds.csv': pd.concat(thresholds), 'warm_seasons.csv': pd.DataFrame(seasons),
                  'daily_heat_flags.csv.gz': pd.concat(daily), 'raw_events.csv': pd.concat(raw),
                  'process_events.csv': pd.concat(process), 'analysis_events.csv': pd.concat(analysis)}
        for name, table in tables.items():
            atomic(out / name, table)
        summary = {'state': 'complete', 'countries': len(groups), 'input_rows_selected': len(data),
                   'zero_population_exclusions': exclusions, 'output_rows': {k: len(v) for k, v in tables.items()},
                   'analysis_events_by_country': tables['analysis_events.csv'].groupby('country_id').size().to_dict(),
                   'network_screened': False, 'elapsed_seconds': time.time() - started}
        atomic(out / 'summary.json', summary)
        manifest = {'schema_version': 1, 'state': 'complete', 'script_sha256': sha256(__file__),
                    'numpy_version': np.__version__, 'pandas_version': pd.__version__, 'sources': sources,
                    'reference_period': ['2018-01-01', '2021-12-31'], 'analysis_period': ['2022-01-01', '2025-12-31'],
                    'context_start': '2021-01-01', 'countries_requested': args.countries, 'excluded_units': exclusions,
                    'threshold': {'quantile': .9, 'method': 'linear', 'calendar_days': 365, 'half_window_days': 15,
                                  'expected_samples': 124, 'minimum_samples': 112, 'required_years': 4,
                                  'leap_day': 'excluded from reference; analysis average of Feb28 and Mar01'},
                    'analysis_merge': 'Merge qualifying processes unless separated by >=7 consecutive complete nonhot days; singleton hot days reset the counter and contribute dose inside merged spans; missing values are barriers.',
                    'isolation': 'Union of start[-7,+7] calendar days and full event core plus 72h must not overlap any other all-year analysis core plus 72h.',
                    'secondary_missingness': 'Any missing metric/threshold day in fixed event span makes its aggregate missing.',
                    'network_screened': False,
                    'outputs': {name: {'sha256': sha256(out / name), 'rows': len(table)} for name, table in tables.items()}}
        atomic(out / 'manifest.json', manifest)
        atomic(out / 'progress.json', summary)
        print(json.dumps(summary, indent=2))
        return 0
    except Exception as exc:
        failure = {'state': 'failed', 'error': str(exc), 'elapsed_seconds': time.time() - started}
        atomic(out / 'progress.json', failure)
        atomic(out / 'manifest.json', failure)
        atomic(out / 'summary.json', failure)
        raise
    finally:
        lock.unlink()


if __name__ == '__main__':
    raise SystemExit(main())
