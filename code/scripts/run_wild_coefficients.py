import argparse,json,time
from pathlib import Path
import numpy as np
from .wild_coefficients import draws
from .run_connection_baseline import Sources,Stage,_json
def run(args):
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError('Fresh output required')
    sources=Sources();stage=Stage(args.inference,sources,status_key='status',manifest_key=('status','completed'))
    ip=Path(args.inference)/'scores_inputs.npz';sources.verify(ip,stage.manifest['outputs'][ip.name])
    ep=next(Path(p) for p in stage.manifest['inputs'] if p.endswith('/estimates.json'));rp=next(Path(p) for p in stage.manifest['inputs'] if p.endswith('/row_identity.json'))
    est=_json(sources.read(ep,stage.manifest['inputs'][str(ep)]));rows=_json(sources.read(rp,stage.manifest['inputs'][str(rp)]));groups=[r['country_id'] for r in rows]
    arrays={};report={}
    with np.load(ip,allow_pickle=False) as z:
        for outcome,r in est['results'].items():
            delta,signs=draws(z[outcome+'_x'],z[outcome+'_u'],groups)
            q=np.quantile(delta,[.025,.975],axis=0,method='linear');beta=np.array(r['beta'])
            report[outcome]=dict(basic_interval95=np.c_[beta-q[1],beta-q[0]].tolist())
            arrays[outcome+'_delta']=delta
    arrays['signs']=signs
    for name in ('wild_coefficients.py','run_wild_coefficients.py','run_connection_baseline.py'):sources.verify(Path(__file__).parent/name)
    sources.check();out.mkdir(parents=True)
    def publish(n,obj):(out/n).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
    np.savez_compressed(out/'draws.npz',**arrays)
    publish('bootstrap.json',dict(signal=est['signal'],countries=len(set(groups)),draws=len(signs),enumerated=len(set(groups))<=16,seed=20261013,results=report,elapsed_seconds=time.monotonic()-start,scope='Unrestricted country Rademacher residual bootstrap, basic nonstudentized coefficient intervals. Not restricted-null tests, studentized intervals, causal randomization or multiway inference. Full sign enumeration is not a finite-sample validity guarantee.'))
    products={n:Sources().verify(out/n) for n in ('draws.npz','bootstrap.json')}
    publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products));publish('status.json',dict(status='completed'))
    print(json.dumps(dict(signal=est['signal'],draws=len(signs),countries=len(set(groups)),elapsed_seconds=time.monotonic()-start)))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inference',required=True);p.add_argument('--output',required=True);run(p.parse_args())
