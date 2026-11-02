"""Ten-minute point objective represented by exact six-slot sufficient cells."""
import argparse,csv,io,json,time,os
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from scipy import sparse
from .hour_sufficient import summarize
from .event_curve_core import fit
from .run_connection_baseline import Sources,Stage,_json

def design(rows,x,w):
    labels=[]
    for r in rows:
        dt=datetime.fromtimestamp(int(r['date_utc']),timezone.utc)
        for hour in range(24):
            labels.append([('window',r['group_id'],r['window_id']),('group_day',r['group_id'],r['relative_day']),('country_hour_weekday',r['country_id'],hour,dt.weekday()),('year_month',dt.year,dt.month)])
    codes={k:i for i,k in enumerate(sorted({k for rr in labels for k in rr},key=str))}
    z=sparse.csr_matrix((np.ones(len(labels)*4),(np.repeat(np.arange(len(labels)),4),[codes[k] for rr in labels for k in rr])),shape=(len(labels),len(codes)))
    return np.repeat(x,24,axis=0),z,np.repeat(w*6,24)

def run(args):
    started=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError('Fresh output required')
    src=Sources();stage=Stage(args.daily,src,status_key='status',manifest_key=('status','completed'))
    def read(n):return src.read(Path(args.daily)/n,stage.manifest['outputs'][n])
    est=_json(read('estimates.json'));rows=_json(read('row_identity.json'));mp=Path(args.daily)/'model_inputs.npz';src.verify(mp,stage.manifest['outputs'][mp.name])
    with np.load(mp) as a:x0=a['x'].copy();w0=a['weights'].copy()
    from .run_variant_matching import ancestry_entry
    rp=Path(args.responses)/'manifest.json'
    src.verify(rp,ancestry_entry(stage.manifest['inputs'],rp));response=Stage(rp.parent,src,status_key='status',manifest_key=('status','completed'))
    rr=list(csv.DictReader(io.StringIO(src.read(rp.parent/'daily_1.csv',response.manifest['outputs']['daily_1.csv']).decode())))
    key=lambda r:(r['group_id'],r['window_id'],r['country_id'],str(r['date_utc']))
    lookup={key(r):r for r in rr if r['signal']==est['signal'] and r['purpose']=='curve'}
    paths={Path(p).name:Path(p) for p in response.manifest['inputs'] if p.endswith('.npz')}
    ys={n:[] for n in ('signed','deficit','below95')};within={n:[] for n in ys};identity=[]
    out.mkdir(parents=True)
    def publish(n,obj):(out/n).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
    publish('status.json',dict(status='running',pid=os.getpid(),stage='prepare',daily_rows=len(rows)))
    try:
        for i,r in enumerate(rows):
            q=lookup[key(r)];p=paths[Path(q['point_file']).name];src.verify(p,response.manifest['inputs'][str(p)])
            with np.load(p) as a:
                if str(a['window_id'])!=r['window_id'] or str(a['signal'])!=est['signal']:raise ValueError('Point identity mismatch')
                h=summarize(a['target_timestamps'],a['target_values'],a['baseline'],a['target_technical_available'],int(r['date_utc']))
            if float(q['weight'])!=w0[i]:raise ValueError('Weight lineage mismatch')
            for name in ys:
                np.testing.assert_allclose(h[name].mean(),float(q[name]),atol=1e-12,rtol=1e-10)
                ys[name].extend(h[name]);within[name].extend(h[name+'_within_ss'])
            identity.extend([dict(r,hour=hour) for hour in range(24)])
        x,z,w=design(rows,x0,w0);results={}
        for name in ys:
            publish('status.json',dict(status='running',pid=os.getpid(),stage='fit',outcome=name,rows=len(w)))
            ys[name]=np.array(ys[name]);within[name]=np.array(within[name]);f=fit(x,ys[name],z,w)
            ss=float(f['residual']@f['residual']);extra=float((w/6)@within[name])
            results[name]=dict(beta=f['beta'].tolist(),condition=f['condition'],projection=f['projection'],weighted_residual_ss=ss,within_cell_weighted_ss=extra,full_slot_weighted_residual_ss=ss+extra)
        for name in ('run_variant_hour_curve.py','run_variant_matching.py','hour_sufficient.py','event_curve_core.py','run_connection_baseline.py'):src.verify(Path(__file__).parent/name)
        src.check()
        np.savez_compressed(out/'model_inputs.npz',x=x,weights=w,z_data=z.data,z_indices=z.indices,z_indptr=z.indptr,z_shape=z.shape,**ys,**{n+'_within_ss':v for n,v in within.items()})
        publish('row_identity.json',identity)
        publish('estimates.json',dict(signal=est['signal'],rows=len(w),raw_slot_rows=len(w)*6,groups=est['groups'],countries=est['countries'],terms=est['terms'],reference_day=-1,results=results,elapsed_seconds=time.monotonic()-started,scope='Exact ten-minute point objective compressed within UTC hour; country hour-weekday effects, daily dewpoint, no precipitation; inference not yet verified.'))
        products={n:Sources().verify(out/n) for n in ('model_inputs.npz','row_identity.json','estimates.json')}
        publish('manifest.json',dict(status='completed',inputs=src.entries,outputs=products));publish('status.json',dict(status='completed'))
        print(json.dumps(dict(rows=len(w),raw_slot_rows=len(w)*6,elapsed_seconds=time.monotonic()-started)))
    except BaseException as exc:
        publish('status.json',dict(status='failed',error=str(exc)));raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--daily',required=True);p.add_argument('--responses',required=True);p.add_argument('--output',required=True);run(p.parse_args())

