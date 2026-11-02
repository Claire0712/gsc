#!/usr/bin/env python3
"""Read-only full baseline artifact audit; no baseline or effect re-estimation.

Run on Judy with the existing NumPy environment. Rebuilds exclusion masks with
merged interval lookup, independently of runner/core helpers. Prints a receipt.
"""
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import time
import argparse

import numpy as np


STARTED = time.monotonic()
parser=argparse.ArgumentParser()
for key in ('project','output','heat','candidate','preflight'):parser.add_argument('--'+key,required=True)
parser.add_argument('--cyclone-radius',required=True,type=int,choices=(100,300,500))
parser.add_argument('--cyclone-hours',required=True,type=int,choices=(24,72))
args=parser.parse_args()
ROOT=Path(args.project);OUT=Path(args.output);BASE=OUT.parent
CYCLONE = ROOT/'analysis/2026-10-11_cyclone_screen/v4/full_outputs'
SIGNALS = ('ping-slash24', 'bgp', 'merit-nt')


def digest(path):
    h = hashlib.sha256()
    before = path.stat()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns, before.st_ctime_ns) == (after.st_size, after.st_mtime_ns, after.st_ctime_ns), path
    return dict(bytes=after.st_size, sha256=h.hexdigest())


def read_json(path):
    return json.loads(path.read_text())


def rows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def utc(text):
    return int(datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp())


def boolean(text):
    assert text in ('True', 'False')
    return text == 'True'


def merged(windows, closed=False):
    result = []
    for start, end in sorted(windows):
        end += int(closed)
        assert end > start
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return np.array(result, dtype=np.int64).reshape(-1, 2)


def contains(stamps, intervals):
    if not len(intervals):
        return np.zeros(stamps.shape, dtype=bool)
    indices = np.searchsorted(intervals[:, 0], stamps, side='right') - 1
    return (indices >= 0) & (stamps < intervals[np.maximum(indices, 0), 1])


status = read_json(OUT/'status.json')
assert status['status'] == 'completed'
assert not (Path('/proc')/str(status['pid'])).exists(), 'Baseline process still present'
manifest = read_json(OUT/'manifest.json')
assert manifest['status'] == 'completed'
for path, entry in manifest['inputs'].items():
    assert digest(Path(path)) == entry, path
for name, entry in manifest['outputs'].items():
    assert Path(name).name == name
    assert digest(OUT/name) == entry, name
assert digest(CYCLONE/'manifest.json')['sha256'] == 'b4fa179216b7a04775cd06f85a2b9019cd056e58a1762ec2c35a9dccbfdfd85e'
summary = read_json(OUT/'summary.json')
assert summary['baseline_computed'] is True
assert summary['cyclone_radius_km']==args.cyclone_radius
assert summary['cyclone_half_width_hours']==args.cyclone_hours
complete_start=utc('2018-01-01T00:00:00Z')+args.cyclone_hours*3600
complete_end=utc('2026-01-01T00:00:00Z')-args.cyclone_hours*3600
assert summary['cyclone_complete_bounds']==[complete_start,complete_end]
assert summary['dhrd_computed'] is False and summary['final_sample_eligible'] is False
SIGNALS = tuple(summary['selected_signals'])
assert SIGNALS and set(SIGNALS) <= {'ping-slash24','bgp','merit-nt'}
expected_events=summary['selected_events'];expected_windows=expected_events*len(SIGNALS)
assert summary['signal_windows']==expected_windows
route = rows(OUT/'event_routing.csv')
assert Counter(r['route'] for r in route) == summary['route_counts']
for name in ('event_routing.csv', 'held_stop_review.csv'):
    assert (OUT/name).read_bytes() == (Path(args.candidate)/name).read_bytes()
forward = [r for r in route if r['route'] == 'forward' and r['country_id'] in summary['selected_countries']]
mapping = {r['joint_country_id']: r['ioda_iso2'] for r in rows(Path(args.preflight)/'joint_crosswalk.csv') if r['joint_status'] == 'exact_joint_match'}
assert len(mapping) == 195 and set(summary['selected_countries']) <= set(mapping)
assert len(forward) == expected_events and expected_events > 0

annual = {}
for r in rows(ROOT/'analysis/2026-10-07_parallel_prep/ioda/coverage_annual.csv'):
    annual[r['country_id'], r['signal'], int(r['year'])] = 5*int(r['valid_points']) >= 4*int(r['expected_points'])

