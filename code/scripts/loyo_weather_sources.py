"""Exact monthly provenance gate for LOYO batches without an original-manifest link."""
from pathlib import Path
import json

def verify_monthly_membership(entries, path, record):
    path = Path(path)
    for target, expected in ((path, record['sha256']), (path.with_suffix('.audit.json'), record['audit_sha256'])):
        matches = [v for k, v in entries.items() if Path(k).resolve() == target.resolve()]
        if len(matches) != 1 or matches[0]['sha256'] != expected:
            raise ValueError('Missing, ambiguous or different LOYO monthly provenance: ' + str(target))

def resolve_sources(heat, batch, original, sources, weather):
    matches = [v for k, v in heat['inputs'].items() if Path(k).resolve() == Path(batch).resolve()]
    if len(matches) != 1:
        raise ValueError('LOYO heat stage must link its exact batch manifest')
    bm = json.loads(sources.read(batch, matches[0]))
    om = json.loads(sources.read(original))
    if bm.get('status') != 'completed' or om.get('state') != 'complete':
        raise ValueError('Incomplete monthly provenance stages')
    monthly = om['sources']
    if len(monthly) != 96 or len({r['month'] for r in monthly}) != 96:
        raise ValueError('96 unique original source months required')
    for record in monthly:
        verify_monthly_membership(bm['inputs'], Path(weather) / f"era5_country_daily_{record['month']}.csv", record)
    sources.verify(Path(__file__))
    sources.verify(Path(__file__).with_name('run_loyo_pre_weather.py'))
    return monthly
