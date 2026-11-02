"""Check completed CMIP6 files against their requested variables, dates and grid."""
import datetime as dt
import json
from pathlib import Path
import sys
import os
import time
import fcntl
import h5netcdf
import cftime
import numpy as np
from server_fetch import atomic_json, now


def string(value):
    return value.decode() if isinstance(value, bytes) else str(value)


def validate_title(title, task):
    fields = [field.strip() for field in title.split(',')]
    assert len(fields) >= 3, 'incomplete model/scenario title'
    assert fields[0].casefold() == task['model'].casefold(), 'wrong model'
    assert fields[1] == task['member'], 'wrong title member'
    assert fields[2] == task['experiment'], 'wrong scenario'


def decode_times(values, units, calendar):
    return cftime.num2date(values, units=units, calendar=calendar,
                          only_use_cftime_datetimes=False, only_use_python_datetimes=False)


def validate_year(times, units, cal, year):
    assert cal in ['standard', 'gregorian', 'proleptic_gregorian',
                   'noleap', '365_day', 'all_leap', '366_day', '360_day'], 'unsupported calendar'
    start = cftime.datetime(year, 1, 1, calendar=cal)
    next_year = cftime.datetime(year + 1, 1, 1, calendar=cal)
    assert len(times) == (next_year - start).days, 'wrong day count for declared calendar'
    assert np.allclose(np.diff(times), 1), 'non-daily or missing dates'
    first, last = decode_times(np.asarray(times)[[0, -1]], units, cal)
    end = next_year - dt.timedelta(days=1)
    assert (first.year, first.month, first.day) == (year, 1, 1), 'wrong first date'
    assert (last.year, last.month, last.day) == (end.year, end.month, end.day), 'wrong last date'
    return first, last


def inspect(path, task):
    with h5netcdf.File(path, 'r') as ds:
        v = ds.variables[task['variable']]
        assert v.dimensions == ('time', 'lat', 'lon'), 'unexpected variable dimensions'
        assert string(v.attrs['units']) == 'K', 'unexpected temperature units'
        assert string(ds.attrs['variant_label']) == task['member'], 'wrong model member'
        assert string(ds.attrs['version']) == task['version'], 'wrong data version'
        title = string(ds.attrs['title'])
        validate_title(title, task)
        lat, lon = ds.variables['lat'][:], ds.variables['lon'][:]
        assert len(lat) == 600 and len(lon) == 1440, 'unexpected grid size'
        assert np.allclose(lat, -59.875 + np.arange(600)*0.25), 'wrong latitude grid'
        assert np.allclose(lon, 0.125 + np.arange(1440)*0.25), 'wrong longitude grid'
        tv = ds.variables['time']
        cal = string(tv.attrs.get('calendar', 'standard'))
        units = string(tv.attrs['units'])
        assert units.startswith('days since '), 'unexpected time units'
        times = np.asarray(tv[:], dtype=float)
        first, last = validate_year(times, units, cal, task['year'])
        # Read two land cells at both ends of the year, exercising actual data chunks.
        sample = np.array([float(v[t, y, x]) for t in [0, len(times)-1]
                           for y, x in [(400, 1000), (400, 400)]])
        finite = sample[np.isfinite(sample) & (sample < 1e10)]
        assert finite.size and np.all((finite > 100) & (finite < 400)), 'invalid land-cell temperature sample'
        return {'dimensions': {k: len(d) for k, d in ds.dimensions.items()},
                'variable': task['variable'], 'units': 'K', 'calendar': cal,
                'first_date': first.isoformat(), 'last_date': last.isoformat(),
                'sample_temperature_K': finite.tolist()}


def main():
    root = Path(sys.argv[1]).resolve()
    tasks = json.loads(Path(sys.argv[2]).read_text())['tasks']
    records = root / 'metadata/full_download_v2/records'
    target = root / 'metadata/full_download_v2/content_checks'
    target.mkdir(parents=True, exist_ok=True)
    passed, failed, pending = [], [], []
    for task in tasks:
        p = records / (task['id'] + '.json')
        if not p.exists():
            pending.append(task['id']); continue
        record = json.loads(p.read_text())
        if record.get('status') not in ['downloaded_verified', 'existing_verified']:
            pending.append(task['id']); continue
        file = root / record['file']
        output = target / (task['id'] + '.json')
        stat = file.stat()
        old = json.loads(output.read_text()) if output.exists() else {}
        if old.get('passed') and old.get('transport_sha256') == record['sha256'] and old.get('mtime_ns') == stat.st_mtime_ns:
            passed.append(task['id']); continue
        result = {'id': task['id'], 'checked_utc': now(), 'transport_sha256': record['sha256'],
                  'mtime_ns': stat.st_mtime_ns, 'bytes': stat.st_size,
                  'scope': 'All coordinate values and dates, requested variable/model/member/version, four temperature data cells; not exhaustive climate-value QA'}
        try:
            assert stat.st_size == record['bytes'], 'size changed after transport validation'
            result.update(passed=True, content=inspect(file, task))
            passed.append(task['id'])
        except Exception as error:
            result.update(passed=False, error_type=type(error).__name__, message=str(error))
            failed.append(task['id'])
        atomic_json(output, result)
    report = {'checked_utc': now(), 'planned': len(tasks), 'passed': len(passed),
              'failed_ids': failed, 'pending': len(pending), 'all_complete_and_passed': len(passed) == len(tasks)}
    atomic_json(target / 'cmip6_summary.json', report)
    print(json.dumps(report), flush=True)
    return report


if __name__ == '__main__':
    if '--watch' in sys.argv[3:]:
        root = Path(sys.argv[1]).resolve()
        meta = root / 'metadata/full_download_v2'
        with (meta / 'cmip6_content_worker.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            atomic_json(meta / 'cmip6_content_worker.json', {'pid': os.getpid(), 'started_utc': now()})
            while True:
                report = main()
                progress = json.loads((meta / 'cmip6_progress.json').read_text())
                if report['all_complete_and_passed'] or progress.get('worker_finished'):
                    break
                time.sleep(120)
    else:
        main()