heat_days = defaultdict(list)
with gzip.open(Path(args.heat)/'daily_heat_flags.csv.gz', 'rt') as stream:
    for r in csv.DictReader(stream):
        if r['analysis_event_id']:
            heat_days[r['country_id'], r['analysis_event_id']].append(utc(r['date']+'T00:00:00Z'))
heat_windows = defaultdict(list)
for (country, event), days in heat_days.items():
    heat_windows[country].append((min(days), max(days)+4*86400))
stop_windows = defaultdict(list)
unresolved = Counter()
unknown_end = Counter()
for r in read_json(ROOT/'analysis/2026-10-12_stop_windows/v2/outputs/stop_windows.json')['records']:
    if r['windows']:
        stop_windows[r['country_id']].append(r['windows']['main'])
        unknown_end[r['country_id']] += int(r['end_unknown'])
    else:
        unresolved[r['country_id']] += 1

mask_intervals = {}
for country in mapping:
    obj = read_json(CYCLONE/(country+'.json'))
    assert obj['country'] == country
    masks = [merged(heat_windows[country]), merged(stop_windows[country])]
    for mode in ('conservative', 'known'):
        masks.append(merged([(w['start_utc_seconds'], w['end_utc_seconds']) for w in obj['windows'] if w['radius_km'] == args.cyclone_radius and w['half_width_hours'] == args.cyclone_hours and w['mode'] == mode], closed=True))
    mask_intervals[country] = masks


def expected_bits(stamps, country):
    heat, stop, conservative, known = [contains(stamps, intervals) for intervals in mask_intervals[country]]
    assert not np.any(known & ~conservative)
    edge = (stamps < complete_start) | (stamps >= complete_end)
    return heat.astype(np.uint8) + 2*stop + 4*conservative + 8*(conservative & ~known) + 16*edge


def annual_bits(stamps, iso2, signal):
    result = np.zeros(stamps.shape, dtype=bool)
    for year in range(2022, 2026):
        if annual.get((iso2, signal, year), False):
            result |= (stamps >= utc(f'{year}-01-01T00:00:00Z')) & (stamps < utc(f'{year+1}-01-01T00:00:00Z'))
    return result


