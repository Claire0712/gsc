#!/usr/bin/env python3
"""Screen candidate event windows using annual native-cadence coverage.

This stage is unmasked and provisional. It does not qualify reference years,
compute a baseline, apply exclusion masks, or declare final sample eligibility.
"""
import argparse
import calendar
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

SIGNALS = {'ping-slash24': 600, 'bgp': 300, 'merit-nt': 300}
ANNUAL_FIELDS = 'country_id year signal expected_points valid_points candidate_80pct'.split()
CANDIDATE_FIELDS = 'event_id country_id ioda_iso2 signal core_start_utc full_end_exclusive_utc complete_full unmasked_potential_reference_all_slots'.split()
ADDED_FIELDS = 'annual_years annual_missing_years annual_failed_years annual_start_year_pass annual_all_window_years_pass annual_coverage_details_json provisional_full_and_annual provisional_full_refs_and_annual final_sample_eligible'.split()


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def atomic(path, data):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def file_stat(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f'input must be a regular non-symlink file: {path}')
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def check_snapshot(snapshot):
    for path, initial in snapshot.items():
        if file_stat(path) != initial:
            raise ValueError(f'input changed during screening: {path}')


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'duplicate JSON key: {key}')
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError(f'invalid JSON constant: {value}')
    result = json.loads(data, object_pairs_hook=pairs, parse_constant=reject_constant)
    if not isinstance(result, dict):
        raise ValueError('JSON metadata must be an object')
    return result


def basename(name):
    if (not isinstance(name, str) or not name or name in ('.', '..')
            or Path(name).name != name or '\\' in name or '\x00' in name):
        raise ValueError(f'invalid manifest output basename: {name!r}')
    return name


def read_inputs(quality, candidate, script):
    """Hash and parse the same bytes, retaining one read per source path."""
    paths = [quality / 'manifest.json', candidate / 'manifest.json', candidate / 'status.json', script]
    snapshot = {path: file_stat(path) for path in paths}
    content = {path: path.read_bytes() for path in paths}
    check_snapshot(snapshot)
    qm, cm, cs = (strict_json(content[p]) for p in paths[:3])
    if qm.get('state') != 'completed':
        raise ValueError('quality manifest state must be completed')
    if cs.get('status') != 'completed':
        raise ValueError('candidate status must be completed')
    if not isinstance(qm.get('outputs'), list) or not isinstance(cm.get('outputs'), dict):
        raise ValueError('invalid upstream manifest outputs structure')
    groups = {}
    for label, directory, entries in (
            ('quality', quality, [(entry.get('file'), entry) for entry in qm['outputs']]),
            ('candidate', candidate, list(cm['outputs'].items()))):
        group = {}
        for name, meta in entries:
            basename(name)
            if name in group or not isinstance(meta, dict):
                raise ValueError('duplicate or invalid manifest output')
            if not isinstance(meta.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', meta['sha256']):
                raise ValueError(f'invalid sha256 metadata: {name}')
            if type(meta.get('bytes')) is not int or meta['bytes'] < 0:
                raise ValueError(f'invalid bytes metadata: {name}')
            group[name] = meta
            path = directory / name
            if path not in snapshot:
                snapshot[path] = file_stat(path)
        groups[label] = group
    if not {'coverage_annual.csv', 'summary.json'}.issubset(groups['quality']):
        raise ValueError('consumed quality files absent from manifest')
    if 'signal_window_audit.csv' not in groups['candidate']:
        raise ValueError('consumed candidate file absent from manifest')
    check_snapshot(snapshot)
    for path in snapshot:
        if path not in content:
            content[path] = path.read_bytes()
    check_snapshot(snapshot)
    sources = {}
    for label, directory in (('quality', quality), ('candidate', candidate)):
        hashes = {}
        for name, meta in groups[label].items():
            measured = digest(content[directory / name])
            if any(measured[key] != meta[key] for key in ('sha256', 'bytes')):
                raise ValueError(f'output hash/size mismatch: {directory / name}')
            hashes[name] = measured
        sources[label] = {'path': str(directory), 'manifest': digest(content[directory / 'manifest.json']), 'outputs': hashes}
    sources['candidate']['status'] = digest(content[candidate / 'status.json'])
    if strict_json(content[quality / 'summary.json']).get('quality_pass') is not True:
        raise ValueError('quality summary quality_pass must be true')
    af, annuals = read_csv(content[quality / 'coverage_annual.csv'], ANNUAL_FIELDS)
    fields, events = read_csv(content[candidate / 'signal_window_audit.csv'], CANDIDATE_FIELDS)
    row_count = groups['candidate']['signal_window_audit.csv'].get('rows')
    if type(row_count) is not int or row_count != len(events):
        raise ValueError('candidate manifest CSV row count mismatch')
    check_snapshot(snapshot)
    return annuals, fields, events, sources, snapshot, digest(content[script])


def read_csv(data, required):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''), strict=True)
    fields = reader.fieldnames or []
    if (not fields or any(not name.strip() for name in fields) or len(fields) != len(set(fields))
            or not set(required).issubset(fields)):
        raise ValueError('CSV missing, empty, or duplicate fields')
    rows = list(reader)
    if any(None in row or None in row.values() for row in rows):
        raise ValueError('malformed CSV row width')
    return fields, rows


