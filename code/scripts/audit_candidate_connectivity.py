#!/usr/bin/env python3
"""Route approved candidates and audit unmasked potential reference availability.

No baseline, exclusion mask, zero-baseline check, or resilience is computed.
All event intervals and connection labels use right-open UTC ten-minute grids.
"""
import argparse
from collections import Counter, OrderedDict
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile

import numpy as np

SIGNALS = {'ping-slash24': 600, 'bgp': 300, 'merit-nt': 300}
QUARTERS = [f'{year}Q{q}' for year in range(2022, 2026) for q in range(1, 5)]
OFFSETS = [-7, -14, -21, -28, 7, 14, 21, 28]
EVENT_FIELDS = 'event_id country_id start_date end_exclusive_utc weather_candidate network_screened review_window_start_utc review_window_end_exclusive_utc review_only'.split()
AUDIT_FIELDS = 'event_id country_id ioda_iso2 signal core_start_utc core_end_exclusive_utc full_end_exclusive_utc expected_core_slots valid_core_slots zero_core_slots complete_core expected_full_slots valid_full_slots zero_full_slots complete_full analysis_boundary_truncated missing_country missing_country_quarters unmasked_potential_reference_slots unmasked_potential_reference_fraction unmasked_potential_reference_all_slots reference_boundary_truncated reference_missing_country availability_scope downstream_ready_for_baseline'.split()


def now():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return {'sha256': h.hexdigest(), 'bytes': path.stat().st_size}


def atomic(path, data):
    fd, temp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def json_data(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def write_csv(path, fields, rows):
    f = io.StringIO(newline='')
    writer = csv.DictWriter(f, fields)
    writer.writeheader()
    writer.writerows(rows)
    atomic(path, f.getvalue().encode())


def read_csv(path, required):
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, strict=True)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)) or not set(required).issubset(fields):
            raise ValueError(f'{path.name}: missing or duplicate CSV fields')
        rows = list(reader)
    if any(None in r or None in r.values() for r in rows):
        raise ValueError(f'{path.name}: malformed row')
    return fields, rows


def unique(rows, keys):
    seen = set()
    for row in rows:
        value = tuple(row[k] for k in keys)
        if any(not x.strip() for x in value) or value in seen:
            raise ValueError(f'duplicate or empty key: {keys}')
        seen.add(value)


def boolean(text):
    if text not in ('True', 'False', '1', '0'):
        raise ValueError(f'invalid strict boolean: {text!r}')
    return text in ('True', '1')


def utc(value):
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if d.tzinfo is None or d.utcoffset() != timedelta(0):
        raise ValueError('timestamp must be explicitly UTC')
    stamp = d.timestamp()
    if stamp % 600:
        raise ValueError('timestamp must align to UTC 600-second grid')
    return int(stamp)


def iso(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat().replace('+00:00', 'Z')


def quarter_bounds(label):
    year, quarter = int(label[:4]), int(label[-1])
    start = datetime(year, quarter * 3 - 2, 1, tzinfo=timezone.utc)
    end = datetime(year + (quarter == 4), 1 if quarter == 4 else quarter * 3 + 1, 1, tzinfo=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())


BOUNDS = {q: quarter_bounds(q) for q in QUARTERS}
ANALYSIS_START = BOUNDS[QUARTERS[0]][0]
ANALYSIS_END = BOUNDS[QUARTERS[-1]][1]


def verify_outputs(directory, entries):
    result = {}
    for name, metadata in entries:
        if not isinstance(name, str) or Path(name).name != name or name in result:
            raise ValueError('invalid or duplicate manifest output name')
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'missing or symlink output: {name}')
        measured = fingerprint(path)
        if measured['sha256'] != metadata.get('sha256') or ('bytes' in metadata and measured['bytes'] != metadata['bytes']):
            raise ValueError(f'output hash/size mismatch: {name}')
        result[name] = measured
    return result