audit = rows(OUT/'event_baseline_audit.csv')
assert len(audit) == expected_windows
audit_by_key = {(r['event_id'], r['signal']): r for r in audit}
assert len(audit_by_key) == expected_windows
expected_files = set()
statistics = {s: Counter() for s in SIGNALS}
total_slots = 0
for index, event in enumerate(forward):
    start = utc(event['start_date']+'T00:00:00Z')
    end = utc(event['end_exclusive_utc'])
    stamps = np.arange(start, end+72*3600, 600, dtype=np.int64)
    queries = stamps[:, None] + np.array([-28, -21, -14, -7, 7, 14, 21, 28])[None, :]*86400
    target_bits = expected_bits(stamps, event['country_id'])
    reference_bits = expected_bits(queries, event['country_id'])
    reference_present = (queries >= utc('2022-01-01T00:00:00Z')) & (queries < utc('2026-01-01T00:00:00Z'))
    for signal in SIGNALS:
        name = f'points_{index:06d}_{signal}.npz'
        expected_files.add(name)
        row = audit_by_key[event['event_id'], signal]
        assert row['point_file'] == name and row['country_id'] == event['country_id'] and row['ioda_iso2'] == mapping[event['country_id']]
        with np.load(OUT/name, allow_pickle=False) as a:
            assert str(a['event_id']) == event['event_id'] and str(a['country_id']) == event['country_id'] and str(a['signal']) == signal
            np.testing.assert_array_equal(a['target_timestamps'], stamps)
            np.testing.assert_array_equal(a['core_mask'], stamps < end)
            np.testing.assert_array_equal(a['target_exclusion_bits'], target_bits)
            np.testing.assert_array_equal(a['reference_exclusion_bits'], reference_bits)
            np.testing.assert_array_equal(a['reference_present'], reference_present)
            ref_annual = annual_bits(queries, mapping[event['country_id']], signal)
            np.testing.assert_array_equal(a['reference_annual_eligible'], ref_annual)
            target_present = (stamps >= utc('2022-01-01T00:00:00Z')) & (stamps < utc('2026-01-01T00:00:00Z'))
            np.testing.assert_array_equal(a['target_present'], target_present)
            np.testing.assert_array_equal(a['target_finite'], np.isfinite(a['target_values']))
            np.testing.assert_array_equal(a['target_valid'], np.isfinite(a['target_values']) & (a['target_values'] >= 0))
            np.testing.assert_array_equal(a['target_annual_eligible'], annual_bits(stamps, mapping[event['country_id']], signal) & target_present)
            count = a['reference_count']
            np.testing.assert_array_equal(count, a['before_count']+a['after_count'])
            support = reference_present & ref_annual & (reference_bits == 0)
            assert np.all(count <= support.sum(axis=1)) and np.all(count >= 0)
            assert np.all(a['before_count'] <= support[:, :4].sum(axis=1)) and np.all(a['after_count'] <= support[:, 4:].sum(axis=1))
            qualifies = (count >= 4) & (a['before_count'] > 0) & (a['after_count'] > 0)
            np.testing.assert_array_equal(a['reference_count_eligible'], qualifies)
            available = qualifies & np.isfinite(a['reference_median']) & (a['reference_median'] > 0)
            np.testing.assert_array_equal(a['baseline_available'], available)
            np.testing.assert_array_equal(a['baseline'], np.where(available, a['reference_median'], np.nan))
            analysis = available & a['target_valid'] & a['target_annual_eligible']
            clean = analysis & ((target_bits & 22) == 0)
            np.testing.assert_array_equal(a['analysis_available'], analysis)
            np.testing.assert_array_equal(a['target_analysis_unconfounded'], clean)
            np.testing.assert_array_equal(a['target_mask_coverage_complete'], (target_bits & 16) == 0)
            expected_counts = dict(expected_full_slots=len(stamps), target_valid_slots=int(a['target_valid'].sum()), baseline_available_slots=int(available.sum()), analysis_available_slots=int(analysis.sum()), target_stop_or_cyclone_slots=int(np.count_nonzero(target_bits & 6)), target_cyclone_uncertain_slots=int(np.count_nonzero(target_bits & 8)), target_mask_coverage_unknown_slots=int(np.count_nonzero(target_bits & 16)), unresolved_stop_country_records=unresolved[event['country_id']], unknown_end_stop_country_records=unknown_end[event['country_id']])
            for field, value in expected_counts.items():
                assert int(row[field]) == value, (name, field)
            assert boolean(row['full_target_and_baseline']) == bool(analysis.all())
            assert boolean(row['full_observed_unconfounded']) == bool(clean.all())
            assert row['final_sample_eligible'] == 'False'
            statistics[signal].update(signal_windows=1, expected_slots=len(stamps), full_target_and_baseline=int(analysis.all()), full_observed_unconfounded=int(clean.all()), target_valid_slots=int(a['target_valid'].sum()), baseline_available_slots=int(available.sum()), analysis_available_slots=int(analysis.sum()), unconfounded_available_slots=int(clean.sum()), target_stop_or_cyclone_slots=int(np.count_nonzero(target_bits & 6)), target_mask_coverage_unknown_slots=int(np.count_nonzero(target_bits & 16)))
            total_slots += len(stamps)
assert expected_files == {p.name for p in OUT.glob('points_*.npz')}
assert expected_files == {n for n in manifest['outputs'] if n.endswith('.npz')}
for signal in SIGNALS:
    assert statistics[signal]['signal_windows'] == expected_events
    assert statistics[signal]['full_target_and_baseline'] == summary['full_target_and_baseline_by_signal'][signal]
finish = (OUT/'status.json').stat().st_mtime
print(json.dumps(dict(status='verified',manifest_sha256=digest(OUT/'manifest.json')['sha256'],source_files_verified=len(manifest['inputs']),output_files_verified=len(manifest['outputs']),npz_windows_verified=len(expected_files),pointwise_slots_verified=total_slots,route_counts=summary['route_counts'],by_signal=statistics,verification_seconds=time.monotonic()-STARTED,verifier_sha256=digest(Path(__file__))['sha256'],limits='All hashes, windows, pointwise masks/annual gates/support/internal baseline diagnostics. No full raw median re-estimation; separate MYS/AP scalar pilot provides raw-value verification. No DHRD/effect or absent-confounding claim.'),allow_nan=False))