def boolean(value):
    if value not in ('True', 'False', '1', '0'):
        raise ValueError(f'invalid strict boolean: {value!r}')
    return value in ('True', '1')


def integer(value):
    if not re.fullmatch(r'0|[1-9][0-9]*', value):
        raise ValueError(f'invalid nonnegative integer: {value!r}')
    return int(value)


def unique_key(row, fields, seen):
    key = tuple(row[field] for field in fields)
    if any(not value or value != value.strip() for value in key) or key in seen:
        raise ValueError(f'duplicate or empty key: {fields}')
    seen.add(key)
    return key


def utc(value):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)', value):
        raise ValueError('timestamp must be explicitly UTC ISO 8601')
    fraction = re.search(r'\.(\d+)', value)
    if fraction and any(digit != '0' for digit in fraction.group(1)):
        raise ValueError('timestamp must align to UTC 600-second grid')
    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.microsecond or value.second or value.minute % 10:
        raise ValueError('timestamp must align to UTC 600-second grid')
    return value


def screen(annuals, fields, events):
    if set(fields) & set(ADDED_FIELDS):
        raise ValueError('candidate columns collide with screening columns')
    coverage, seen = {}, set()
    for row in annuals:
        unique_key(row, ('country_id', 'signal', 'year'), seen)
        signal = row['signal']
        year = integer(row['year'])
        if signal not in SIGNALS or year not in range(2022, 2026):
            raise ValueError('unsupported annual signal or year')
        expected, valid = integer(row['expected_points']), integer(row['valid_points'])
        native_expected = (366 if calendar.isleap(year) else 365) * 86400 // SIGNALS[signal]
        if expected != native_expected or valid > expected:
            raise ValueError('annual counts inconsistent with full native calendar year')
        passed = 5 * valid >= 4 * expected
        if boolean(row['candidate_80pct']) != passed:
            raise ValueError('candidate_80pct disagrees with exact annual threshold')
        coverage[row['country_id'], signal, year] = dict(year=year, expected_points=expected, valid_points=valid, annual_pass=passed, missing=False)
    result, seen = [], set()
    for row in events:
        unique_key(row, ('event_id', 'signal'), seen)
        if row['signal'] not in SIGNALS or not row['country_id'].strip() or not row['ioda_iso2'].strip():
            raise ValueError('unsupported candidate signal or empty country')
        complete, references = boolean(row['complete_full']), boolean(row['unmasked_potential_reference_all_slots'])
        start, end = utc(row['core_start_utc']), utc(row['full_end_exclusive_utc'])
        if end <= start:
            raise ValueError('event window must be positive and right-open')
        years = list(range(start.year, (end - timedelta(microseconds=1)).year + 1))
        details = [coverage.get((row['ioda_iso2'], row['signal'], year), dict(year=year, missing=True, expected_points=None, valid_points=None, annual_pass=False)) for year in years]
        missing = [r['year'] for r in details if r['missing']]
        failed = [r['year'] for r in details if not r['missing'] and not r['annual_pass']]
        all_pass = all(r['annual_pass'] for r in details)
        result.append(dict(row, annual_years=';'.join(map(str, years)), annual_missing_years=';'.join(map(str, missing)),
                           annual_failed_years=';'.join(map(str, failed)), annual_start_year_pass=details[0]['annual_pass'],
                           annual_all_window_years_pass=all_pass, annual_coverage_details_json=json.dumps(details, separators=(',', ':')),
                           provisional_full_and_annual=complete and all_pass,
                           provisional_full_refs_and_annual=complete and references and all_pass, final_sample_eligible=False))
    per_signal = {}
    for signal in SIGNALS:
        rows = [r for r in result if r['signal'] == signal]
        per_signal[signal] = dict(rows=len(rows), annual_pass=sum(r['annual_all_window_years_pass'] for r in rows),
                                  full_and_annual=sum(r['provisional_full_and_annual'] for r in rows),
                                  full_potentialrefs_and_annual=sum(r['provisional_full_refs_and_annual'] for r in rows),
                                  start_vs_all_disagreements=sum(r['annual_start_year_pass'] != r['annual_all_window_years_pass'] for r in rows))
    passing = {s: {r['event_id'] for r in result if r['signal'] == s and r['provisional_full_refs_and_annual']} for s in SIGNALS}
    summary = dict(rows=len(result), per_signal=per_signal,
                   common_events_all_three_signals_provisional=len(set.intersection(*passing.values())),
                   cross_year_events=len({r['event_id'] for r in result if ';' in r['annual_years']}),
                   cross_year_rows=sum(';' in r['annual_years'] for r in result),
                   availability_scope='unmasked_provisional_only', downstream_ready_for_baseline=False,
                   final_sample_eligible=False, masks_applied=[], baseline_computed=False,
                   annual_rule='5 * valid_points >= 4 * expected_points for every calendar year touched by the full right-open event window.',
                   reference_year_annual_eligibility_applied=False,
                   annual_join='annual.country_id = candidate.ioda_iso2, signal, calendar year; candidate boundary country_id is preserved.',
                   missing_year_policy='Missing country/signal/year keys fail qualification; no imputation.',
                   interval_semantics='Explicit UTC 600-second aligned positive right-open windows.')
    return result, summary


