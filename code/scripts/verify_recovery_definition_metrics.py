"""Read-only independent scalar checks and counts; no imports from metrics core."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import numpy as np

p=argparse.ArgumentParser()
p.add_argument('--metrics',required=True,type=Path)
p.add_argument('--baseline',required=True,type=Path)
p.add_argument('--output',required=True,type=Path)
a=p.parse_args()
if a.output.exists():raise FileExistsError(a.output)
manifest=json.loads((a.metrics/'manifest.json').read_text())
hashes={}
for name,entry in manifest['outputs'].items():
    data=(a.metrics/name).read_bytes()
    hashes[name]=hashlib.sha256(data).hexdigest()==entry['sha256'] and len(data)==entry['bytes']
assert all(hashes.values())
rows=json.loads((a.metrics/'event_metrics.json').read_text())
definition=json.loads((a.metrics/'summary.json').read_text())
threshold=definition['maintenance_threshold'];slots=definition['confirmation_slots']
assert (threshold,slots) in ((.9,24),(.98,24),(.95,12),(.95,36))
summary={}; selected={}
for row in rows:
    s=row['signal'];m=row['metrics'];r=m['recovery']
    assert m['maintenance_threshold']==threshold and m['confirmation_slots']==slots
    if s not in summary:summary[s]=dict(windows=0,complete=0,unconfounded=0,states=Counter(),recovery_statuses=Counter(),core_recurrences=0,post_recurrences=0)
    q=summary[s];q['windows']+=1;q['complete']+=int(m['full_window_complete']);q['unconfounded']+=int(row['full_observed_unconfounded'])
    q['states'][m['state']]+=1;q['recovery_statuses'][r['status']]+=1
    q['core_recurrences']+=int(m['recurrence_during_core'] is True)
    q['post_recurrences']+=int(r['recurrence_after_confirmation'] is True)
    assert row['final_sample_eligible'] is False
    # Select one representative of each distinct scientific state/censoring per signal.
    key=(s,m['state'],r['status'],r['supplementary_status'],m['recurrence_during_core'])
    selected.setdefault(key,row)
checks=[]
for row in selected.values():
    m=row['metrics'];path=a.baseline/row['source_point_file']
    entry=manifest['inputs'][str(path)]
    data=path.read_bytes();assert hashlib.sha256(data).hexdigest()==entry['sha256']
    with np.load(path,allow_pickle=False) as z:
        vals=z['target_values'].tolist();base=z['baseline'].tolist();valid=z['analysis_available'].tolist()
    ratios=[v/b if ok else None for v,b,ok in zip(vals,base,valid)]
    ncore=m['core_required_slots'];core=ratios[:ncore]
    if all(valid):
        deficit=math.fsum(max(0,1-x) for x in ratios)/6
        signed=math.fsum(x-1 for x in ratios)/6
        assert math.isclose(deficit,m['dhrd_hours'],rel_tol=1e-12,abs_tol=1e-12)
        assert math.isclose(signed,m['signed_deviation_hours'],rel_tol=1e-12,abs_tol=1e-12)
    else:
        deficit=None;assert m['dhrd_hours'] is None
    recovery=m['recovery'];confirmation=None
    if recovery['survival_eligible_from_core']:
        assert all(x is not None for x in core) and core[-1]<threshold
        consecutive=0;last=0
        for i,ratio in enumerate(ratios[ncore:]):
            if ratio is None:break
            last=i+1
            consecutive=consecutive+1 if ratio>=threshold else 0
            if consecutive==slots:
                confirmation=(i+1)/6;break
        assert confirmation==recovery['confirmation_hours']
        if confirmation is not None:assert recovery['status']=='confirmed'
        elif last==432:assert recovery['status']=='right_censored_72h'
        else:assert recovery['status']=='missingness_censored' and recovery['followup_hours']==last/6
    checks.append(dict(event_id=row['event_id'],signal=row['signal'],state=m['state'],dhrd_hours=deficit,
                       recovery_status=recovery['status'],independent_confirmation_hours=confirmation))
report=dict(status='passed',output_hash_checks=hashes,signal_summary=summary,
            independent_scalar_checks=checks,scalar_case_count=len(checks),all_final_sample_eligible_false=True,
            note='Scalar sums and consecutive-slot loops independent of metrics implementation. Sampled representative states, not causal validation.')
with a.output.open('x') as f:json.dump(report,f,indent=2,allow_nan=False)
print(json.dumps(dict(status='passed',scalar_case_count=len(checks),signal_summary=summary)))
