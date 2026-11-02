"""Independent scalar support and augmented-OLS/CR0 reconstruction."""
from pathlib import Path
import argparse,json,csv,math,hashlib,time
import numpy as np
p=argparse.ArgumentParser();p.add_argument('path');a=p.parse_args();base=Path(a.path);started=time.monotonic();manifest=json.loads((base/'manifest.json').read_text());assert manifest['status']=='completed'
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for n,v in manifest['outputs'].items():assert digest(base/n)==v['sha256']
for n,v in manifest['inputs'].items():assert digest(n)==v['sha256'],n
inputs=json.loads((base/'support_inputs.json').read_text());results=json.loads((base/'results.json').read_text());panel=json.loads(Path('analysis/2026-10-13_event_panel/v1/full_outputs/rows.json').read_text());original={(r['signal'],r['event_id']):r for r in panel};window={}
with open('analysis/2026-10-12_comparison_windows/v1/full_outputs/window_audit.csv') as f:
 for r in csv.DictReader(f):window[r['signal'],r['window_id']]=r
metadata=json.loads(Path('data/worldbank/countries.json').read_text());regions={r['id']:r['region']['id'] for r in metadata[1]}
def quantile(values,q):
 s=sorted(values);x=(len(s)-1)*q;lo=math.floor(x);hi=math.ceil(x);return s[lo]+(s[hi]-s[lo])*(x-lo)
checks=0;audited_fits=0;max_beta=0.;max_cov=0.
for data in inputs:
 sig=data['signal'];source=[r for r in panel if r['matched_integral'] and r['signal']==sig];ids=[r['event_id'] for r in data['predictor_complete']]+[r['event_id'] for r in data['excluded']];assert len(ids)==len(set(ids)) and set(ids)=={r['event_id'] for r in source}
 rows=data['predictor_complete']
 for r in rows:
  old=original[sig,r['event_id']];w=window[sig,'heat:'+r['event_id']];expected=[old['exposure'][k] for k in ('hd_c_days','absolute_tmax_c','span_days')]+[float(w['raw_pre_level']),float(w['raw_pre_mad_over_median']),old['metrics']['coverage_fraction']];assert r['features']==expected and r['region']==regions[r['country_id']]
 band=[quantile([r['features'][0] for r in rows],q) for q in (.25,.75)];scales=[quantile([r['features'][j] for r in rows],.75)-quantile([r['features'][j] for r in rows],.25) for j in range(6)];np.testing.assert_allclose(data['hd_band'],band,rtol=1e-13,atol=1e-13);np.testing.assert_allclose(data['iqr_scales'],scales,rtol=1e-13,atol=1e-13)
 for r in rows:assert r['in_hd_band']==(band[0]<=r['features'][0]<=band[1])
 rr=[r for r in rows if r['in_hd_band']]
 for rec in [r for r in results if r['signal']==sig]:
  reg=rec['region'];cal=rec['caliper_iqr'];peers={r['event_id']:r for r in rec['peers']};selected=[]
  for r in rr:
   candidates=[]
   for other in rr:
    if (r['region']==reg)==(other['region']==reg):continue
    ds=[abs(x-y)/s if s>0 else 0. if x==y else math.inf for x,y,s in zip(r['features'],other['features'],scales)];d=max(ds)
    if d<=cal:candidates.append((d,other['event_id']))
   if candidates:
    selected.append(r);assert r['event_id'] in peers;peer=peers[r['event_id']];pd=next(d for d,i in candidates if i==peer['peer_event_id']);assert math.isclose(pd,peer['max_scaled_distance'],rel_tol=1e-12,abs_tol=1e-12);assert pd<=min(d for d,i in candidates)+1e-12
   else:assert r['event_id'] not in peers
   checks+=1
  assert [r['event_id'] for r in selected]==rec['selected_event_ids']
  counts=[dict(events=sum((r['region']==reg)==bool(g) for r in selected),countries=len({r['country_id'] for r in selected if (r['region']==reg)==bool(g)})) for g in (0,1)];assert counts==rec['after_joint_support'];assert rec['support_passed']==all(r['events']>=10 and r['countries']>=5 for r in counts)
  if not rec['support_passed']:assert not rec['results'];continue
  m=np.load(base/rec['matrix'],allow_pickle=False);old=[original[sig,r['event_id']] for r in selected];raw=np.array([[o['exposure'][k] for k in ('hd_c_days','span_days','dewpoint_mean_c','ntrd_c_days')]+[r['features'][1],r['features'][3],r['features'][4],r['features'][0]*int(r['region']==reg)] for o,r in zip(old,selected)]);np.testing.assert_allclose(m['raw_x'],raw,rtol=0,atol=0);np.testing.assert_allclose(m['x']*m['scales'],raw,rtol=1e-12,atol=1e-12)
  assert m['countries'].tolist()==[r['country_id'] for r in old] and m['event_ids'].tolist()==rec['selected_event_ids'];z=m['z'];expected_z=np.column_stack([[float(r['country_id']==c) for r in old] for c in sorted({r['country_id'] for r in old})]+[[float(r['year_month']==c) for r in old] for c in sorted({r['year_month'] for r in old})]);np.testing.assert_array_equal(z,expected_z);design=np.column_stack([z,m['x']]);rank_z=np.linalg.matrix_rank(z);rank=np.linalg.matrix_rank(design)
  for outcome,fit in rec['results'].items():
   y=np.array([r['metrics'][outcome] for r in old]);np.testing.assert_allclose(m[outcome],y,rtol=0,atol=0)
   if not fit['estimable']:
    if fit['reason']=='Constant outcome':assert np.ptp(y)<=1e-12
    elif fit['reason']=='No residual degrees of freedom':assert len(y)-rank_z<=m['x'].shape[1]
    elif fit['reason']=='Absorbed focal column':assert any(np.linalg.norm(m['x'][:,j]-z@np.linalg.lstsq(z,m['x'][:,j],rcond=None)[0])<1e-8 for j in range(m['x'].shape[1]))
    elif fit['reason']=='Focal design rank deficient':assert rank<rank_z+m['x'].shape[1]
    else:raise AssertionError('Numerical gate requires explicit independent audit: '+fit['reason'])
    continue
   beta=np.linalg.lstsq(design,y,rcond=None)[0][-m['x'].shape[1]:];res=y-design@np.linalg.lstsq(design,y,rcond=None)[0];xx=m['x']-z@np.linalg.lstsq(z,m['x'],rcond=None)[0];bread=np.linalg.inv(xx.T@xx);meat=np.zeros((len(beta),len(beta)))
   for country in set(m['countries']):
    score=xx[m['countries']==country].T@res[m['countries']==country];meat+=np.outer(score,score)
   cov=bread@meat@bread;rawbeta=beta/m['scales'];rawcov=cov/np.outer(m['scales'],m['scales']);np.testing.assert_allclose(rawbeta,fit['beta'],rtol=1e-7,atol=1e-9);np.testing.assert_allclose(rawcov,fit['covariance_country_cr0'],rtol=1e-6,atol=1e-9);max_beta=max(max_beta,float(np.max(np.abs(rawbeta-fit['beta']))));max_cov=max(max_cov,float(np.max(np.abs(rawcov-fit['covariance_country_cr0']))));audited_fits+=1
