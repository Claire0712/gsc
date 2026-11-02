"""Read-only hash/identity/invariant audit and technical risk-set counts."""
import json,hashlib
from pathlib import Path
from collections import Counter

root=Path(__file__).resolve().parents[1]
def read(directory):
    path=root/directory/'event_metrics.json'
    manifest=json.loads((path.parent/'manifest.json').read_text())
    entry=manifest['outputs'][path.name];data=path.read_bytes()
    assert hashlib.sha256(data).hexdigest()==entry['sha256']
    rows=json.loads(data);index={(r['event_id'],r['signal']):r for r in rows}
    assert len(index)==len(rows)
    return index
main=read('analysis/2026-10-12_resilience_metrics/v1/full_outputs')
fields=('dhrd_hours','signed_deviation_hours','coverage_fraction','valid_slots',
        'full_window_complete','mean_deficit_core','peak_loss_core','peak_loss_full')
reports=[]
for scenario in ('90_4h','98_4h','95_2h','95_6h'):
    other=read('analysis/2026-10-25_recovery_definition/v1/full_'+scenario)
    assert set(other)==set(main)
    counts={}
    for key,r in other.items():
        prior=main[key]
        assert r['country_id']==prior['country_id']
        assert r['full_observed_unconfounded']==prior['full_observed_unconfounded']
        for field in fields:assert r['metrics'][field]==prior['metrics'][field],(scenario,key,field)
        s=r['signal'];c=counts.setdefault(s,Counter())
        m=r['metrics'];rec=m['recovery'];c['windows']+=1
        c['technical_risk']+=int(rec['survival_eligible_from_core'])
        if rec['survival_eligible_from_core']:c['risk_'+rec['status']]+=1
        c['state_'+m['state']]+=1
    reports.append(dict(scenario=scenario,windows=len(other),by_signal=counts))
print(json.dumps(dict(status='verified',invariant_fields=fields,reports=reports,
    limit='Technical risk only; not confound-censored qualification or Cox inference.'),allow_nan=False))
