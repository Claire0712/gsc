"""Compare all accepted scenario point arrays against original primary arrays."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import time
import numpy as np

root=Path('/volume1/homes/Judy/GSC2027/HeatSignal')
base=root/'analysis/2026-10-12_connection_baseline/v1/full_outputs'
started=time.monotonic()
def read(path):
    return json.loads(path.read_text())
def checked(path, entry):
    data=path.read_bytes()
    assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256'],path

primary=read(base/'manifest.json')
points=sorted(k for k in primary['outputs'] if k.startswith('points_'))
assert len(points)==2730
reports=[]
for scenario in ('unknown_end_plusminus7','unknown_end_plusminus30'):
    directory=root/'analysis/2026-10-23_stop_reference_baseline/v1'/('full_'+scenario)
    manifest=read(directory/'manifest.json')
    assert read(directory/'status.json')['status']=='completed'
    assert read(directory/'summary.json')['stop_scenario']==scenario
    assert sorted(k for k in manifest['outputs'] if k.startswith('points_'))==points
    changed=[];counts=defaultdict(Counter)
    for name in points:
        checked(base/name,primary['outputs'][name]);checked(directory/name,manifest['outputs'][name])
        with np.load(base/name,allow_pickle=False) as old,np.load(directory/name,allow_pickle=False) as new:
            assert set(old.files)==set(new.files)
            for key in ('country_id','event_id','signal','target_timestamps','target_values'):
                assert np.array_equal(old[key],new[key],equal_nan=True) if old[key].dtype.kind in 'fc' else np.array_equal(old[key],new[key]), (name,key)
            delta={}
            for key in old.files:
                a,b=old[key],new[key]
                assert a.shape==b.shape and a.dtype==b.dtype,(name,key)
                same=(a==b)
                if a.dtype.kind in 'fc':same=same | (np.isnan(a)&np.isnan(b))
                n=int(np.count_nonzero(~same))
                if n:delta[key]=n
            if delta:
                country=str(old['country_id']);signal=str(old['signal'])
                changed.append(dict(file=name,country=country,signal=signal,event=str(old['event_id']),changed_elements=delta))
                counts[country].update(delta)
    reports.append(dict(scenario=scenario,windows_checked=len(points),changed_windows=changed,
                        changed_elements_by_country=dict(counts)))
print(json.dumps(dict(status='verified_comparison',reports=reports,elapsed_seconds=time.monotonic()-started,
    scope='Exact hash-checked point-array comparison; changed-element counts include repeated reference queries and are not independent events. No DHRD, matching, or effect inference.'),allow_nan=False))
