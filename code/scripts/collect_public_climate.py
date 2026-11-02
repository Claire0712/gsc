"""NAS-only public NASA download worker, bounded concurrency and durable progress."""
import concurrent.futures
import fcntl
import json
import os
from pathlib import Path
import sys
import time
from server_fetch import fetch, atomic_json, now


def process(root, task):
    errors = root / 'metadata/full_download_v2/errors'
    errors.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, 9):
        try:
            result = fetch(root, task)
            print(json.dumps({'id': task['id'], 'status': result['status'], 'time': now()}), flush=True)
            return task['id'], result['status']
        except Exception as e:
            failure = {'id': task['id'], 'attempt': attempt, 'error_type': type(e).__name__,
                       'http_status': getattr(e, 'code', None), 'time': now()}
            atomic_json(errors / (task['id'] + '.json'), failure)
            print(json.dumps(failure), flush=True)
            if failure['http_status'] in [401, 403, 404, 412] or isinstance(e, (ValueError, FileExistsError)):
                break
            time.sleep(min(30 * 2**(attempt-1), 900))
    return task['id'], 'needs_review'


def main():
    root = Path(sys.argv[1]).resolve()
    plan_path = Path(sys.argv[2]).resolve()
    tasks = json.loads(plan_path.read_text())['tasks']
    metadata = root / 'metadata/full_download_v2'
    metadata.mkdir(parents=True, exist_ok=True)
    with (metadata / 'cmip6_worker.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        atomic_json(metadata / 'cmip6_worker.json', {'pid': os.getpid(), 'started_utc': now(),
                    'planned': len(tasks), 'plan': str(plan_path)})
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(process, root, t): t for t in tasks}
            while any(not f.done() for f in futures):
                done = []
                failed = []
                for f, task in futures.items():
                    if f.done():
                        try:
                            _, status = f.result()
                        except Exception:
                            status = 'needs_review'
                        (done if status in ['downloaded_verified', 'existing_verified'] else failed).append(task)
                atomic_json(metadata / 'cmip6_progress.json', {'pid': os.getpid(), 'updated_utc': now(),
                            'planned': len(tasks), 'verified': len(done),
                            'verified_bytes': sum(t['bytes'] for t in done),
                            'needs_review': [t['id'] for t in failed], 'worker_finished': False})
                time.sleep(30)
            results = [f.result() for f in futures]
        atomic_json(metadata / 'cmip6_progress.json', {'pid': os.getpid(), 'updated_utc': now(),
                    'planned': len(tasks), 'verified': sum(s in ['downloaded_verified', 'existing_verified'] for _, s in results),
                    'needs_review': [k for k, s in results if s not in ['downloaded_verified', 'existing_verified']],
                    'worker_finished': True})


if __name__ == '__main__':
    main()
