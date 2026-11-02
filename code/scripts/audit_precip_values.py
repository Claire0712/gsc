#!/usr/bin/env python3
"""Bounded read-only precipitation audit; no correction or spatial aggregation."""
import argparse
import calendar
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import tempfile

import h5netcdf
import numpy as np

COUNTS = ('cells', 'finite_positive', 'finite_zero', 'finite_negative', 'nan', 'infinity')
EXTREMA = ('finite_min_m', 'finite_max_m', 'negative_min_m')
GRID_TOLERANCE = 1e-5
# Retain an eight-day spatial chunk slab while callers still read one 2D slice.
HDF5_RAW_CHUNK_CACHE_BYTES = 256 * 1024 * 1024


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def timestamp(seconds):
    return dt.datetime.fromtimestamp(int(seconds), dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def expected_names():
    return [f'precip_{year}_{month:02d}.nc' for year in range(2018, 2026)
            for month in range(1, 13)] + ['precip_2026_01.nc']


def expected_times(name):
    if name not in expected_names():
        raise ValueError(f'Unexpected precipitation filename: {name}')
    year, month = map(int, Path(name).stem.split('_')[1:])
    days = 1 if year == 2026 else calendar.monthrange(year, month)[1]
    start = int(dt.datetime(year, month, 1, tzinfo=dt.timezone.utc).timestamp())
    return start + np.arange(days, dtype=np.int64) * 86400


def empty_statistics():
    return dict.fromkeys(COUNTS, 0) | dict.fromkeys(EXTREMA)


def merge_statistics(total, part):
    for key in COUNTS:
        total[key] += part[key]
    for key in EXTREMA:
        value = part[key]
        if value is not None:
            combine = max if key == 'finite_max_m' else min
            total[key] = value if total[key] is None else combine(total[key], value)


def slice_statistics(values):
    values = np.asarray(values)
    if values.ndim != 2:
        raise ValueError('Expected one two-dimensional time slice')
    finite = np.isfinite(values)
    negative = finite & (values < 0)
    result = {
        'cells': int(values.size),
        'finite_positive': int(np.count_nonzero(finite & (values > 0))),
        'finite_zero': int(np.count_nonzero(finite & (values == 0))),
        'finite_negative': int(np.count_nonzero(negative)),
        'nan': int(np.count_nonzero(np.isnan(values))),
        'infinity': int(np.count_nonzero(np.isinf(values))),
        'finite_min_m': float(values[finite].min()) if finite.any() else None,
        'finite_max_m': float(values[finite].max()) if finite.any() else None,
        'negative_min_m': float(values[negative].min()) if negative.any() else None,
    }
    if sum(result[k] for k in COUNTS[1:]) != result['cells']:
        raise ValueError('Cell categories do not partition the slice')
    return result


def decoded(value):
    return value.decode('utf-8') if isinstance(value, bytes) else value


def check_attr(variable, key, accepted):
    value = decoded(variable.attrs.get(key))
    if value not in accepted:
        raise ValueError(f'{variable.name}: invalid {key}: {value!r}')


def audit_file(path, *, grid=None, progress=None):
    """Read one slice at a time. Explicit grid injection is for small unit fixtures."""
    path = Path(path)
    times = expected_times(path.name)
    if grid is None:
        grid = (90. - np.arange(1801) / 10., np.arange(3600) / 10.)
    with h5netcdf.File(path, 'r', rdcc_nbytes=HDF5_RAW_CHUNK_CACHE_BYTES) as source:
        for name in ('tp', 'valid_time', 'latitude', 'longitude'):
            if name not in source.variables:
                raise ValueError(f'Missing variable {name}: {path}')
        tp = source['tp']
        if tp.dimensions != ('valid_time', 'latitude', 'longitude'):
            raise ValueError(f'Invalid tp dimensions: {tp.dimensions}')
        expected_shape = (len(times), len(grid[0]), len(grid[1]))
        if tp.shape != expected_shape:
            raise ValueError(f'Invalid tp shape: {tp.shape}; expected {expected_shape}')
        if tp.dtype.kind not in 'fi':
            raise ValueError(f'Invalid tp numeric dtype: {tp.dtype}')
        for key, allowed in [('units', ('m',)), ('GRIB_stepType', ('accum',)), ('GRIB_dataType', ('fc',))]:
            check_attr(tp, key, allowed)
        for key in ('scale_factor', 'add_offset'):
            if key in tp.attrs:
                raise ValueError(f'Forbidden tp attribute: {key}')
        if '_FillValue' in tp.attrs:
            fill = np.asarray(tp.attrs['_FillValue'])
            if fill.size != 1 or not np.isnan(fill).all():
                raise ValueError('tp _FillValue must be NaN when provided')
        for name, expected in zip(('latitude', 'longitude'), grid):
            coordinate = source[name]
            if coordinate.dimensions != (name,) or coordinate.shape != expected.shape:
                raise ValueError(f'Invalid {name} coordinate shape/dimensions')
            if not np.allclose(coordinate[:], expected, atol=GRID_TOLERANCE, rtol=0):
                raise ValueError(f'Invalid {name} grid')
        time = source['valid_time']
        check_attr(time, 'units', ('seconds since 1970-01-01', 'seconds since 1970-01-01 00:00:00', 'seconds since 1970-01-01T00:00:00'))
        check_attr(time, 'calendar', ('gregorian', 'proleptic_gregorian', 'standard'))
        if time.dimensions != ('valid_time',) or time.shape != times.shape or not np.array_equal(time[:], times):
            raise ValueError(f'Invalid valid_time dates for {path.name}')
        total = empty_statistics()
        daily = []
        for index, seconds in enumerate(times):
            stats = slice_statistics(tp[index, :, :])
            merge_statistics(total, stats)
            daily.append({'valid_time': timestamp(seconds), **stats})
            if progress:
                progress(index + 1, timestamp(seconds))
    return {'file': path.name, 'days': len(times), 'time_start': timestamp(times[0]),
            'time_end': timestamp(times[-1]), 'counts': total, 'daily': daily}


def snapshot(path):
    stat = path.stat()
    return {key: getattr(stat, key) for key in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')}


def assert_unchanged(path, before):
    if snapshot(path) != before:
        raise ValueError(f'Source changed during audit: {path}')


def fingerprint(path):
    before = snapshot(path)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    assert_unchanged(path, before)
    return {'path': str(path.resolve()), 'sha256': digest.hexdigest(),
            'bytes': before['st_size'], 'stat': before}


def atomic_json(path, data):
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_manifest(source):
    actual = {p.name for p in source.glob('precip_*.nc')}
    expected = set(expected_names())
    if actual != expected:
        raise ValueError(f'Invalid input manifest: missing={sorted(expected-actual)}, extra={sorted(actual-expected)}')
    for name in expected:
        if not (source / name).is_file():
            raise ValueError(f'Input is not a file: {source / name}')


def run_audit(input_dir, output_dir, *, grid=None):
    source, output = Path(input_dir).resolve(), Path(output_dir).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError('Input/output directories must not overlap')
    if not source.is_dir():
        raise ValueError('Input directory does not exist')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Output must be absent or empty; refusing overwrite')
    output.mkdir(parents=True, exist_ok=True)
    # Exclusive ownership also rejects concurrent jobs using the same empty stage.
    with (output / 'audit.lock').open('x') as lock:
        lock.write(str(os.getpid()) + '\n')
    status = {'status': 'running', 'pid': os.getpid(), 'started_at': utc_now(),
              'files_completed': 0, 'days_completed': 0, 'files_hashed': 0,
              'baseline_computed': False, 'country_aggregation_computed': False,
              'files_expected': 97, 'days_expected': 2923, 'phase': 'hashing'}
    def publish_status(**updates):
        status.update(updates)
        status['updated_at'] = utc_now()
        atomic_json(output / 'status.json', status)
    publish_status()
    try:
        script_path = Path(__file__).resolve()
        script = fingerprint(script_path)
        validate_manifest(source)
        records = []
        for name in expected_names():
            publish_status(current_file=name)
            records.append(fingerprint(source / name))
            publish_status(files_hashed=len(records))
        manifest = {'created_at': utc_now(), 'input_dir': str(source), 'script': script,
                    'hdf5_raw_chunk_cache_bytes': HDF5_RAW_CHUNK_CACHE_BYTES,
                    'grid_atol_degrees': GRID_TOLERANCE, 'grid_rtol': 0,
                    'grid_shape': [len(x) for x in grid] if grid is not None else [1801, 3600],
                    'sources': records}
        atomic_json(output / 'manifest.json', manifest)
        (output / 'monthly').mkdir()
        total = empty_statistics()
        days = 0
        publish_status(phase='scanning')
        for index, record in enumerate(records):
            path = source / expected_names()[index]
            assert_unchanged(path, record['stat'])
            publish_status(current_file=path.name, current_file_days_completed=0)
            def progress(count, time):
                publish_status(current_file_days_completed=count, days_completed=days + count, current_time=time)
            result = audit_file(path, grid=grid, progress=progress)
            assert_unchanged(path, record['stat'])
            result.update(sha256=record['sha256'], bytes=record['bytes'], source_path=record['path'])
            atomic_json(output / 'monthly' / (path.stem + '.json'), result)
            days += result['days']
            merge_statistics(total, result['counts'])
            publish_status(files_completed=index + 1, days_completed=days)
        if len(records) != 97 or days != 2923:
            raise ValueError('Final file/day totals do not match bounded audit')
        validate_manifest(source)
        for record, name in zip(records, expected_names()):
            assert_unchanged(source / name, record['stat'])
        assert_unchanged(script_path, script['stat'])
        summary = {'files': len(records), 'days': days, 'counts': total,
                   'baseline_computed': False, 'country_aggregation_computed': False,
                   'time_start': timestamp(expected_times(expected_names()[0])[0]),
                   'time_end': timestamp(expected_times(expected_names()[-1])[-1]),
                   'completed_at': utc_now(), 'script_sha256': script['sha256'],
                   'interpretation': 'Raw values retained: zero is valid; negatives, NaN and infinity are diagnostics. No date relabeling, exclusion, clipping, imputation or aggregation.'}
        atomic_json(output / 'summary.json', summary)
        output_records = []
        for path in sorted((output / 'monthly').glob('*.json')) + [output / 'summary.json']:
            record = fingerprint(path)
            output_records.append({'path': str(path.relative_to(output)),
                                   'sha256': record['sha256'], 'bytes': record['bytes']})
        atomic_json(output / 'output_manifest.json', {'outputs': output_records})
        # Completion is the commit marker: recheck provenance after output publication.
        validate_manifest(source)
        for record, name in zip(records, expected_names()):
            assert_unchanged(source / name, record['stat'])
        assert_unchanged(script_path, script['stat'])
        publish_status(status='completed', phase='completed', completed_at=summary['completed_at'])
        return summary
    except BaseException as error:
        publish_status(status='failed', phase='failed', failed_at=utc_now(), error=f'{type(error).__name__}: {error}')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    run_audit(args.input_dir, args.output_dir)


if __name__ == '__main__':
    main()
