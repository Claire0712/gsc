"""Re-fit all original risk sets once, audit fixed numerical tolerance policies."""
import argparse,json,time,warnings
from pathlib import Path
import numpy as np
from statsmodels.duration.hazard_regression import PHReg
from .run_connection_baseline import Sources,Stage
from .cox_health_sensitivity import decisions,POLICIES
def run(a):
 start=time.monotonic();out=Path(a.output);assert not out.exists();sources=Sources()
 stage=Stage(a.source,sources,status_key='status',manifest_key=('status','completed'));original=stage.json('results.json')
 p=next(Path(n) for n in stage.manifest['inputs'] if n.endswith('/rows.json'))
 rows=json.loads(sources.read(p,stage.manifest['inputs'][str(p)]));result=[];payload=[]
 out.mkdir(parents=True);save=lambda n,d:(out/n).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
 save('status.json',dict(status='running'))
 for old in original:
  if a.signal and old['signal']!=a.signal:continue
  r={k:old[k] for k in ('signal','sample','model','terms')};r.update(original_estimable=old['estimable'])
  rr=[v for v in rows if v['signal']==old['signal'] and v['qualified']['risk_eligible'] and v['qualified']['recovery']['followup_hours']>0 and (old['sample']=='primary' or v['qualified']['full_window_clean_complete'])]
  events=[v['qualified']['recovery']['followup_hours'] for v in rr if v['qualified']['recovery']['status']=='confirmed']
  r.update(events=len(events),decisions={k:False for k in POLICIES})
  if len(events)<=len(old['terms']):r['reason']='Insufficient recovery endpoints';result.append(r);continue
  rr=[v for v in rr if v['qualified']['recovery']['followup_hours']>=min(events)]
  x=np.array([[v['exposure'][k] for k in old['terms']] for v in rr]);scale=x.std(axis=0)
  if np.any(scale==0) or np.linalg.matrix_rank(x-x.mean(axis=0))<len(old['terms']):r['reason']='Constant or rank deficient covariates';result.append(r);continue
  z=(x-x.mean(axis=0))/scale;t=np.array([v['qualified']['recovery']['followup_hours'] for v in rr]);d=np.array([v['qualified']['recovery']['status']=='confirmed' for v in rr],int)
  try:
   model=PHReg(t,z,status=d,ties='breslow')
   with warnings.catch_warnings(record=True) as ww:f=model.fit(groups=np.array([v['country_id'] for v in rr]),disp=False,maxiter=200)
   b=f.params;cov=f.cov_params();score=model.score(b);info=-model.hessian(b);messages=[str(w.message) for w in ww]
   r['decisions']=decisions(b,score,cov,info,messages);r['warnings']=messages
   if all(np.isfinite(v).all() for v in (b,cov,score,info)):
    ev=np.linalg.eigvalsh((info+info.T)/2);r.update(score_max=float(np.max(np.abs(score))),information_min=float(ev[0]),information_max=float(ev[-1]),beta_per_original_unit=(b/scale).tolist())
    payload.append(dict(identity=[old[k] for k in ('signal','sample','model')],z=z.tolist(),t=t.tolist(),d=d.tolist(),beta=b.tolist(),cov=cov.tolist(),score=score.tolist(),information=info.tolist(),warnings=messages))
   else:r['reason']='Nonfinite fit diagnostics'
  except (ValueError,np.linalg.LinAlgError,FloatingPointError) as e:r['reason']='Numerical exception: '+str(e)
  result.append(r)
 for r in result:assert r['decisions']['main']==r['original_estimable'],r
 for n in ('run_cox_health_sensitivity.py','cox_health_sensitivity.py'):sources.verify(Path(__file__).with_name(n))
 sources.check();save('results.json',result);save('diagnostic_fits.json',payload)
 save('summary.json',dict(models=len(result),accepted={k:sum(r['decisions'][k] for r in result) for k in POLICIES},policies=POLICIES,elapsed_seconds=time.monotonic()-start,scope='Primary study only; numerical tolerance audit, not new scientific effects, validation of other sensitivity families or inferential/whole-study acceptance. Original main policy and outputs unchanged.'))
 save('manifest.json',dict(status='completed',inputs=sources.entries,outputs={n:Sources().verify(out/n) for n in ('results.json','diagnostic_fits.json','summary.json')}));save('status.json',dict(status='completed'));print((out/'summary.json').read_text())
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--signal');run(p.parse_args())