def run(quality_dir, candidate_dir, output_dir):
    quality, candidate = Path(quality_dir).resolve(), Path(candidate_dir).resolve()
    output_raw = Path(output_dir).absolute()
    out = output_raw.resolve()
    owned = acquired = False
    lock = out.parent / ('.' + out.name + '.annual-screen.lock')
    common = dict(pid=os.getpid(), started_utc=now(), downstream_ready_for_baseline=False)
    try:
        if output_raw.is_symlink() or any(out == p or out in p.parents or p in out.parents for p in (quality, candidate)):
            raise ValueError('input/output overlap or symlink output')
        if out.exists() and (not out.is_dir() or any(out.iterdir())):
            raise ValueError('output directory must be absent or empty')
        out.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        acquired = True
        with os.fdopen(fd, 'w') as stream:
            stream.write(str(os.getpid()))
        out.mkdir(exist_ok=True)
        if any(out.iterdir()):
            raise ValueError('output directory must be empty')
        owned = True
        atomic(out / 'status.json', json_bytes(dict(common, status='running', updated_utc=now())))
        script = Path(__file__).absolute()
        annuals, fields, events, sources, snapshot, script_hash = read_inputs(quality, candidate, script)
        rows, summary = screen(annuals, fields, events)
        data = io.StringIO(newline='')
        writer = csv.DictWriter(data, fields + ADDED_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        summary.update(common)
        payloads = {'annual_event_screen.csv': data.getvalue().encode(), 'summary.json': json_bytes(summary)}
        check_snapshot(snapshot)
        for name, payload in payloads.items():
            check_snapshot(snapshot)
            atomic(out / name, payload)
        outputs = {name: digest(payload) for name, payload in payloads.items()}
        outputs['annual_event_screen.csv'].update(rows=len(rows), columns=fields + ADDED_FIELDS)
        manifest = dict(common, status='completed', finished_utc=now(), inputs=sources, outputs=outputs,
                        script_sha256=script_hash['sha256'], script=script_hash,
                        hash_scope='Exact source bytes read once and parsed; all upstream manifested files verified. Output data and summary hashed; mutable status and self-referential manifest excluded.')
        check_snapshot(snapshot)
        atomic(out / 'manifest.json', json_bytes(manifest))
        check_snapshot(snapshot)
        atomic(out / 'status.json', json_bytes(dict(common, status='completed', updated_utc=now(), finished_utc=now())))
        return 0
    except Exception as exc:
        if owned:
            atomic(out / 'status.json', json_bytes(dict(common, status='failed', updated_utc=now(), finished_utc=now(), error=str(exc))))
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if acquired:
            lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quality-dir', required=True, type=Path)
    parser.add_argument('--candidate-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    return run(args.quality_dir, args.candidate_dir, args.output_dir)


if __name__ == '__main__':
    sys.exit(main())
