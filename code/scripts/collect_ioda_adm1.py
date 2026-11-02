"""Collect native IODA region signals required by the proposal's six-country check."""
import concurrent.futures
import datetime as dt
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request
from server_fetch import atomic_json, now


def summarize(data, task):
    if data.get('error'):
        raise ValueError('IODA API error')
    result = []
    seen = set()
    for group in data['data']:
        for series in group:
            code = str(series['entityCode'])
            if series['entityType'] != 'region' or code not in task['regions']:
                raise ValueError('Unexpected region')
            if series['datasource'] != task['datasource'] or code in seen:
                raise ValueError('Unexpected or duplicate source')
            if series['step'] != series['nativeStep'] or series['nativeStep'] <= 0:
                raise ValueError('Temporal downsampling')
            seen.add(code)
            result.append({'region': code, 'native_step': series['nativeStep'],
                           'points': len(series['values']),
                           'nonmissing': sum(v is not None for v in series['values']),
                           'from': series['from'], 'until': series['until']})
    return result


def collect(root, task):
    out = root / 'ioda/adm1_six_countries/raw'
    out.mkdir(parents=True, exist_ok=True)
    dest = out / (task['id'] + '.json.gz')
    record = out / (task['id'] + '.metadata.json')
    if record.exists():
        old = json.loads(record.read_text())
        if dest.stat().st_size != old['bytes'] or hashlib.sha256(dest.read_bytes()).hexdigest() != old['sha256']:
            raise ValueError('Previously downloaded raw response changed')
        return old
    url = 'https://api.ioda.inetintel.cc.gatech.edu/v2/signals/raw/region/' + ','.join(task['regions'])
    url += '?' + urllib.parse.urlencode({'from': task['from'], 'until': task['until'],
                                        'datasource': task['datasource'], 'maxPoints': 1000000})
    for attempt in range(1, 6):
        try:
            if dest.exists():
                payload = dest.read_bytes()
                data = json.loads(gzip.decompress(payload))
            else:
                with urllib.request.urlopen(url, timeout=120) as response:
                    content = response.read()
                data = json.loads(content)
                payload = gzip.compress(content, compresslevel=6, mtime=0)
            series = summarize(data, task)
            if not dest.exists():
                part = dest.with_name(dest.name + '.part')
                part.write_bytes(payload)
                part.rename(dest)
            result = {'id': task['id'], 'task': task, 'file': str(dest.relative_to(root)),
                      'url': url, 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(),
                      'retrieved_utc': data.get('metadata', {}).get('responseTime'),
                      'checked_utc': now(), 'core_signals': series,
                      'regions_without_series': sorted(set(task['regions']) - {s['region'] for s in series}),
                      'status': 'downloaded_with_series' if series else 'response_without_series'}
            atomic_json(record, result)
            print(json.dumps({'id': task['id'], 'status': result['status'], 'regions_returned': len(series)}), flush=True)
            time.sleep(0.5)
            return result
        except Exception as e:
            if attempt == 5:
                result = {'id': task['id'], 'status': 'failed', 'error_type': type(e).__name__,
                          'http_status': getattr(e, 'code', None), 'checked_utc': now()}
                errors = root / 'ioda/adm1_six_countries/errors'
                errors.mkdir(parents=True, exist_ok=True)
                atomic_json(errors / (task['id'] + '.json'), result)
                return result
            time.sleep(10 * attempt)


def main():
    root = Path(sys.argv[1]).resolve()
    plan = json.loads(Path(sys.argv[2]).read_text())
    out = root / 'ioda/adm1_six_countries'
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'worker.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        atomic_json(out / 'worker.json', {'pid': os.getpid(), 'started_utc': now(), 'planned': len(plan)})
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = {pool.submit(collect, root, t): t for t in plan}
            while True:
                results = []
                for f, task in futures.items():
                    if f.done():
                        try:
                            results.append(f.result())
                        except Exception as e:
                            results.append({'id': task['id'], 'status': 'failed', 'error_type': type(e).__name__})
                finished = len(results) == len(plan)
                report = {'updated_utc': now(), 'pid': os.getpid(), 'planned': len(plan),
                          'finished_requests': len(results), 'worker_finished': finished,
                          'responses_with_series': sum(r['status'] == 'downloaded_with_series' for r in results),
                          'responses_without_series': sum(r['status'] == 'response_without_series' for r in results),
                          'failed_ids': [r['id'] for r in results if r['status'] == 'failed'],
                          'note': 'Successful HTTP responses, including empty responses, do not prove full historical coverage or observability.'}
                atomic_json(out / 'progress.json', report)
                if finished:
                    break
                time.sleep(30)


if __name__ == '__main__':
    main()
