import argparse,json,time
from pathlib import Path
import numpy as np
from scipy import sparse
from .event_curve_core import fit
from .curve_inference import covariance,diagnostics
from .run_connection_baseline import Sources,Stage,_json
def run(args):
    started=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError('Fresh output required')
    sources=Sources();stage=Stage(args.estimates,sources,status_key='status',manifest_key=('status','completed'))
    def read(n):return sources.read(Path(args.estimates)/n,stage.manifest['outputs'][n])
    estimates=_json(read('estimates.json'));rows=_json(read('row_identity.json'));path=Path(args.estimates)/'model_inputs.npz';sources.verify(path,stage.manifest['outputs'][path.name])
    countries=[r['country_id'] for r in rows];day=np.array([int(r['date_utc'])//86400 for r in rows]);ng=len(set(countries))
    clusters={'country':countries}
    for length in (7,14,28):
        block=((day-4)//length).tolist();clusters['block'+str(length)]=block;clusters['intersection'+str(length)]=list(zip(countries,block))
    result={};arrays={}
    with np.load(path,allow_pickle=False) as z:
        nuisance=sparse.csr_matrix((z['z_data'],z['z_indices'],z['z_indptr']),shape=tuple(z['z_shape']))
        for outcome,old in estimates['results'].items():
            f=fit(z['x'],z[outcome],nuisance,z['weights']);np.testing.assert_allclose(f['beta'],old['beta'],atol=1e-10,rtol=1e-9)
            xx,u=f['residualized_x'],f['residual'];covs={k:covariance(xx,u,g) for k,g in clusters.items()}
            report={'country':covs['country']}
            for length in (7,14,28):report['country_block'+str(length)]=covs['country']+covs['block'+str(length)]-covs['intersection'+str(length)]
            result[outcome]={k:dict(covariance=v.tolist(),**diagnostics(f['beta'],v,list(range(6)))) for k,v in report.items()}
            arrays[outcome+'_x']=xx;arrays[outcome+'_u']=u
    for n in ('curve_inference.py','run_curve_inference.py','event_curve_core.py','run_connection_baseline.py'):sources.verify(Path(__file__).parent/n)
    sources.check();out.mkdir(parents=True)
    def publish(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    np.savez_compressed(out/'scores_inputs.npz',**arrays)
    publish('inference.json',dict(signal=estimates['signal'],country_clusters=ng,few_country_clusters=ng<30,cluster_counts={k:len(set(g)) for k,g in clusters.items()},results=result,elapsed_seconds=time.monotonic()-started,scope='CR0 asymptotic diagnostics, normal intervals/chi-square lead tests. No finite-sample correction, wild bootstrap or final causal inference. Non-PSD matrices not repaired.'))
    products={n:Sources().verify(out/n) for n in ('scores_inputs.npz','inference.json')}
    publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products));publish('status.json',dict(status='completed'))
    print(json.dumps(dict(signal=estimates['signal'],country_clusters=ng,elapsed_seconds=time.monotonic()-started,psd={o:{k:r['psd'] for k,r in vv.items()} for o,vv in result.items()})))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--estimates',required=True);p.add_argument('--output',required=True);run(p.parse_args())
