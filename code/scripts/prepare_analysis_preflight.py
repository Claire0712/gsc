#!/usr/bin/env python3
"""Exact country coverage and STOP/event candidate review; never exclusion masks.

STOP dates are calendar proxies in UTC, with unknown source timezones. All
intervals are right-open. An unknown end contributes only its known start day
plus separate uncertainty review, never an unbounded exclusion interval.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

SCHEMAS = {
    'crosswalk': 'ioda_iso2 ioda_name worldbank_iso3 worldbank_name mapping_status'.split(),
    'countries': 'country_id total_population country_name'.split(),
    'events': 'event_id country_id start_date end_exclusive_utc weather_candidate network_screened'.split(),
    'stop': 'source_row normalized_start_date normalized_end_date date_interval_status bounded_interval_eligible normalized_geo_scope matched_worldbank_iso3 country_match_status qa_flags shutdown_extent area_name'.split(),
}
REVIEW_FIELDS = 'event_id source_row country_id event_start_utc event_end_plus_72h_utc stop_start_utc stop_end_exclusive_utc normalized_geo_scope shutdown_extent area_name qa_flags date_interval_status bounded_interval_eligible country_match_status weather_candidate network_screened review_reason review_only source_timezone interval_semantics'.split()


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(path, data):
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def csv_bytes(fields, rows):
    if len(fields) != len(set(fields)):
        raise ValueError('source columns collide with generated preflight columns')
    handle = io.StringIO(newline='')
    writer = csv.DictWriter(handle, fields, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode()


def read_source(path, required):
    data = path.read_bytes()
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''), strict=True)
    fields = reader.fieldnames or []
    if len(fields) != len(set(fields)) or not set(required).issubset(fields):
        raise ValueError(f'{path}: duplicate or missing required CSV columns')
    rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f'{path}: malformed CSV row')
    return fields, rows, {'path': str(path), 'sha256': digest(data), 'bytes': len(data), 'rows': len(rows)}


def unique(rows, key):
    values = [row[key] for row in rows]
    if any(not value.strip() for value in values) or len(values) != len(set(values)):
        raise ValueError(f'duplicate or empty {key}')


def positive_population(value):
    try:
        number = float(value)
        return math.isfinite(number) and number > 0
    except ValueError:
        return False


def calendar_day(value):
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        raise ValueError('date must be YYYY-MM-DD')
    return datetime.combine(date.fromisoformat(value), time(), timezone.utc)


def utc_text(value):
    return value.isoformat().replace('+00:00', 'Z') if value else ''


def event_interval(row):
    start = calendar_day(row['start_date'])
    end = datetime.fromisoformat(row['end_exclusive_utc'].replace('Z', '+00:00'))
    if end.tzinfo is None or end.utcoffset() != timedelta(0) or end <= start:
        raise ValueError(f"event {row['event_id']}: invalid UTC right-open interval")
    return start, end + timedelta(hours=72)


def build(sources):
    cross, countries, events, stop = (sources[key][1] for key in SCHEMAS)
    for rows, key in ((cross, 'ioda_iso2'), (countries, 'country_id'), (events, 'event_id'), (stop, 'source_row')):
        unique(rows, key)
    boundary = {row['country_id']: row for row in countries}
    candidates = Counter(row['worldbank_iso3'] for row in cross if row['mapping_status'] == 'exact_iso2_match' and row['worldbank_iso3'])
    joint = []
    mapped = {}
    for row in cross:
        cid = row['worldbank_iso3']
        if row['mapping_status'] != 'exact_iso2_match' or not cid:
            status = 'source_not_exact'
        elif candidates[cid] > 1:
            status = 'ambiguous_many_to_one'
        elif cid not in boundary:
            status = 'boundary_not_found'
        elif not positive_population(boundary[cid]['total_population']):
            status = 'nonpositive_or_invalid_population'
        else:
            status = 'exact_joint_match'
            mapped[cid] = row['ioda_iso2']
        joint.append(dict(row, joint_status=status, joint_country_id=cid if status == 'exact_joint_match' else '', boundary_country_name=boundary.get(cid, {}).get('country_name', ''), boundary_total_population=boundary.get(cid, {}).get('total_population', '')))
    coverage = []
    for row in countries:
        cid = row['country_id']
        status = ('nonpositive_or_invalid_population' if not positive_population(row['total_population']) else 'exact_joint_match' if cid in mapped else 'ambiguous_many_to_one' if candidates[cid] > 1 else 'no_exact_ioda_match')
        coverage.append(dict(row, coverage_status=status, ioda_iso2=mapped.get(cid, '')))
    by_country = defaultdict(list)
    event_rows = []
    for row in events:
        if row['country_id'] not in boundary:
            raise ValueError(f"event {row['event_id']}: unknown country_id {row['country_id']}")
        start, end = event_interval(row)
        by_country[row['country_id']].append((row, start, end))
        event_rows.append(dict(row, review_window_start_utc=utc_text(start), review_window_end_exclusive_utc=utc_text(end), review_only='1'))
    unresolved, reviews = [], []
    for row in stop:
        reasons = []
        start = end = None
        for field, label in (('normalized_start_date', 'start'), ('normalized_end_date', 'end')):
            value = row[field]
            if not value:
                reasons.append('missing_' + label)
            else:
                try:
                    parsed = calendar_day(value)
                    if label == 'start':
                        start = parsed
                    else:
                        end = parsed
                except ValueError:
                    reasons.append('invalid_' + label)
        # Normalization can erase invalid raw dates; retain upstream QA semantics.
        flags = row['qa_flags'].lower()
        if 'start_date_invalid' in flags and 'invalid_start' not in reasons:
            reasons.append('invalid_start')
        if 'end_date_invalid' in flags and 'invalid_end' not in reasons:
            reasons.append('invalid_end')
        if start and end and end < start:
            reasons.append('reversed_dates')
        if row['date_interval_status'] == 'reversed' and 'reversed_dates' not in reasons:
            reasons.append('reversed_dates')
        cid = row['matched_worldbank_iso3']
        matched = row['country_match_status'] == 'exact_name_match' and cid in boundary
        if not matched:
            reasons.append('unmatched_exact_country')
        bounded = bool(start and end and not reasons and row['date_interval_status'] == 'complete' and row['bounded_interval_eligible'] == '1')
        if start and end and not bounded and not any(r in reasons for r in ('reversed_dates', 'invalid_start', 'invalid_end')):
            reasons.append('bounded_status_not_eligible')
        if reasons:
            unresolved.append(dict(row, unresolved_reason=';'.join(reasons), review_only='1'))
        if not matched:
            continue
        known_day = bool(start and not row['normalized_end_date'] and 'invalid_end' not in reasons and 'reversed_dates' not in reasons)
        stop_end = end + timedelta(days=1) if bounded else start + timedelta(days=1) if known_day else None
        for event, event_start, event_end in by_country[cid]:
            reason = ''
            if (bounded or known_day) and start < event_end and stop_end > event_start:
                reason = 'bounded_calendar_proxy_overlap' if bounded else 'known_start_day_overlap'
            elif known_day and event_start >= stop_end:
                reason = 'open_ended_uncertainty'
            elif not start and not any(r in reasons for r in ('invalid_start', 'invalid_end', 'reversed_dates')):
                # A trustworthy known end limits an unknown-start interval;
                # later events cannot overlap and must not fall through.
                if end is None or event_start < end + timedelta(days=1):
                    reason = 'unknown_start_uncertainty'
            elif not bounded and not known_day:
                reason = 'invalid_interval_uncertainty'
            if reason:
                reviews.append(dict(row, event_id=event['event_id'], country_id=cid, event_start_utc=utc_text(event_start), event_end_plus_72h_utc=utc_text(event_end), stop_start_utc=utc_text(start), stop_end_exclusive_utc=utc_text(stop_end), weather_candidate=event['weather_candidate'], network_screened=event['network_screened'], review_reason=reason, review_only='1', source_timezone='unknown', interval_semantics='UTC_calendar_proxy_right_open'))
    files = {
        'joint_crosswalk.csv': (sources['crosswalk'][0] + ['joint_status', 'joint_country_id', 'boundary_country_name', 'boundary_total_population'], joint),
        'boundary_coverage.csv': (sources['countries'][0] + ['coverage_status', 'ioda_iso2'], coverage),
        'event_review_windows.csv': (sources['events'][0] + ['review_window_start_utc', 'review_window_end_exclusive_utc', 'review_only'], event_rows),
        'stop_unresolved.csv': (sources['stop'][0] + ['unresolved_reason', 'review_only'], unresolved),
        'stop_event_review.csv': (REVIEW_FIELDS, reviews),
    }
    summary = {'downstream_ready_for_baseline': False, 'purpose': 'candidate_preflight_review_only', 'exclusion_masks_created': False, 'source_timezone': 'unknown', 'interval_policy': 'STOP inclusive dates converted to UTC calendar proxy right-open intervals; missing ends use only start day plus separate later uncertainty review; local/service scope is preserved and never inferred national', 'counts': {name: len(rows) for name, (_, rows) in files.items()}, 'joint_status_counts': dict(Counter(row['joint_status'] for row in joint)), 'review_reason_counts': dict(Counter(row['review_reason'] for row in reviews))}
    return files, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in SCHEMAS:
        parser.add_argument('--' + key, required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(argv)
    started = now()
    out = args.output_dir.resolve()
    lock = out.parent / ('.' + out.name + '.lock')
    acquired = owned = False
    try:
        paths = {key: getattr(args, key).resolve() for key in SCHEMAS}
        if any(path == out or out in path.parents or path == lock for path in paths.values()):
            raise ValueError('input/output overlap')
        if out.exists():
            raise ValueError('output directory must be fresh (must not exist)')
        out.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        acquired = True
        with os.fdopen(fd, 'w') as handle:
            handle.write(str(os.getpid()))
        out.mkdir()
        owned = True
        atomic_write(out / 'status.json', json_bytes({'status': 'running', 'pid': os.getpid(), 'updated_utc': now(), 'started_at': started, 'downstream_ready_for_baseline': False}))
        sources = {key: read_source(paths[key], SCHEMAS[key]) for key in SCHEMAS}
        files, summary = build(sources)
        outputs = {}
        for name, (fields, rows) in files.items():
            data = csv_bytes(fields, rows)
            atomic_write(out / name, data)
            outputs[name] = {'sha256': digest(data), 'bytes': len(data), 'rows': len(rows)}
        data = json_bytes(summary)
        atomic_write(out / 'summary.json', data)
        outputs['summary.json'] = {'sha256': digest(data), 'bytes': len(data)}
        atomic_write(out / 'manifest.json', json_bytes({'schema_version': 1, 'script_sha256': digest(Path(__file__).read_bytes()), 'started_at': started, 'finished_at': now(), 'downstream_ready_for_baseline': False, 'sources': {key: source[2] for key, source in sources.items()}, 'outputs': outputs, 'hash_scope': 'All data outputs and summary; manifest and mutable run status excluded to avoid self-reference.'}))
        atomic_write(out / 'status.json', json_bytes({'status': 'completed', 'pid': os.getpid(), 'updated_utc': now(), 'started_at': started, 'finished_at': now(), 'downstream_ready_for_baseline': False}))
        return 0
    except Exception as exc:
        if owned:
            atomic_write(out / 'status.json', json_bytes({'status': 'failed', 'pid': os.getpid(), 'updated_utc': now(), 'started_at': started, 'finished_at': now(), 'error': str(exc), 'downstream_ready_for_baseline': False}))
        print(f'preflight failed: {exc}', file=sys.stderr)
        return 1
    finally:
        if acquired:
            lock.unlink()


if __name__ == '__main__':
    raise SystemExit(main())
