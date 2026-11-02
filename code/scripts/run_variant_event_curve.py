"""Daily-scale dewpoint-adjusted point estimates. Inference is not yet attached."""
import argparse,csv,io,json,time,os
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import scipy
from scipy import sparse
from .event_curve_core import fit
from .run_connection_baseline import Sources,Stage,_json
from .run_variant_matching import ancestry_entry
DAYS=[k for k in range(-7,8) if k!=-1]
def design(rows):
    x=np.array([[float(r['role']=='heat' and int(r['relative_day'])==k) for k in DAYS]+[float(r['dewpoint'])] for r in rows])
    labels=[]
    for r in rows:
        dt=datetime.fromtimestamp(int(r['date_utc']),timezone.utc)
        labels.append([('window',r['group_id'],r['window_id']),('group_day',r['group_id'],r['relative_day']),('country_weekday',r['country_id'],dt.weekday()),('year_month',dt.year,dt.month)])
    codes={key:i for i,key in enumerate(sorted({key for rr in labels for key in rr},key=str))}
    z=sparse.csr_matrix((np.ones(len(rows)*4),(np.repeat(np.arange(len(rows)),4),[codes[key] for rr in labels for key in rr])),shape=(len(rows),len(codes)))
    return x,z,np.array([float(r['weight']) for r in rows])

def run(args):
    started=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError('Fresh output required')
    sources=Sources();stage=Stage(args.responses,sources,status_key='status',manifest_key=('status','completed'))
    weather=Stage(args.weather,sources,status_key='status',manifest_key=('status','completed'))
    # Prove weather belongs to the same matching lineage as the responses.
    matchpath=Path(args.matching)/'manifest.json'
    match=_json(sources.read(matchpath,ancestry_entry(stage.manifest['inputs'],matchpath)))
    wp=Path(args.weather)/'manifest.json';sources.verify(wp,ancestry_entry(match['inputs'],wp))
    name='daily_1.csv';raw=sources.read(Path(args.responses)/name,stage.manifest['outputs'][name])
    rows=[r for r in csv.DictReader(io.StringIO(raw.decode())) if r['signal']==args.signal and r['purpose']=='curve']
    groups=sorted({r['group_id'] for r in rows})
    if args.limit_groups:
        chosen=set(groups[:args.limit_groups]);rows=[r for r in rows if r['group_id'] in chosen]
    if not rows:raise ValueError('Empty selected model')
    needed={(r['country_id'],datetime.fromtimestamp(int(r['date_utc']),timezone.utc).strftime('%Y-%m-%d')) for r in rows}
    months={date[:7].replace('-','') for _,date in needed};lookup={}
    for p,e in weather.manifest['inputs'].items():
        if Path(p).name in {'era5_country_daily_'+m+'.csv' for m in months}:
            for r in csv.DictReader(io.StringIO(sources.read(Path(p),e).decode())):
                key=r['country_id'],r['date']
                if key in needed:
                    if key in lookup:raise ValueError('Duplicate weather day')
                    lookup[key]=float(r['dewpoint_c'])
    if set(lookup)!=needed:raise ValueError('Weather coverage incomplete')
    for r in rows:r['dewpoint']=lookup[r['country_id'],datetime.fromtimestamp(int(r['date_utc']),timezone.utc).strftime('%Y-%m-%d')]
    for n in ('event_curve_core.py','run_variant_event_curve.py','run_variant_matching.py','run_connection_baseline.py'):sources.verify(Path(__file__).parent/n)
    out.mkdir(parents=True)
    def publish(n,obj):(out/n).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
    publish('status.json',dict(status='running',pid=os.getpid(),rows=len(rows)))
    x,z,w=design(rows);results={}
    try:
        for outcome in ('signed','deficit','below95'):
            y=np.array([float(r[outcome]) for r in rows]);f=fit(x,y,z,w)
            results[outcome]=dict(beta=f['beta'].tolist(),condition=f['condition'],projection=f['projection'],weighted_residual_ss=float(f['residual']@f['residual']))
        sources.check()
        np.savez_compressed(out/'model_inputs.npz',x=x,z_data=z.data,z_indices=z.indices,z_indptr=z.indptr,z_shape=z.shape,weights=w,**{o:np.array([float(r[o]) for r in rows]) for o in results})
        publish('row_identity.json',[{k:r[k] for k in ('group_id','window_id','country_id','date_utc','relative_day','role')} for r in rows])
        publish('estimates.json',dict(signal=args.signal,rows=len(rows),groups=len({r['group_id'] for r in rows}),countries=len({r['country_id'] for r in rows}),terms=['heat_day_'+str(k) for k in DAYS]+['dewpoint_c'],reference_day=-1,results=results,elapsed_seconds=time.monotonic()-started,numpy=np.__version__,scipy=scipy.__version__,scope='Daily-scale sensitivity, main caliper, existing date-normalized weights, contemporaneous dewpoint, fixed effects; point estimates only, no confidence interval or causal claim; no precipitation adjustment. Pilot retains full-sample weights.'))
        products={n:Sources().verify(out/n) for n in ('model_inputs.npz','row_identity.json','estimates.json')}
        publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products));publish('status.json',dict(status='completed',elapsed_seconds=time.monotonic()-started))
        print((out/'estimates.json').read_text())
    except BaseException as e:
        publish('status.json',dict(status='failed',error=str(e)));raise
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('responses','weather','matching','output'):p.add_argument('--'+n,required=True)
    p.add_argument('--signal',default='ping-slash24');p.add_argument('--limit-groups',type=int);run(p.parse_args())

