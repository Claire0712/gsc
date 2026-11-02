"""Verify downloaded CDS artifacts against exact requested dates, fields and statistics."""
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import sys
import time
import zipfile
import h5netcdf
import numpy as np
from server_fetch import atomic_json, now

FIELDS = {'2m_temperature': ('t2m', 'K'), '2m_dewpoint_temperature': ('d2m', 'K'),
          '10m_u_component_of_wind': ('u10', 'm s**-1'),
          '10m_v_component_of_wind': ('v10', 'm s**-1'), 'total_precipitation': ('tp', 'm')}


def text(v):
    return v.decode() if isinstance(v, bytes) else str(v)


def expected_dates(task):
    req = task['request']
    hours = req.get('time', ['00:00'])
    return [dt.datetime(int(req['year']), int(m), int(d), int(t[:2]), int(t[3:5]))
            for m in req['month'] for d in req['day'] for t in hours]


def inspect_dataset(ds, task):
    req = task['request']
    lat, lon = ds.variables['latitude'][:], ds.variables['longitude'][:]
    assert len(lat) == 1801 and len(lon) == 3600, 'wrong grid size'
    assert np.allclose(lat, 90 - np.arange(1801)*.1, atol=1e-5), 'wrong latitude grid'
    assert np.allclose(lon, np.arange(3600)*.1, atol=1e-5), 'wrong longitude grid'
    tv = ds.variables['valid_time']
    units = text(tv.attrs['units'])
    unit, origin = units.split(' since ', 1)
    factor = {'days': 86400, 'hours': 3600, 'seconds': 1}[unit]
    assert text(tv.attrs.get('calendar', 'standard')) in ['standard', 'gregorian', 'proleptic_gregorian']
    origin = dt.datetime.fromisoformat(origin)
    dates = [origin + dt.timedelta(seconds=float(v)*factor) for v in tv[:]]
    assert dates == expected_dates(task), 'dates differ from exact request'
    expected = dict(FIELDS[v] for v in req['variable'])
    found = {}
    for name, v in ds.variables.items():
        if 'latitude' not in v.dimensions or 'longitude' not in v.dimensions:
            continue
        assert name in expected, 'unexpected spatial variable: ' + name
        assert v.dimensions == ('valid_time', 'latitude', 'longitude'), 'wrong field dimensions'
        assert text(v.attrs['units']) == expected[name], 'wrong field units'
        found[name] = {'units': expected[name], 'shape': list(v.shape)}
    assert found, 'no requested weather fields'
    history = text(ds.attrs.get('history', ''))
    if 'daily_statistic' in req:
        operation = {'daily_mean': 'mean', 'daily_minimum': 'min', 'daily_maximum': 'max'}[req['daily_statistic']]
        assert 'daily_reduce(' in history and 'how=' + operation in history, 'wrong daily statistic history'
        assert text(tv.attrs.get('time_shift', '')) == '0 days 00:00:00', 'wrong day boundary'
    if task['kind'] == 'precip':
        assert text(ds.variables['tp'].attrs['GRIB_stepType']) == 'accum', 'precipitation is not accumulation'
    return {'fields': found, 'first_time': dates[0].isoformat(), 'last_time': dates[-1].isoformat(),
            'time_count': len(dates), 'history': history}


def inspect_file(path, task):
    members = []
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.lower().endswith('.nc'):
                    with z.open(name) as f:
                        with h5netcdf.File(f, 'r') as ds:
                            members.append(dict(member=name, **inspect_dataset(ds, task)))
    else:
        with h5netcdf.File(path, 'r') as ds:
            members.append(inspect_dataset(ds, task))
    names = [n for member in members for n in member['fields']]
    assert len(names) == len(set(names)), 'duplicate spatial variables'
    assert set(names) == {FIELDS[v][0] for v in task['request']['variable']}, 'missing requested variables'
    return members


def run(root, plan):
    records = root / 'metadata/full_download_v2/records'
    target = root / 'metadata/full_download_v2/content_checks'
    target.mkdir(parents=True, exist_ok=True)
    passed, failed, pending = [], [], []
    for task in plan:
        p = records / (task['id'] + '.json')
        r = json.loads(p.read_text()) if p.exists() else {}
        if r.get('status') not in ['downloaded_verified', 'existing_verified']:
            pending.append(task['id']); continue
        source = root / r['file']; st = source.stat()
        out = target / (task['id'] + '.json')
        old = json.loads(out.read_text()) if out.exists() else {}
        if old.get('passed') and old.get('transport_sha256') == r['sha256'] and old.get('mtime_ns') == st.st_mtime_ns:
            passed.append(task['id']); continue
        result = {'id': task['id'], 'checked_utc': now(), 'transport_sha256': r['sha256'],
                  'mtime_ns': st.st_mtime_ns, 'scope': 'Exact requested dates, full coordinate arrays, field names/units/dimensions, daily statistic and UTC boundary metadata; not exhaustive value-level QA'}
        try:
            assert st.st_size == r['bytes'], 'file size changed'
            result.update(passed=True, members=inspect_file(source, task))
            passed.append(task['id'])
        except Exception as e:
            result.update(passed=False, error_type=type(e).__name__, message=str(e))
            failed.append(task['id'])
        atomic_json(out, result)
    report = {'checked_utc': now(), 'planned': len(plan), 'passed': len(passed),
              'failed_ids': failed, 'pending': len(pending), 'all_complete_and_passed': len(passed) == len(plan)}
    atomic_json(target / 'cds_summary.json', report)
    print(json.dumps(report), flush=True)
    return report


if __name__ == '__main__':
    root = Path(sys.argv[1]).resolve(); plan_path = Path(sys.argv[2])
    with (root / 'metadata/full_download_v2/cds_content_worker.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        atomic_json(root / 'metadata/full_download_v2/cds_content_worker.json', {'pid': os.getpid(), 'started_utc': now()})
        while True:
            report = run(root, json.loads(plan_path.read_text()))
            if '--watch' not in sys.argv[3:] or report['all_complete_and_passed']:
                break
            time.sleep(180)
