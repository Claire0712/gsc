"""Country WCU and retrospective full-family CR0 multiplicity diagnostics."""
import argparse,io,json,time
from pathlib import Path
import numpy as np
from scipy import sparse
from scipy.stats import norm
from statsmodels.stats.multitest import multipletests
from .event_curve_core import fit
from .wild_coefficients import draws
from .run_connection_baseline import Sources,Stage,_json

def marginal_p(beta,variance):
    if not np.isfinite(beta) or not np.isfinite(variance) or variance<0:raise ValueError('Invalid marginal inputs')
    return None if variance==0 else float(2*norm.sf(abs(beta)/np.sqrt(variance)))

def run(args):
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources();stage=Stage(args.models,sources,status_key='status',manifest_key=('status','completed'))
    models=_json(sources.read(Path(args.models)/'results.json',stage.manifest['outputs']['results.json']))
    records=[];arrays={}
    for m in models:
        with np.load(io.BytesIO(sources.read(Path(args.models)/m['matrix'],stage.manifest['outputs'][m['matrix']])),allow_pickle=False) as a:
            for outcome,est in m['results'].items():
                key='_'.join([m['signal'],m['setting'],m['model'],outcome]);interval=None
                if est['estimable']:
                    f=fit(a['x'],a[outcome],sparse.csr_matrix(a['z']),np.ones(len(a[outcome])))
                    np.testing.assert_allclose(f['beta'],est['beta'],atol=1e-10,rtol=1e-8)
                    delta,signs=draws(f['residualized_x'],f['residual'],a['countries'].tolist())
                    arrays[key]=delta;quant=np.quantile(delta,[.025,.975],axis=0)
                    beta=np.array(est['beta']);interval=np.column_stack([beta-quant[1],beta-quant[0]])
                for j,term in enumerate(m['terms']):
                    p=marginal_p(est['beta'][j],est['covariance_country_cr0'][j][j]) if est['estimable'] else None
                    records.append(dict(key=key,signal=m['signal'],setting=m['setting'],model=m['model'],outcome=outcome,term=term,estimable=est['estimable'],beta=est['beta'][j] if est['estimable'] else None,p_normal_cr0=p,p_for_adjustment=1. if p is None else p,wcu_basic95=interval[j].tolist() if interval is not None else None,draws=len(delta) if interval is not None else None))
    pp=[r['p_for_adjustment'] for r in records]
    for method in ('fdr_bh','fdr_by'):
        adjusted=multipletests(pp,method=method)[1]
        for r,v in zip(records,adjusted):r[method]=float(v)
    for name in ('run_heat_inference.py','event_curve_core.py','wild_coefficients.py','run_connection_baseline.py'):sources.verify(Path(__file__).parent/name)
    sources.check();out.mkdir(parents=True)
    def publish(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    np.savez_compressed(out/'draws.npz',**arrays);publish('inference.json',records)
    report=dict(status='completed',family_size=len(records),estimable_coefficients=sum(r['estimable'] for r in records),outcome_bootstraps=len(arrays),bh_below_05=sum(r['fdr_bh']<.05 for r in records),by_below_05=sum(r['fdr_by']<.05 for r in records),elapsed_seconds=time.monotonic()-start,scope='Retrospective full family of all slope/outcome/model/signal tests. Non-estimable p=1 only for adjustment; no estimate imputed. Normal CR0 p-values; BH/BY cannot fix marginal calibration. Country WCU basic marginal intervals nonstudentized, unrestricted, unadjusted for multiplicity, seed20261013 and9999 signs. Not causal, joint-test or small-sample certification.')
    publish('summary.json',report);publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs={n:Sources().verify(out/n) for n in ('draws.npz','inference.json','summary.json')}));publish('status.json',dict(status='completed'));print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--models',required=True);p.add_argument('--output',required=True);run(p.parse_args())