for policy in ('primary','strict'):
 refs=[(r,o) for r in results if r['policy']==policy for o in ('mean_deficit_core','maintenance_core','peak_loss_core')];pvalues=[]
 for rec,outcome in refs:
  fit=rec['results'].get(outcome,{})
  if fit.get('estimable'):
   beta=fit['beta'][-1];se=math.sqrt(fit['covariance_country_cr0'][-1][-1]);pv=math.erfc(abs(beta/se)/math.sqrt(2));assert math.isclose(pv,fit['difference_p_normal'],rel_tol=1e-8,abs_tol=1e-12);pvalues.append(pv)
  else:pvalues.append(1.)
 pvalues += [1.]*(63-len(pvalues));order=sorted(range(63),key=lambda i:pvalues[i])
 for name,mult in [('q_bh',1.),('q_by',sum(1./i for i in range(1,64)))]:
  q=[1.]*63;previous=1.
  for pos in range(62,-1,-1):
   i=order[pos];previous=min(previous,pvalues[i]*63/(pos+1)*mult);q[i]=previous
  for i,(rec,outcome) in enumerate(refs):
   fit=rec['results'].get(outcome,{})
   if fit.get('estimable'):assert math.isclose(fit[name],q[i],rel_tol=1e-8,abs_tol=1e-12)
receipt=dict(status='verified',manifest_sha256=digest(base/'manifest.json'),support_membership_checks=checks,contrasts=len(results),augmented_ols_cr0_fits_verified=audited_fits,max_beta_discrepancy=max_beta,max_cov_discrepancy=max_cov,elapsed_seconds=time.monotonic()-started,scope='Scalar observed peer/selection and original predictor checks, plus full augmented OLS/CR0 for estimable models. Not causal identification or small-cluster calibration.')
out=base.with_name(base.name+'.verify.json');assert not out.exists();out.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
