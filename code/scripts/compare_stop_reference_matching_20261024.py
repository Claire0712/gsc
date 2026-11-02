"""Exact selected-record comparison; no outcome selection or model changes."""
import hashlib
import json
from pathlib import Path

root=Path('/volume1/homes/Judy/GSC2027/HeatSignal')
def records(directory, name):
    manifest=json.loads((directory/'manifest.json').read_text())
    data=(directory/name).read_bytes();expected=manifest['outputs'][name]
    assert len(data)==expected['bytes'] and hashlib.sha256(data).hexdigest()==expected['sha256']
    return json.loads(data)
def canonical(row):return json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)
result=[]
for scenario in ('unknown_end_plusminus7','unknown_end_plusminus30'):
    for scale in ('0.5','1','2'):
        name='selected_'+scale+'.json'
        primary=records(root/'analysis/2026-10-12_matching/v1/full_outputs',name)
        changed=records(root/'analysis/2026-10-24_stop_reference_matching/v1'/('full_'+scenario),name)
        a={canonical(r) for r in primary};b={canonical(r) for r in changed}
        assert len(a)==len(primary) and len(b)==len(changed)
        result.append(dict(scenario=scenario,scale=scale,primary_records=len(a),scenario_records=len(b),
            identical_records=primary==changed,removed_records=[json.loads(k) for k in sorted(a-b)],
            added_records=[json.loads(k) for k in sorted(b-a)]))
print(json.dumps(dict(status='verified_comparison',comparisons=result,
    scope='Exact selected-record comparison including weights/distances; changed records may represent metadata changes, not distinct independent pairs. No effect interpretation.'),indent=2))