def inputs(preflight, connection):
    metadata_paths = [preflight / 'status.json', preflight / 'manifest.json', connection / 'manifest.json']
    snapshot = {path: file_stat(path) for path in metadata_paths}
    metadata_bytes = {path: path.read_bytes() for path in metadata_paths}
    check_snapshot(snapshot)
    pstatus, pmanifest, cmanifest = (json.loads(metadata_bytes[path]) for path in metadata_paths)
    if pstatus.get('status') != 'completed':
        raise ValueError('preflight is not completed')
    if cmanifest.get('state') != 'complete' or cmanifest.get('quarters') != QUARTERS:
        raise ValueError('connection manifest must be complete for 2022Q1–2025Q4')
    for directory, names in ((preflight, pmanifest['outputs']), (connection, [entry['file'] for entry in cmanifest['outputs']])):
        for name in names:
            if not isinstance(name, str) or Path(name).name != name:
                raise ValueError('invalid manifest output name')
            snapshot[directory / name] = file_stat(directory / name)
    check_snapshot(snapshot)
    phashes = verify_outputs(preflight, pmanifest['outputs'].items())
    chashes = verify_outputs(connection, ((x['file'], x) for x in cmanifest['outputs']))
    check_snapshot(snapshot)
    required = {'event_review_windows.csv', 'joint_crosswalk.csv', 'stop_event_review.csv'}
    expected = {f'ioda_{q}_{s}.npz' for q in QUARTERS for s in SIGNALS}
    if not required.issubset(phashes) or not expected.issubset(chashes):
        raise ValueError('required outputs absent from verified manifest')
    if {name for name in chashes if name.endswith('.npz')} != expected:
        raise ValueError('connection must contain exactly the 48 expected NPZ files')
    fields, events = read_csv(preflight / 'event_review_windows.csv', EVENT_FIELDS)
    _, cross = read_csv(preflight / 'joint_crosswalk.csv', ['ioda_iso2', 'joint_country_id', 'joint_status'])
    _, stop = read_csv(preflight / 'stop_event_review.csv', ['event_id', 'source_row', 'review_only'])
    unique(events, ['event_id'])
    unique(cross, ['ioda_iso2'])
    unique(stop, ['event_id', 'source_row'])
    exact = [r for r in cross if r['joint_status'] == 'exact_joint_match']
    unique(exact, ['joint_country_id'])
    if any(not re.fullmatch('[A-Z]{2}', r['ioda_iso2']) for r in cross):
        raise ValueError('invalid crosswalk ISO2')
    if any(not boolean(r['review_only']) for r in stop):
        raise ValueError('STOP rows must be review_only')
    event_ids = {e['event_id'] for e in events}
    if any(r['event_id'] not in event_ids for r in stop):
        raise ValueError('STOP event_id absent from event catalogue')
    check_snapshot(snapshot)
    metadata_hashes = {path: {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)} for path, data in metadata_bytes.items()}
    return fields, events, exact, stop, {'preflight': {'path': str(preflight), 'manifest': metadata_hashes[preflight / 'manifest.json'], 'status': metadata_hashes[preflight / 'status.json'], 'outputs': phashes}, 'connection': {'path': str(connection), 'manifest': metadata_hashes[connection / 'manifest.json'], 'outputs': chashes}}, snapshot


def route_events(events, exact, stop):
    mapping = {r['joint_country_id']: r['ioda_iso2'] for r in exact}
    held = {r['event_id'] for r in stop}
    routed = []
    for event in events:
        candidate = boolean(event['weather_candidate'])
        boolean(event['network_screened'])
        if not boolean(event['review_only']):
            raise ValueError('event must be review_only')
        event_bounds(event)
        country = mapping.get(event['country_id'], '')
        route = 'unmatched_country' if not country else 'not_weather_candidate' if not candidate else 'held_stop_review' if event['event_id'] in held else 'forward'
        routed.append(dict(event, route=route, ioda_iso2=country))
    return routed


def event_bounds(event):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', event['start_date']):
        raise ValueError('start_date must be a calendar date')
    start = utc(event['start_date'] + 'T00:00:00Z')
    end = utc(event['end_exclusive_utc'])
    full = end + 72 * 3600
    if end <= start or utc(event['review_window_start_utc']) != start or utc(event['review_window_end_exclusive_utc']) != full:
        raise ValueError('event/review UTC windows inconsistent')
    return start, end, full


def load_archive(directory, quarter, signal, validate=True):
    with np.load(directory / f'ioda_{quarter}_{signal}.npz', allow_pickle=False) as f:
        required = {'values', 'country_ids', 'native_phase_seconds', 'interval_start_utc'}
        if not required.issubset(f.files):
            raise ValueError('missing NPZ fields')
        values, countries, phases, times = (f[k] for k in ('values', 'country_ids', 'native_phase_seconds', 'interval_start_utc'))
    if not validate:
        return values, {str(c): i for i, c in enumerate(countries)}, phases
    start, end = BOUNDS[quarter]
    if countries.ndim != 1 or countries.dtype.kind not in 'US' or len(set(countries.tolist())) != len(countries):
        raise ValueError('country_ids must be unique ISO2 strings')
    countries = countries.astype(str)
    if any(not re.fullmatch('[A-Z]{2}', c) for c in countries):
        raise ValueError('country_ids must be ISO2')
    if times.dtype != np.dtype('int64') or times.ndim != 1 or not np.array_equal(times, np.arange(start, end, 600, dtype=np.int64)):
        raise ValueError('invalid quarterly 600-second grid')
    if values.dtype != np.dtype('float64') or values.shape != (len(countries), len(times)):
        raise ValueError('invalid values dtype or dimensions')
    if np.any(np.isinf(values)) or np.any(values < 0):
        raise ValueError('values must be finite nonnegative or NaN')
    if phases.shape != (len(countries),) or phases.dtype.kind not in 'iu' or np.any((phases < -1) | (phases >= SIGNALS[signal])):
        raise ValueError('invalid native phase')
    if np.any(np.isfinite(values[phases == -1])):
        raise ValueError('native phase -1 cannot have observed values')
    return values, {c: i for i, c in enumerate(countries)}, phases


