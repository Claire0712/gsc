"""Complete previously omitted limited M3 products; no sample re-selection."""
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
from scipy.stats import norm
from statsmodels.stats.multitest import multipletests
from .proposal_interactions import interaction_design
from .heat_associations import design,estimate
from .run_connection_baseline import Sources,Stage,_json
from .run_heat_associations import OUTCOMES

def run(a):
 start=time.monotonic();out=Path(a.output)
 if out.exists():raise FileExistsError(out)
 src=Sources();st=Stage(a.panel,src,status_key='status',manifest_key=('status','completed'));rows=_json(src.read(Path(a.panel)/'rows.json',st.manifest['outputs']['rows.json']))
 for n in ('proposal_interactions.py','run_proposal_interactions_20261101.py','heat_associations.py','event_curve_core.py','curve_inference.py','run_connection_baseline.py'):src.verify(Path(__file__).with_name(n))
 for p in (a.spec,a.plan):src.verify(Path(p))
 oldst=Stage(a.original,src,status_key='status',manifest_key=('status','completed'));old=_json(src.read(Path(a.original)/'results.json',oldst.manifest['outputs']['results.json']));old={r['signal']:r for r in old if r['setting']=='A' and r['model']=='M2'}
 out.mkdir(parents=True);publish=lambda n,v:(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n');publish('status.json',dict(status='running'));results=[];products={};links=[]
 try:
  for sig in sorted({r['signal'] for r in rows}):
   if a.signal and sig!=a.signal:continue
   rr=[r for r in rows if r['signal']==sig and r['matched_integral']];assert all(r['metrics']['full_window_complete'] and r['full_observed_unconfounded'] for r in rr)
   countries=[r['country_id'] for r in rr];base,z,_,_=design(rr,'A','M2');ys={o:np.array([np.log1p(r['metrics']['dhrd_hours']) if o=='log1p_dhrd' else r['metrics'][o] for r in rr],float) for o in OUTCOMES}
   basefits={o:estimate(base,y,z,countries,o!='log1p_dhrd') for o,y in ys.items()}
   for o,b in basefits.items():
    prior=old[sig]['results'][o];assert b['estimable']==prior['estimable'] and b['n']==prior['n'] and b['countries']==prior['countries']
    if b['estimable']:np.testing.assert_allclose(b['beta'],prior['beta'],rtol=1e-10,atol=1e-10)
   for kind in ('ntrd','dewpoint'):
    x,z,names,centering=interaction_design(rr,kind);fn=f'{sig}_{kind}.npz';np.savez_compressed(out/fn,x=x,z=z.toarray(),countries=np.array(countries),event_ids=np.array([r['event_id'] for r in rr]),**ys);products[fn]=Sources().verify(out/fn)
    fits={}
    for o,y in ys.items():
     f=estimate(x,y,z,countries,o!='log1p_dhrd');f['base_rss']=basefits[o].get('rss');f['partial_residual_variance_explained']=(f['base_rss']-f['rss'])/f['base_rss'] if f['estimable'] and f['base_rss']>0 else None
     var=f['covariance_country_cr0'][-1][-1] if f['estimable'] else None;f['interaction_p_normal_cr0']=float(2*norm.sf(abs(f['beta'][-1])/np.sqrt(var))) if var is not None and var>0 else None;fits[o]=f;links.append((sig,kind,o,f))
    results.append(dict(signal=sig,setting='A',model='M3_'+kind,kind=kind,terms=names,centering=centering,matrix=fn,results=fits))
  # Keep the declared global family size even in the one-signal pilot.
  assert len(links)<=30;p=[f['interaction_p_normal_cr0'] if f['interaction_p_normal_cr0'] is not None else 1. for _,_,_,f in links];p+= [1.]*(30-len(p));bh=multipletests(p,method='fdr_bh')[1];by=multipletests(p,method='fdr_by')[1]
  for (_,_,_,f),b,y in zip(links,bh,by):f['interaction_bh']=float(b);f['interaction_by']=float(y)
  src.check();publish('results.json',results);summary=dict(status='completed',models=len(results),outcome_cases=len(links),estimated_outcome_cases=sum(f['estimable'] for _,_,_,f in links),family_size=30,bh05=sum(f['interaction_bh']<=.05 for _,_,_,f in links),by05=sum(f['interaction_by']<=.05 for _,_,_,f in links),elapsed_seconds=time.monotonic()-start,scope='Post-hoc completion of proposal 9.3, original A/M2 rows/main effects and FE, separate centered HD×NTRD and HD×dewpoint. Normal CR0 uncertainty approximate; distinct 30-test family. No causal or predictive interpretation. Not pre-registered; all prior results had been viewed.');publish('summary.json',summary)
  for n in ('results.json','summary.json'):products[n]=Sources().verify(out/n)
  publish('manifest.json',dict(status='completed',inputs=src.entries,outputs=products));publish('status.json',dict(status='completed'));print(json.dumps(summary))
 except BaseException as e:publish('status.json',dict(status='failed',error=str(e)));raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--panel',required=True);p.add_argument('--original',required=True);p.add_argument('--output',required=True);p.add_argument('--signal');p.add_argument('--spec',default='docs/superpowers/specs/2026-11-01-proposal-interactions.md');p.add_argument('--plan',default='docs/superpowers/plans/2026-11-01-proposal-interactions.md');run(p.parse_args())
