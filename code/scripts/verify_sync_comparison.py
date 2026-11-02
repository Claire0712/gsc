"""Preserved independent comparison audit plus exact sync-mask/raw-view checks."""
import argparse,json,sys
from pathlib import Path
import numpy as np

p=argparse.ArgumentParser()
for key in ('output','baseline','verifier','sync'):p.add_argument('--'+key,required=True,type=Path)
a=p.parse_args();summary=json.loads((a.output/'summary.json').read_text())
universe=summary['sync_universe'];assert universe in ('joint','all')
sets={}
for signal in summary['selected_signals']:
    with np.load(a.sync/(signal+'_'+universe+'.npz'),allow_pickle=False) as z:
        sets[signal]=z['interval_start_utc'][z['candidate']]
targets=queries=0
for file in a.output.glob('window_*.npz'):
    with np.load(file,allow_pickle=False) as z:
        t=z['target_timestamps'];signal=str(z['signal']);q=t[:,None]+np.array([-28,-21,-14,-7,7,14,21,28])[None,:]*86400
        mask=np.isin(t,sets[signal]);ref=np.isin(q,sets[signal])
        np.testing.assert_array_equal(z['target_sync_candidate'],mask)
        np.testing.assert_array_equal(z['reference_sync_candidate'],ref)
        np.testing.assert_array_equal(z['target_values'],np.where(mask,np.nan,z['raw_target_values']))
        assert not np.any(z['analysis_available']&mask)
        targets+=int(mask.sum());queries+=int(ref.sum())
source=a.verifier.read_text()
old="base=root/'analysis/2026-10-12_connection_baseline/v1/full_outputs'"
assert source.count(old)==1
source=source.replace(old,'base=Path('+repr(str(a.baseline.absolute()))+')')
needle='raw_t=np.concatenate(source_times);raw_v=np.concatenate(source_values)'
assert source.count(needle)==1
source=source.replace(needle,needle+";raw_v=raw_v.copy();raw_v[np.isin(raw_t,"+repr(sets.get('bgp',np.array([],dtype=np.int64)).tolist())+")]=np.nan")
sys.argv=[str(a.verifier),str(a.output.absolute())]
print(json.dumps(dict(sync_target_occurrences=targets,sync_reference_occurrences=queries)),file=sys.stderr)
exec(compile(source,str(a.verifier),'exec'),{'__name__':'__main__','__file__':str(a.verifier)})
