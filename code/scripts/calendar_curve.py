"""Add exact UTC-day common effects without changing the frozen sample."""
import argparse,json,time
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy import sparse
from .event_curve_core import fit
from .run_connection_baseline import Sources,Stage,_json
def augment(z,timestamps):
    t=np.asarray(timestamps,dtype=np.int64)
    if len(t)!=z.shape[0] or np.any(t%86400):raise ValueError('Aligned UTC midnights required')
    unique,index=np.unique(t,return_inverse=True)
    d=sparse.csr_matrix((np.ones(len(t)),(np.arange(len(t)),index)),shape=(len(t),len(unique)))
    return sparse.hstack([z,d],format='csr')
def run(args):
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError('Fresh output required')
    sources=Sources();stage=Stage(args.estimates,sources,status_key='status',manifest_key=('status','completed'))
    def read(n):return sources.read(Path(args.estimates)/n,stage.manifest['outputs'][n])
    est=_json(read('estimates.json'));rows=_json(read('row_identity.json'));p=Path(args.estimates)/'model_inputs.npz';sources.verify(p,stage.manifest['outputs'][p.name])
    with np.load(p,allow_pickle=False) as z:
        original=sparse.csr_matrix((z['z_data'],z['z_indices'],z['z_indptr']),shape=tuple(z['z_shape']))
        extended=augment(original,[int(r['date_utc']) for r in rows]);x=z['x'].copy();w=z['weights'].copy();ys={o:z[o].copy() for o in est['results']}
    results={};reason=None
    for outcome,y in ys.items():
        try:f=fit(x,y,extended,w)
        except ValueError as exc:
            if str(exc) not in ('Absorbed focal column','Focal design rank deficient'):raise
            reason=str(exc);results={};break
        results[outcome]=dict(beta=f['beta'].tolist(),condition=f['condition'],projection=f['projection'],weighted_residual_ss=float(f['residual']@f['residual']))
    for name in ('calendar_curve.py','event_curve_core.py','run_connection_baseline.py'):sources.verify(Path(__file__).parent/name)
    dates=defaultdict(set)
    for r in rows:dates[r['date_utc']].add(r['country_id'])
    sources.check();out.mkdir(parents=True)
    def publish(n,obj):(out/n).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
    np.savez_compressed(out/'model_inputs.npz',x=x,weights=w,z_data=extended.data,z_indices=extended.indices,z_indptr=extended.indptr,z_shape=extended.shape,**ys)
    publish('row_identity.json',rows)
    publish('estimates.json',dict(signal=est['signal'],rows=len(rows),groups=est['groups'],countries=est['countries'],terms=est['terms'],reference_day=-1,results=results,estimable=reason is None,not_estimable_reason=reason,calendar_dates=len(dates),multi_country_dates=sum(len(v)>1 for v in dates.values()),elapsed_seconds=time.monotonic()-start,scope='Exact UTC-day additive common-effect sensitivity; original sample/weights/dewpoint retained. Point estimates only, no arbitrary cross-country dependence guarantee.'))
    products={n:Sources().verify(out/n) for n in ('model_inputs.npz','row_identity.json','estimates.json')}
    publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products));publish('status.json',dict(status='completed'))
    print(json.dumps(dict(signal=est['signal'],estimable=reason is None,reason=reason,elapsed_seconds=time.monotonic()-start)))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--estimates',required=True);p.add_argument('--output',required=True);run(p.parse_args())
