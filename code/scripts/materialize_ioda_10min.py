#!/usr/bin/env python3
"""Materialize audited IODA observations; no baseline or resilience inference."""
import argparse
from contextlib import contextmanager
import csv
import fcntl
import gzip
import json
import os
from pathlib import Path
import re
import tempfile
import numpy as np
import prepare_ioda_quality as qa


@contextmanager
def run_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'run.lock').open('a+') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Another materializer holds this output lock') from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def parse_quarter(value):
    if not re.fullmatch(r'202[2-5]Q[1-4]', value):
        raise ValueError('Quarter must be 2022Q1 through 2025Q4')
    return int(value[:4]), int(value[-1])


def ten_minute_values(grid, signal):
    if signal not in qa.CADENCES:
        raise ValueError('Unknown signal')
    if len(grid.phases) > 1:
        raise ValueError('Incompatible native phases cannot be materialized')
    phase = next(iter(grid.phases)) if grid.phases else -1
    values = np.full(grid.expected, np.nan, dtype=np.float64)
    if grid.values is not None:
        valid = (grid.counts > 0) & ((grid.flags & grid.CONFLICT) == 0)
        values[valid] = grid.values[valid]
    if qa.CADENCES[signal] == 600:
        return values, phase
    if len(values) % 2:
        raise ValueError('5-minute series lacks an even quarter lattice')
    pair = values.reshape(-1, 2)
    complete = np.isfinite(pair).all(axis=1)
    result = np.full(len(pair), np.nan)
    # Half first, avoiding overflow in an intermediate sum.
    result[complete] = pair[complete, 0] / 2 + pair[complete, 1] / 2
    return result, phase


def write_archive(path, values, country_ids, phases, times, provenance):
    path = Path(path)
    if values.shape != (len(country_ids), len(times)) or len(phases) != len(country_ids):
        raise ValueError('Archive dimensions are inconsistent')
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            np.savez_compressed(handle, values=values, country_ids=np.asarray(country_ids, dtype='U2'),
                                native_phase_seconds=np.asarray(phases, dtype=np.int16),
                                interval_start_utc=np.asarray(times, dtype=np.int64))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    audit = {'state': 'complete', 'updated_utc': qa.now(), 'provenance': provenance,
             'shape': list(values.shape), 'valid_points': int(np.isfinite(values).sum()),
             'zero_points': int(np.count_nonzero(values == 0)), 'output': qa.fingerprint(path),
             'time_definition': 'UTC left-closed right-open 600-second intervals; labels are interval starts, not asserted measurement times',
             'native_phase_definition': 'Seconds after each native 300/600-second lattice start; -1 means no series phase was observed',
             'aggregation': 'AP native observation; BGP/Telescope arithmetic mean of two complete valid native slots'}
    qa.atomic_json(path.with_suffix('.audit.json'), audit)
    return audit


def valid_archive(path, provenance):
    try:
        audit = json.loads(path.with_suffix('.audit.json').read_text())
        return (audit['state'] == 'complete' and audit['provenance'] == provenance
                and audit['output'] == qa.fingerprint(path))
    except (OSError, ValueError, KeyError):
        return False


def load_qa(directory):
    summary = json.loads((directory / 'summary.json').read_text())
    if summary.get('state') != 'completed' or summary.get('quality_pass') is not True:
        raise ValueError('A completed clean IODA audit is required')
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest.get('state') != 'completed' or manifest.get('errors'):
        raise ValueError('IODA manifest reports incomplete audit or errors')
    for output in manifest['outputs']:
        name = output['file']
        if Path(name).name != name:
            raise ValueError('Invalid QA output path')
        if qa.fingerprint(directory / name) != {k: output[k] for k in ('bytes', 'sha256')}:
            raise ValueError('QA output hash mismatch: ' + name)
    if manifest.get('script_sha256') != qa.fingerprint(Path(qa.__file__))['sha256']:
        raise ValueError('QA code differs from the completed audited version')
    return manifest


