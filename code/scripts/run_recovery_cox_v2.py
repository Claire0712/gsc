"""Conditional recovery associations on qualified positive followup."""
import argparse,json,time,warnings
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.stats import chi2
from statsmodels.duration.hazard_regression import PHReg
from .recovery_cox import objective
from .cox_fit_health import assess
from .run_connection_baseline import Sources,Stage

def run(args):
    started=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources();stage=Stage(args.qualified,sources,status_key='status',manifest_key=('status','completed'));rows=stage.json('rows.json')
    if args.signal:rows=[r for r in rows if r['signal']==args.signal]
    out.mkdir(parents=True);results=[];products={}
    def publish(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    publish('status.json',dict(status='running'))
    for signal in sorted({r['signal'] for r in rows}):
        for sample in ('primary','complete72'):
            rr=[r for r in rows if r['signal']==signal and r['qualified']['risk_eligible'] and r['qualified']['recovery']['followup_hours']>0 and (sample=='primary' or r['qualified']['full_window_clean_complete'])]
            events=sum(r['qualified']['recovery']['status']=='confirmed' for r in rr)
            before=len(rr)
            if events:
                first=min(r['qualified']['recovery']['followup_hours'] for r in rr if r['qualified']['recovery']['status']=='confirmed')
                rr=[r for r in rr if r['qualified']['recovery']['followup_hours']>=first]
            for model in ('M1','M2'):
                terms=['hd_c_days','span_days','dewpoint_mean_c']+(['ntrd_c_days'] if model=='M2' else [])
                record=dict(signal=signal,sample=sample,model=model,terms=terms,eligible_positive_rows=before,uninformative_early_censored=before-len(rr),rows=len(rr),events=events,countries=len({r['country_id'] for r in rr}),exploratory_sparse=events<30)
                if events<=len(terms):results.append(dict(record,estimable=False,reason='Insufficient recovery endpoints'));continue
                x=np.array([[r['exposure'][k] for k in terms] for r in rr]);center=x.mean(axis=0);scale=x.std(axis=0);t=np.array([r['qualified']['recovery']['followup_hours'] for r in rr]);d=np.array([r['qualified']['recovery']['status']=='confirmed' for r in rr],dtype=int);groups=np.array([r['country_id'] for r in rr])
                if np.any(scale==0):results.append(dict(record,estimable=False,reason='Constant covariate'));continue
                z=(x-center)/scale
                if np.linalg.matrix_rank(z)<len(terms):results.append(dict(record,estimable=False,reason='Rank deficient covariates'));continue
                fitmodel=PHReg(t,z,status=d,ties='breslow')
                try:
                    with warnings.catch_warnings(record=True) as ww:
                        fitted=fitmodel.fit(groups=groups,disp=False,maxiter=200)
                    b=fitted.params;score=fitmodel.score(b);cov=fitted.cov_params()
                    health=assess(b,score,cov,-fitmodel.hessian(b),[str(w.message) for w in ww])
                except (np.linalg.LinAlgError, ValueError, FloatingPointError) as exc:
                    health='Numerical fit failure: '+str(exc)
                if health:
                    results.append(dict(record,estimable=False,reason=health))
                    continue
                raw=b/scale;se=np.sqrt(np.diag(cov))/scale
                ph=minimize(lambda bb:objective(bb,z,t,d,True),np.r_[b,np.zeros(len(b))],jac=True,method='BFGS',options=dict(gtol=1e-7,maxiter=1000))
                ph_ok=bool(np.isfinite(ph.fun) and np.linalg.norm(ph.jac,np.inf)<1e-5)
                lr=max(0.,2*(-ph.fun-fitmodel.loglike(b))) if ph_ok else None
                file=f'{signal}_{sample}_{model}.npz';np.savez_compressed(out/file,x=x,z=z,center=center,scale=scale,t=t,d=d,groups=groups,ids=np.array([r['event_id'] for r in rr]),beta=b,cov=cov,ph_beta=ph.x,ph_gradient=ph.jac)
                products[file]=Sources().verify(out/file)
                results.append(dict(record,estimable=True,matrix=file,beta_per_original_unit=raw.tolist(),hazard_ratio=np.exp(raw).tolist(),hazard_ratio95=np.exp(np.column_stack([raw-1.959963984540054*se,raw+1.959963984540054*se])).tolist(),loglike=float(fitmodel.loglike(b)),score_max=float(np.max(np.abs(score))),warnings=[str(w.message) for w in ww],ph_diagnostic=dict(converged=ph_ok,lr=lr,df=len(b),p_asymptotic=float(chi2.sf(lr,len(b))) if ph_ok else None)))
    for n in ('recovery_cox.py','run_recovery_cox_v2.py','cox_fit_health.py','run_connection_baseline.py'):sources.verify(Path(__file__).parent/n)
    sources.check();publish('results.json',results);report=dict(status='completed',models=len(results),estimable=sum(r['estimable'] for r in results),elapsed_seconds=time.monotonic()-started,scope='Conditional end-damaged recovery, country sandwich Cox Breslow; M1/M2 same sample, complete72 sensitivity conditions on future completeness. No country FE/calendar strata, no causal or unconditional resilience claim. Sparse AP exploratory; PH LR diagnostic asymptotic, not cluster-robust. No multiplicity correction or AFT fitted.')
    publish('summary.json',report)
    for n in ('results.json','summary.json'):products[n]=Sources().verify(out/n)
    publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products));publish('status.json',dict(status='completed'));print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--qualified',required=True);p.add_argument('--output',required=True);p.add_argument('--signal');run(p.parse_args())