def connection_stats(directory):
    return {f'ioda_{q}_{s}.npz': file_stat(directory / f'ioda_{q}_{s}.npz') for q in QUARTERS for s in SIGNALS}


def file_stat(path):
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino


def check_snapshot(snapshot):
    for path, expected in snapshot.items():
        try:
            observed = file_stat(path)
        except OSError as exc:
            raise ValueError(f'source changed or removed after initial snapshot: {path}') from exc
        if observed != expected:
            raise ValueError(f'source changed after initial snapshot: {path}')


def validate_archives(directory, progress=None):
    history = {}
    count = 0
    for signal in SIGNALS:
        for quarter in QUARTERS:
            values, countries, phases = load_archive(directory, quarter, signal)
            for country, idx in countries.items():
                phase = int(phases[idx])
                if phase < 0 or not np.isfinite(values[idx]).any():
                    continue
                key = (country, signal)
                if key in history and history[key] != phase:
                    raise ValueError(f'inconsistent observed native phase: {country}/{signal}')
                history[key] = phase
            del values
            count += 1
            if progress:
                progress(stage='validate_archives', validated_archives=count, current_signal=signal, current_quarter=quarter)
    return {country + '/' + signal: phase for (country, signal), phase in sorted(history.items())}


class QuarterCache:
    """One signal at a time, with no more than two quarterly matrices retained."""
    def __init__(self, directory, signal, stats=None):
        self.directory, self.signal = directory, signal
        self.cache = OrderedDict()
        self.stats = stats

    def sample(self, country, stamps):
        result = np.full(len(stamps), np.nan)
        missing = set()
        for quarter, (start, end) in BOUNDS.items():
            selected = (stamps >= start) & (stamps < end)
            if not selected.any():
                continue
            name = f'ioda_{quarter}_{self.signal}.npz'
            if self.stats is not None and file_stat(self.directory / name) != self.stats[name]:
                raise ValueError(f'connection input changed after verification: {name}')
            if quarter not in self.cache:
                if len(self.cache) >= 2:
                    self.cache.popitem(last=False)
                self.cache[quarter] = load_archive(self.directory, quarter, self.signal, validate=self.stats is None)
            self.cache.move_to_end(quarter)
            values, countries, _ = self.cache[quarter]
            if country not in countries:
                missing.add(quarter)
            else:
                result[selected] = values[countries[country], (stamps[selected] - start)//600]
            del values, countries
        return result, missing


def reference_gate(valid):
    """Rows are -7,-14,-21,-28,+7,+14,+21,+28 days; zeros are valid."""
    return (valid.sum(axis=0) >= 4) & valid[:4].any(axis=0) & valid[4:].any(axis=0)


def audit_events(directory, events, stats=None, progress=None):
    rows = []
    # Chronology improves the bounded quarterly cache without reordering routes.
    ordered = sorted(events, key=lambda e: (e['start_date'], e['end_exclusive_utc'], e['event_id']))
    for signal in SIGNALS:
        cache = QuarterCache(directory, signal, stats)
        for index, event in enumerate(ordered, 1):
            start, end, full = event_bounds(event)
            stamps = np.arange(start, full, 600, dtype=np.int64)
            values, missing = cache.sample(event['ioda_iso2'], stamps)
            valid = np.isfinite(values)
            core = stamps < end
            refs = []
            reference_missing = set()
            for days in OFFSETS:
                samples, absent = cache.sample(event['ioda_iso2'], stamps + days * 86400)
                refs.append(np.isfinite(samples))
                reference_missing.update(absent)
            potential = reference_gate(np.array(refs))
            rows.append(dict(event_id=event['event_id'], country_id=event['country_id'], ioda_iso2=event['ioda_iso2'], signal=signal, core_start_utc=iso(start), core_end_exclusive_utc=iso(end), full_end_exclusive_utc=iso(full), expected_core_slots=int(core.sum()), valid_core_slots=int(valid[core].sum()), zero_core_slots=int((values[core] == 0).sum()), complete_core=bool(valid[core].all()), expected_full_slots=len(stamps), valid_full_slots=int(valid.sum()), zero_full_slots=int((values == 0).sum()), complete_full=bool(valid.all()), analysis_boundary_truncated=start < ANALYSIS_START or full > ANALYSIS_END, missing_country=bool(missing), missing_country_quarters=';'.join(sorted(missing)), unmasked_potential_reference_slots=int(potential.sum()), unmasked_potential_reference_fraction=float(potential.mean()), unmasked_potential_reference_all_slots=bool(potential.all()), reference_boundary_truncated=start - 28 * 86400 < ANALYSIS_START or full + 28 * 86400 > ANALYSIS_END, reference_missing_country=bool(reference_missing), availability_scope='unmasked_potential_only', downstream_ready_for_baseline=False))
            if progress and (index % 20 == 0 or index == len(events)):
                progress(stage='audit_events', current_signal=signal, processed_events=index, total_events=len(events), processed_signal_windows=len(rows))
        del cache
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('preflight-dir', 'connection-dir', 'output-dir'):
        parser.add_argument('--' + key, required=True, type=Path)
    args = parser.parse_args(argv)
    out = args.output_dir.resolve()
    preflight, connection = args.preflight_dir.resolve(), args.connection_dir.resolve()
    lock = out.parent / ('.' + out.name + '.lock')
    owned = acquired = False
    common = dict(schema_version=1, pid=os.getpid(), started_utc=now(), downstream_ready_for_baseline=False)
    try:
        script_path = Path(__file__).resolve()
        script_snapshot = {script_path: file_stat(script_path)}
        script_hash = fingerprint(script_path)['sha256']
        check_snapshot(script_snapshot)
        if any(out == p or out in p.parents or p in out.parents for p in (preflight, connection)):
            raise ValueError('input/output overlap')
        if out.exists():
            raise ValueError('output directory must be fresh (must not exist)')
        out.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        acquired = True
        with os.fdopen(fd, 'w') as f:
            f.write(str(os.getpid()))
        out.mkdir()
        owned = True
        status = dict(common, status='running', updated_utc=now())
        def progress(**updates):
            status.update(updates, updated_utc=now())
            atomic(out / 'status.json', json_data(status))
        progress(stage='verify_input_hashes')
        stats = connection_stats(connection)
        fields, events, exact, stop, sources, source_snapshot = inputs(preflight, connection)
        source_snapshot.update(script_snapshot)
        if stats != connection_stats(connection):
            raise ValueError('connection inputs changed during hash verification')
        if set(fields) & {'route', 'ioda_iso2'}:
            raise ValueError('input columns collide with generated routing columns')
        routed = route_events(events, exact, stop)
        phase_history = validate_archives(connection, progress)
        forward = [r for r in routed if r['route'] == 'forward']
        audits = audit_events(connection, forward, stats, progress)
        if stats != connection_stats(connection):
            raise ValueError('connection inputs changed during audit')
        check_snapshot(source_snapshot)
        files = {'event_routing.csv': (fields + ['route', 'ioda_iso2'], routed), 'held_stop_review.csv': (fields + ['route', 'ioda_iso2'], [r for r in routed if r['route'] == 'held_stop_review']), 'forward_candidates.csv': (fields + ['route', 'ioda_iso2'], forward), 'signal_window_audit.csv': (AUDIT_FIELDS, audits)}
        outputs = {}
        for name, (columns, rows) in files.items():
            write_csv(out / name, columns, rows)
            outputs[name] = dict(fingerprint(out / name), rows=len(rows), columns=columns)
        summary = dict(common, availability_scope='unmasked_potential_only', route_counts=dict(Counter(r['route'] for r in routed)), input_event_count=len(events), signal_window_rows=len(audits), complete_full_by_signal={s: sum(r['complete_full'] for r in audits if r['signal'] == s) for s in SIGNALS}, reference_offsets_days=OFFSETS, reference_rule='At least four finite nonnegative observations, including at least one past and one future observation per target slot.', masks_applied=[], baseline_computed=False, zero_baseline_checked=False, phase_policy='Fail entire stage on inconsistent observed country/signal phases across quarters.', interval_semantics='UTC right-open 600-second interval labels; complete requires every original window slot, including outside analysis boundary.')
        atomic(out / 'summary.json', json_data(summary))
        outputs['summary.json'] = fingerprint(out / 'summary.json')
        check_snapshot(source_snapshot)
        atomic(out / 'manifest.json', json_data(dict(common, status='completed', finished_utc=now(), script_sha256=script_hash, inputs=sources, outputs=outputs, observed_native_phase_seconds=phase_history, phase_history_scope='Only countries/signals with finite nonnegative observations; absent keys have no observed phase.', hash_scope='All data outputs and summary; mutable status and self-referential manifest excluded.')))
        atomic(out / 'status.json', json_data(dict(common, status='completed', updated_utc=now(), finished_utc=now())))
        return 0
    except Exception as exc:
        if owned:
            atomic(out / 'status.json', json_data(dict(common, status='failed', updated_utc=now(), finished_utc=now(), error=str(exc))))
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if acquired:
            lock.unlink()


if __name__ == '__main__':
    sys.exit(main())