def discover(data_root, manifest):
    records, countries = [], set()
    seen = set()
    for entry in manifest['files']:
        if not entry.get('passed'):
            raise ValueError('QA manifest contains a failed source')
        metadata = (data_root / entry['metadata']).resolve()
        allowed = [(data_root / 'ioda' / c).resolve() for c in qa.COLLECTIONS]
        if not any(parent in metadata.parents for parent in allowed):
            raise ValueError('Metadata path outside raw collections')
        record = qa._metadata(data_root, metadata)
        if record is None or record['file'] != entry['file']:
            raise ValueError('Manifest/source identity mismatch')
        if record['sha256'].lower() != entry['sha256'].lower() or record['bytes'] != entry['bytes']:
            raise ValueError('Source metadata differs from completed audit')
        if entry['metadata'] in seen:
            raise ValueError('Duplicate metadata in audit manifest')
        seen.add(entry['metadata'])
        record['_metadata_hash'] = qa.fingerprint(metadata)['sha256']
        records.append(record)
        countries.update(record['countries'])
    return records, sorted(countries)


def ingest(record, accumulator):
    path = record['_payload']
    expected = {'bytes': record['bytes'], 'sha256': record['sha256'].lower()}
    if qa.fingerprint(path) != expected:
        raise ValueError('Raw source hash mismatch: ' + record['file'])
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        raw = json.load(handle)
    request = raw.get('requestParameters', {})
    if raw.get('error') or request.get('from') != accumulator.start or request.get('until') != accumulator.until:
        raise ValueError('Response is not the expected complete quarter request')
    groups = raw.get('data')
    if not isinstance(groups, list) or any(not isinstance(g, list) for g in groups):
        raise ValueError('Malformed raw response')
    for group in groups:
        for series in group:
            if not isinstance(series, dict):
                raise ValueError('Malformed series')
            if series.get('datasource') not in qa.CADENCES:
                continue
            if series.get('entityCode') not in record['countries']:
                raise ValueError('Country mismatch')
            if record.get('datasource') and series['datasource'] != record['datasource']:
                raise ValueError('Signal mismatch')
            accumulator.add(series)


