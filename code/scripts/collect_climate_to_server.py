"""Bounded CDS jobs on Mac; bulk artifacts download directly on the user's NAS.

The existing local CDS credential is never copied to the server. No source files
or successful jobs are deleted. Pending jobs retain their IDs on polling errors.
"""
import argparse
import collections
import concurrent.futures
import datetime as dt
import fcntl
import json
import logging
import os
from pathlib import Path
import subprocess
import threading
import time
import cdsapi

BASE = Path(__file__).resolve().parents[1] / 'downloads'
STATE = BASE / 'state'
DATA_ROOT = '/volume1/homes/Judy/GSC2027/HeatSignal/data'
FETCHER = '/volume1/homes/Judy/GSC2027/HeatSignal/downloads_v2/scripts/server_fetch.py'
SSH = ['ssh', '-S', '/private/tmp/heatsignal-work.sock', '-o', 'BatchMode=yes',
       '-o', 'ConnectTimeout=15', '-p', '1214', 'Judy@100.107.238.58']
STOP_SUBMISSION = threading.Event()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path, value):
    temp = path.with_name(path.name + '.tmp.' + str(threading.get_ident()))
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def status_code(error):
    return getattr(getattr(error, 'response', None), 'status_code', None)


def log(key, event):
    print(json.dumps({'time': now(), 'task': key, 'event': event}), flush=True)


def client():
    c = cdsapi.Client(quiet=True, progress=False, timeout=40, retry_max=1, wait_until_complete=False)
    c.client.session.trust_env = False
    return c


def sync_remote_completions():
    code = "import json;from pathlib import Path; p=Path('" + DATA_ROOT + "/metadata/full_download_v2/records'); print(json.dumps([json.loads(f.read_text()) for f in p.glob('*.json')]))"
    import shlex
    done = subprocess.run(SSH + ['python3 -c ' + shlex.quote(code)], capture_output=True, text=True, timeout=60)
    if done.returncode:
        raise RuntimeError('SSH unavailable; do not submit work without confirmed destination')
    for record in json.loads(done.stdout):
        if record.get('status') in ['downloaded_verified', 'existing_verified']:
            p = STATE / (record['id'] + '.json')
            old = json.loads(p.read_text()) if p.exists() else {}
            old.update(status='downloaded_verified', raw_archive=record, checked_utc=now())
            save(p, old)


def transfer(task, job_id, result, state, path):
    kind = task['kind']
    group = 'era5_land' if kind in ['tmin', 'tmax', 'hourly_temperature'] else 'weather_controls'
    folder = 'raw_hourly' if kind == 'hourly_temperature' else 'raw_monthly'
    payload = {'id': task['id'], 'job_id': job_id, 'task': task,
               'url': result.location, 'bytes': result.content_length,
               'target_stem': group + '/' + folder + '/' + task['id']}
    state.update(status='downloading', expected_bytes=payload['bytes'], checked_utc=now())
    save(path, state)
    process = subprocess.Popen(SSH + ['python3 ' + FETCHER + ' ' + DATA_ROOT],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True)
    process.stdin.write(json.dumps(payload))
    process.stdin.close()
    answer = None
    error = None
    for line in process.stdout:
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if 'progress_bytes' in message:
            state.update(received_bytes=message['progress_bytes'], checked_utc=now())
            save(path, state)
        if 'result' in message:
            answer = message['result']
        if 'error_type' in message:
            error = message
    code = process.wait()
    if code or answer is None:
        state.update(last_transfer_error=error or {'error_type': 'SSH_or_remote_process_failure'}, checked_utc=now())
        save(path, state)
        return None
    return answer


