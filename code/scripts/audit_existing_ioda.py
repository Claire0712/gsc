"""Rehash every existing country response and derive coverage from raw observations."""
import collections
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import sys
from server_fetch import atomic_json, now

CORE = ['ping-slash24', 'bgp', 'merit-nt']


def main():
    root = Path(sys.argv[1]).resolve()
    manifests = sorted(p for folder in ['raw_country_batches', 'raw_core_signals']
                       for p in (root / 'ioda' / folder).glob('*.metadata.json')
                       if not p.name.startswith('._'))
    output = root / 'metadata/full_download_v2'
    rows, requested, observations, missing_values, lengths = [], set(), {}, {}, {}
    failures = []
    for i, path in enumerate(manifests, 1):
        row = {'manifest': str(path.relative_to(root))}
        try:
            record = json.loads(path.read_text())
            file = (root / record['file']).resolve()
            assert root in file.parents, 'manifest path outside root'
            payload = file.read_bytes()
            assert len(payload) == record['bytes'], 'size mismatch'
            assert hashlib.sha256(payload).hexdigest() == record['sha256'], 'SHA256 mismatch'
            raw = json.loads(gzip.decompress(payload))
            assert not raw.get('error'), 'stored API error'
            year, quarter = record['year'], record['quarter']
            start = int(dt.datetime(year, 3*quarter-2, 1, tzinfo=dt.timezone.utc).timestamp())
            until = int((dt.datetime(year+1, 1, 1, tzinfo=dt.timezone.utc) if quarter == 4
                         else dt.datetime(year, 3*quarter+1, 1, tzinfo=dt.timezone.utc)).timestamp())
            assert raw['requestParameters']['from'] == start and raw['requestParameters']['until'] == until, 'wrong quarter'
            sources = [record['datasource']] if record.get('datasource') else CORE
            requested.update((year, quarter, c, src) for c in record['countries'] for src in sources)
            count = 0
            for group in raw['data']:
                for series in group:
                    source = series['datasource']
                    if source not in CORE:
                        continue
                    assert series['entityType'] == 'country' and series['entityCode'] in record['countries'], 'unexpected country'
                    assert source in sources, 'unexpected core source'
                    assert series['step'] == series['nativeStep'] and series['nativeStep'] > 0, 'downsampled series'
                    assert start <= series['from'] < until and series['until'] <= until, 'series outside requested quarter'
                    key = (year, quarter, series['entityCode'], source)
                    nonmissing = sum(v is not None for v in series['values'])
                    observations[key] = max(observations.get(key, 0), nonmissing)
                    lengths[key] = max(lengths.get(key, 0), len(series['values']))
                    missing_values[key] = len(series['values']) - nonmissing
                    count += 1
            row.update(passed=True, file=record['file'], bytes=len(payload), sha256=record['sha256'], core_series=count)
        except Exception as e:
            row.update(passed=False, error_type=type(e).__name__, message=str(e))
            failures.append(row)
        rows.append(row)
        if i % 100 == 0 or i == len(manifests):
            atomic_json(output / 'ioda_country_audit_progress.json', {'checked_utc': now(), 'files_checked': i,
                         'planned_files': len(manifests), 'failures': len(failures), 'finished': i == len(manifests)})
            print(i, '/', len(manifests), 'failures', len(failures), flush=True)
    years = {}
    for year in range(2018, 2026):
        keys = {k for k in requested if k[0] == year}
        years[year] = {'requested_country_quarter_sources': len(keys),
                       'with_nonmissing_values': sum(observations.get(k, 0) > 0 for k in keys),
                       'without_series': sum(k not in observations for k in keys),
                       'all_null_series': sum(k in observations and observations[k] == 0 for k in keys),
                       'nonmissing_values': sum(observations.get(k, 0) for k in keys)}
    report = {'checked_utc': now(), 'files_checked': len(manifests), 'all_files_passed': not failures,
              'failures': failures, 'years': years, 'files': rows,
              'scope': 'Full original country response archive: SHA256/bytes/GZIP/JSON/request quarters/native core sampling and raw availability; not proof of representativeness or causal suitability.',
              'full_target_period_observations_available': False}
    atomic_json(output / 'ioda_country_full_reverification.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'files'}), flush=True)


if __name__ == '__main__':
    main()