def materialize(data_root, qa_dir, output_dir, quarters, resume=False):
    root, qa_dir, out = map(lambda p: Path(p).resolve(), (data_root, qa_dir, output_dir))
    if out == root or root in out.parents or out == qa_dir or qa_dir in out.parents:
        raise ValueError('Output must not overlap raw data or completed QA directory')
    with run_lock(out):
        status = {'state': 'running', 'pid': os.getpid(), 'started_utc': qa.now(),
                  'quarters_requested': quarters, 'completed_quarters': [], 'processed_files': 0,
                  'stage': 'validate_qa', 'result_type': 'observed_connection_inputs_not_resilience'}
        def progress():
            status['updated_utc'] = qa.now()
            qa.atomic_json(out / 'status.json', status)
            print(json.dumps({k: status.get(k) for k in ('state', 'stage', 'current_quarter', 'processed_files', 'updated_utc')}), flush=True)
        progress()
        qa.atomic_json(out / 'manifest.json', {'state': 'running', 'pid': os.getpid(),
                       'started_utc': status['started_utc'], 'quarters': quarters, 'outputs': []})
        try:
            manifest = load_qa(qa_dir)
            records, countries = discover(root, manifest)
            with (qa_dir / 'coverage_quarterly.csv').open() as handle:
                coverage = {(r['country_id'], int(r['year']), int(r['quarter']), r['signal']): r for r in csv.DictReader(handle)}
            common = {'schema_version': 1, 'script_sha256': qa.fingerprint(Path(__file__))['sha256'],
                      'qa_script_sha256': manifest['script_sha256'],
                      'qa_manifest_sha256': qa.fingerprint(qa_dir / 'manifest.json')['sha256']}
            produced = []
            phase_history = {}
            for label in quarters:
                year, quarter = parse_quarter(label)
                selected = [r for r in records if r['year'] == year and r['quarter'] == quarter]
                if not selected:
                    raise ValueError('No audited input files for ' + label)
                prov = {**common, 'quarter': label, 'countries': countries,
                        'inputs': [{'file': r['file'], 'sha256': r['sha256'], 'metadata_sha256': r['_metadata_hash']} for r in selected]}
                paths = {s: out / f'ioda_{label}_{s}.npz' for s in qa.CADENCES}
                status.update(stage='read_native', current_quarter=label)
                progress()
                if resume and all(valid_archive(path, {**prov, 'signal': s}) for s, path in paths.items()):
                    for record in selected:
                        if qa.fingerprint(record['_payload']) != {'bytes': record['bytes'], 'sha256': record['sha256'].lower()}:
                            raise ValueError('Raw source hash mismatch during resume: ' + record['file'])
                    for signal, path in paths.items():
                        with np.load(path, allow_pickle=False) as archive:
                            for country, phase in zip(archive['country_ids'], archive['native_phase_seconds']):
                                if phase >= 0:
                                    phase_history.setdefault(str(country) + '/' + signal, set()).add(int(phase))
                        produced.append({'file': path.name, **qa.fingerprint(path)})
                    status['completed_quarters'].append(label)
                    progress()
                    continue
                accumulator = qa.QuarterAccumulator(year, quarter)
                for record in selected:
                    ingest(record, accumulator)
                    status['processed_files'] += 1
                    progress()
                times = np.arange(accumulator.start, accumulator.until, 600, dtype=np.int64)
                for signal in qa.CADENCES:
                    status.update(stage='write_10min', current_signal=signal)
                    progress()
                    matrix = np.full((len(countries), len(times)), np.nan)
                    phases = np.full(len(countries), -1, dtype=np.int16)
                    for i, country in enumerate(countries):
                        grid = accumulator.grids.get((country, signal), qa.SignalGrid((accumulator.until-accumulator.start)//qa.CADENCES[signal]))
                        stats = grid.statistics()
                        reference = coverage[(country, year, quarter, signal)]
                        for key in ('valid_points', 'zero_points', 'conflict_points', 'expected_points'):
                            if stats[key] != int(reference[key]):
                                raise ValueError(f'Independent QA count mismatch: {label}/{country}/{signal}/{key}')
                        matrix[i], phases[i] = ten_minute_values(grid, signal)
                        if phases[i] >= 0:
                            phase_history.setdefault(country + '/' + signal, set()).add(int(phases[i]))
                    path = paths[signal]
                    write_archive(path, matrix, countries, phases, times, {**prov, 'signal': signal})
                    if not valid_archive(path, {**prov, 'signal': signal}):
                        raise ValueError('Written archive did not pass hash validation')
                    produced.append({'file': path.name, **qa.fingerprint(path)})
                    del matrix
                del accumulator
                status['completed_quarters'].append(label)
                progress()
            status.update(state='complete', stage='complete', finished_utc=qa.now(),
                          output_archives=len(produced), phase_changes={k: sorted(v) for k, v in phase_history.items() if len(v)>1},
                          downstream_ready_for_baseline=False,
                          next_gate='Exact spatial crosswalk, heat/STOP/cyclone/measurement exclusion masks and phase consistency review required before baseline calculation')
            qa.atomic_json(out / 'manifest.json', {**common, 'state': 'complete', 'outputs': produced,
                           'quarters': quarters, 'notes': ['Interval labels do not assert observations occur on exact clock boundaries.',
                           'Every native finite count reconciled to the completed QA quarterly table.',
                           'No interpolation, missing-to-zero conversion, baseline or resilience estimates.']})
            progress()
            return status
        except BaseException as exc:
            status.update(state='failed', error=repr(exc))
            qa.atomic_json(out / 'manifest.json', {'state': 'failed', 'pid': os.getpid(),
                           'updated_utc': qa.now(), 'quarters': quarters, 'outputs': [], 'error': repr(exc)})
            progress()
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--qa-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--quarters', nargs='+', default=[f'{y}Q{q}' for y in qa.YEARS for q in range(1,5)])
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    for value in args.quarters:
        parse_quarter(value)
    if len(set(args.quarters)) != len(args.quarters):
        parser.error('Duplicate quarters')
    materialize(args.data_root, args.qa_dir, args.output_dir, args.quarters, args.resume)


if __name__ == '__main__':
    main()
