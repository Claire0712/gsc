#!/usr/bin/env python3
"""Run a fail-stop, single-worker pipeline over existing Judy data only."""
import argparse
import calendar
import csv
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def run_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'run.lock').open('a+') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Another coordinator holds this run lock') from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def write_status(root, state):
    state['updated_utc'] = utc_now()
    temp = root / 'status.json.tmp'
    temp.write_text(json.dumps(state, indent=2) + '\n')
    temp.replace(root / 'status.json')


def validate_pilot(directory, month):
    directory = Path(directory)
    audit = json.loads((directory / f'era5_country_daily_{month}.audit.json').read_text())
    with (directory / f'era5_country_daily_{month}.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    days = calendar.monthrange(int(month[:4]), int(month[4:]))[1]
    if audit['missing_hour_count'] != 0 or audit['day_count'] != days:
        raise ValueError('Pilot month lacks complete UTC hourly coverage')
    if len(rows) != audit['rows'] or len(rows) != days * audit['country_count']:
        raise ValueError('Pilot row count mismatch')
    keys = {(r['country_id'], r['date']) for r in rows}
    if len(keys) != len(rows):
        raise ValueError('Duplicate pilot country-days')
    countries = {r['country_id'] for r in rows}
    expected = {(c, f'{month[:4]}-{month[4:]}-{d:02d}') for c in countries for d in range(1, days + 1)}
    if keys != expected:
        raise ValueError('Pilot date coverage mismatch')
    positive = [r for r in rows if float(r['total_population']) > 0]
    if not positive:
        raise ValueError('No populated units in the pilot output')
    for row in positive:
        low, high, dew = (float(row[key]) for key in ['tmin_c', 'tmax_c', 'dewpoint_c'])
        if not all(math.isfinite(x) for x in (low, high, dew)):
            raise ValueError('Missing metric in a populated pilot unit: ' + repr(row))
        if not (-100 <= low <= high <= 80 and -120 <= dew <= high + 0.5):
            raise ValueError('Inconsistent pilot temperature/dewpoint range: ' + repr(row))
        if int(row['hours_present']) != 24 or float(row['pop_valid_fraction']) < 1 - 1e-9:
            raise ValueError('Incomplete population/hour coverage in pilot: ' + repr(row))
    summary = {'state': 'passed', 'month': month, 'rows': len(rows),
               'populated_country_count': len({r['country_id'] for r in positive}), 'checked_utc': utc_now()}
    (directory / f'pilot_gate_{month}.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)
    return summary


def execute_steps(root, steps, heartbeat=30.0):
    root = Path(root)
    with run_lock(root):
        state = {'state': 'running', 'pid': os.getpid(), 'started_utc': utc_now(),
                 'completed_stages': [], 'stage': None, 'child_pid': None}
        write_status(root, state)
        child = None
        try:
            for name, command in steps:
                state.update(stage=name, command=command, child_pid=None,
                             stage_started_utc=utc_now())
                print(json.dumps({'stage': name, 'command': command, 'utc': utc_now()}), flush=True)
                write_status(root, state)
                child = subprocess.Popen(command)
                state['child_pid'] = child.pid
                write_status(root, state)
                while True:
                    try:
                        code = child.wait(timeout=heartbeat)
                        break
                    except subprocess.TimeoutExpired:
                        write_status(root, state)
                state.update(child_pid=None, exit_code=code)
                if code != 0:
                    state['state'] = 'failed'
                    write_status(root, state)
                    print(json.dumps(state), flush=True)
                    return code if code > 0 else 1
                state['completed_stages'].append(name)
                write_status(root, state)
            state.update(state='complete', finished_utc=utc_now())
            write_status(root, state)
            print(json.dumps(state), flush=True)
            return 0
        except BaseException as exc:
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            state.update(state='failed', child_pid=None, error=repr(exc))
            write_status(root, state)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True, type=Path)
    parser.add_argument('--steps-json', type=Path)
    parser.add_argument('--validate-pilot', metavar='YYYYMM')
    parser.add_argument('--country-daily', type=Path)
    parser.add_argument('--heartbeat', default=30.0, type=float)
    args = parser.parse_args()
    if args.validate_pilot:
        if args.country_daily is None:
            parser.error('--country-daily is required for pilot validation')
        validate_pilot(args.country_daily, args.validate_pilot)
        return 0
    if args.steps_json is None:
        parser.error('--steps-json is required for pipeline execution')
    raw = json.loads(args.steps_json.read_text())
    if not isinstance(raw, list) or not raw:
        parser.error('steps-json must be a nonempty list')
    steps = []
    names = set()
    for item in raw:
        name, command = item['name'], item['command']
        if not isinstance(name, str) or name in names:
            parser.error('Stage names must be unique strings')
        if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
            parser.error('Each command must be a nonempty list of strings')
        names.add(name)
        steps.append((name, command))
    if args.heartbeat <= 0:
        parser.error('heartbeat must be positive')
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
        os.environ[key] = '1'
    return execute_steps(args.run_dir, steps, args.heartbeat)


if __name__ == '__main__':
    sys.exit(main())
