"""Reverify every planned ADM1 raw response and report actual signal availability."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
from server_fetch import atomic_json, now


def main(root, plan_path):
    tasks = json.loads(plan_path.read_text())
    assert len({t['id'] for t in tasks}) == len(tasks), 'duplicate task IDs'
    out = root / 'metadata/full_download_v2'
    years, failures, missing, verified = {}, [], [], []
    for i, task in enumerate(tasks, 1):
        record_path = root / 'ioda/adm1_six_countries/raw' / (task['id'] + '.metadata.json')
        if not record_path.exists():
            missing.append(task['id'])
            continue
        try:
            record = json.loads(record_path.read_text())
            assert record['task'] == task, 'metadata task differs from plan'
            file = (root / record['file']).resolve()
            assert root in file.parents, 'path outside data root'
            payload = file.read_bytes()
            assert len(payload) == record['bytes'], 'wrong size'
            assert hashlib.sha256(payload).hexdigest() == record['sha256'], 'wrong SHA256'
            raw = json.loads(gzip.decompress(payload))
            assert not raw.get('error'), 'stored API error'
            req = raw['requestParameters']
            assert req['from'] == task['from'] and req['until'] == task['until'], 'wrong request dates'
            seen, observations, null_series = set(), 0, 0
            for group in raw['data']:
                for series in group:
                    code = str(series['entityCode'])
                    assert series['entityType'] == 'region' and code in task['regions'], 'wrong entity'
                    assert code not in seen, 'duplicate series'
                    assert series['datasource'] == task['datasource'], 'wrong source'
                    assert series['step'] == series['nativeStep'] and series['step'] > 0, 'downsampled series'
                    assert task['from'] <= series['from'] < task['until'], 'wrong series start'
                    assert series['until'] <= task['until'], 'wrong series end'
                    if series['values']:
                        assert series['from'] + (len(series['values']) - 1) * series['step'] < task['until'], 'values extend past requested quarter'
                    count = sum(v is not None for v in series['values'])
                    observations += count
                    null_series += count == 0
                    seen.add(code)
            assert set(record['regions_without_series']) == set(task['regions']) - seen, 'missing-series metadata mismatch'
            year = years.setdefault(str(task['year']), dict(requests=0, requested_region_quarter_sources=0,
                                   returned_series=0, absent_series=0, all_null_series=0, nonmissing_values=0))
            year['requests'] += 1
            year['requested_region_quarter_sources'] += len(task['regions'])
            year['returned_series'] += len(seen)
            year['absent_series'] += len(set(task['regions']) - seen)
            year['all_null_series'] += null_series
            year['nonmissing_values'] += observations
            verified.append(task['id'])
        except Exception as exc:
            failures.append(dict(id=task['id'], error_type=type(exc).__name__, message=str(exc)))
        if i % 100 == 0 or i == len(tasks):
            atomic_json(out / 'ioda_adm1_audit_progress.json', dict(checked_utc=now(), examined=i,
                        planned=len(tasks), passed=len(verified), failures=len(failures), missing=len(missing)))
            print(i, '/', len(tasks), 'passed', len(verified), 'failures', len(failures), flush=True)
    report = dict(checked_utc=now(), planned_requests=len(tasks), verified_response_files=len(verified),
                  missing_ids=missing, failures=failures, all_planned_responses_verified=not missing and not failures,
                  years=years, scope='All planned raw responses: SHA256, bytes, gzip/JSON, request dates, entities, sources, native sampling and availability. Successful empty responses do not supply historical observations.')
    atomic_json(out / 'ioda_adm1_full_reverification.json', report)
    print(json.dumps(report, indent=2), flush=True)
    return report


if __name__ == '__main__':
    result = main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]))
    sys.exit(0 if result['all_planned_responses_verified'] else 1)