def process_task(task):
    key = task['id']
    path = STATE / (key + '.json')
    legacy = BASE / 'reference/metadata/climate_jobs' / (key + '.json')
    state = json.loads(path.read_text()) if path.exists() else (
        json.loads(legacy.read_text()) if legacy.exists() else {})
    state['task'] = task
    if state.get('status') == 'downloaded_verified':
        return key, 'existing'
    if state.get('status') in ['submitting', 'submission_unknown'] and not state.get('job_id'):
        STOP_SUBMISSION.set()
        log(key, 'submission_unknown_requires_reconciliation')
        return key, 'submission_unknown'
    c = client()
    missing_checks = 0
    transfer_failures = 0
    while True:
        if not state.get('job_id'):
            if STOP_SUBMISSION.is_set():
                return key, 'not_submitted_safety_stop'
            if len(state.get('previous_attempts', [])) >= 4:
                state.update(status='needs_review_terminal_failures', checked_utc=now());save(path, state)
                return key, state['status']
            state.update(status='submitting', submission_started_utc=now())
            save(path, state)
            try:
                remote = c.retrieve(task['dataset'], task['request'])
                state.update(job_id=remote.request_id, status='submitted', submitted_utc=now())
                save(path, state)
                log(key, 'submitted')
            except Exception as e:
                state.update(status='submission_unknown', error_type=type(e).__name__, http_status=status_code(e), checked_utc=now())
                save(path, state)
                STOP_SUBMISSION.set()
                log(key, 'submission_unknown_requires_reconciliation')
                return key, state['status']
        try:
            remote = c.client.get_remote(state['job_id'])
            status = remote.status
            state.update(status=status, checked_utc=now())
            save(path, state)
        except Exception as e:
            state.update(last_poll_error_type=type(e).__name__, last_poll_http_status=status_code(e), checked_utc=now())
            save(path, state)
            if status_code(e) in [401, 403]:
                STOP_SUBMISSION.set()
                return key, 'authorization_required'
            # Observation errors do not invalidate a live job or trigger resubmission.
            time.sleep(45)
            continue
        if status in ['accepted', 'running', 'queued']:
            time.sleep(45)
            continue
        if status in ['failed', 'rejected', 'dismissed', 'deleted']:
            state.setdefault('previous_attempts', []).append({'job_id': state.pop('job_id'), 'status': status, 'checked_utc': now()})
            state.update(status='retry_after_terminal_state');save(path, state)
            time.sleep(60)
            continue
        if status != 'successful':
            state.update(status='unrecognized_remote_status', remote_status=status);save(path, state)
            return key, state['status']
        try:
            result = remote.get_results()
            missing_checks = 0
        except Exception as e:
            missing_checks = missing_checks + 1 if status_code(e) in [404, 410] else 0
            state.update(result_error_type=type(e).__name__, result_http_status=status_code(e), missing_result_checks=missing_checks, checked_utc=now())
            save(path, state)
            if missing_checks >= 3:
                state.setdefault('previous_attempts', []).append({'job_id': state.pop('job_id'), 'status': 'successful_but_result_missing', 'http_status': status_code(e), 'checked_utc': now()})
                state['status'] = 'retry_expired_result';save(path, state)
                missing_checks = 0
            time.sleep(45)
            continue
        try:
            downloaded = transfer(task, state['job_id'], result, state, path)
        except Exception as e:
            state.update(last_transfer_error={'error_type': type(e).__name__}, checked_utc=now())
            save(path, state)
            downloaded = None
        if downloaded:
            state.update(status='downloaded_verified', raw_archive=downloaded, completed_utc=now())
            save(path, state)
            log(key, 'downloaded_verified')
            return key, 'downloaded_verified'
        transfer_failures += 1
        if transfer_failures >= 5:
            state.update(status='transfer_needs_review', checked_utc=now());save(path, state)
            return key, state['status']
        time.sleep(30)


def snapshot(plan, finished=False):
    states = []
    for task in plan:
        path = STATE / (task['id'] + '.json')
        states.append(json.loads(path.read_text()) if path.exists() else {'status': 'not_submitted'})
    done = [s for s in states if s.get('status') == 'downloaded_verified']
    report = {'updated_utc': now(), 'pid': os.getpid(), 'planned_tasks': len(plan),
              'statuses': dict(collections.Counter(s['status'] for s in states)),
              'verified_downloads': len(done),
              'verified_bytes': sum(s.get('raw_archive', {}).get('bytes', 0) for s in done),
              'worker_finished': finished, 'submission_safety_stop': STOP_SUBMISSION.is_set(),
              'complete': len(done) == len(plan),
              'scope': 'CDS temperature baseline/analysis, weather/precipitation, hourly temperature; not IODA or CMIP6'}
    save(BASE / 'progress.json', report)
    return report


def main():
    logging.disable(logging.CRITICAL)
    STATE.mkdir(parents=True, exist_ok=True)
    lock = (BASE / 'collector.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    sync_remote_completions()
    plan = json.loads((BASE / 'climate_plan.json').read_text())
    save(BASE / 'worker.json', {'pid': os.getpid(), 'started_utc': now(), 'script': str(Path(__file__).resolve())})
    # Daily-statistics processing and native archive retrieval are distinct CDS
    # collections. Keep their queues bounded independently so a long daily queue
    # does not prevent required precipitation/hourly inputs from progressing.
    assert {t['dataset'] for t in plan} <= {'derived-era5-land-daily-statistics', 'reanalysis-era5-land'}
    assert len({t['id'] for t in plan}) == len(plan)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as daily_pool, \
            concurrent.futures.ThreadPoolExecutor(max_workers=1) as archive_pool, \
            concurrent.futures.ThreadPoolExecutor(max_workers=3) as hourly_pool:
        futures = [(hourly_pool if task['kind'] == 'hourly_temperature' else
                    archive_pool if task['dataset'] == 'reanalysis-era5-land' else daily_pool)
                   .submit(process_task, task) for task in plan]
        while any(not f.done() for f in futures):
            snapshot(plan)
            time.sleep(30)
        for future in futures:
            try:
                future.result()
            except Exception as e:
                log('worker', type(e).__name__)
    print(json.dumps(snapshot(plan, finished=True)), flush=True)


if __name__ == '__main__':
    main()
