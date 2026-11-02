"""Independent original-row, dense least-squares and country-score audit."""
import argparse,json,math,time,hashlib
from pathlib import Path
import numpy as np

def run(a):
 start=time.monotonic();p=Path(a.output);m=json.loads((p/'manifest.json').read_text());assert m['status']=='completed'
 for fn,v in m['outputs'].items():assert hashlib.sha256((p/fn).read_bytes()).hexdigest()==v['sha256']
 source=json.loads((Path(a.panel)/'rows.json').read_text());results=json.loads((p/'results.json').read_text());maxb=maxv=0.;fits=rawchecks=0;probs=[];links=[]
 for r in results:
  rows=[t for t in source if t['signal']==r['signal'] and t['matched_integral']];saved=np.load(p/r['matrix'],allow_pickle=False);old=np.load(Path(a.original)/(r['signal']+'_A_M2.npz'),allow_pickle=False)
  ids=np.array([t['event_id'] for t in rows]);countries=np.array([t['country_id'] for t in rows]);np.testing.assert_array_equal(ids,saved['event_ids']);np.testing.assert_array_equal(countries,saved['countries']);np.testing.assert_array_equal(ids,old['event_ids']);np.testing.assert_array_equal(countries,old['countries'])
  base=np.array([[t['exposure'][k] for k in ('hd_c_days','span_days','dewpoint_mean_c','ntrd_c_days')] for t in rows]);np.testing.assert_array_equal(base,old['x'])
  mod=3 if r['kind']=='ntrd' else 2;mean_h=sum(float(t[0]) for t in base)/len(base);mean_m=sum(float(t[mod]) for t in base)/len(base);interaction=np.array([(float(t[0])-mean_h)*(float(t[mod])-mean_m) for t in base]);x=np.column_stack((base,interaction));np.testing.assert_allclose(x,saved['x'],rtol=1e-13,atol=1e-10);rawchecks+=len(rows)
  keys=sorted({('country',t['country_id']) for t in rows}|{('month',t['year_month']) for t in rows});z=np.array([[int(k==('country',t['country_id']) or k==('month',t['year_month'])) for k in keys] for t in rows],float);np.testing.assert_array_equal(z,saved['z']);rank=np.linalg.matrix_rank(z);xx=x-z@np.linalg.lstsq(z,x,rcond=None)[0]
  for outcome,f in r['results'].items():
   y=np.array([math.log1p(t['metrics']['dhrd_hours']) if outcome=='log1p_dhrd' else t['metrics'][outcome] for t in rows]);np.testing.assert_allclose(y,saved[outcome],rtol=1e-14,atol=1e-14)
   if not f['estimable']:assert len(rows)-rank<=x.shape[1] and f['reason']=='No residual degrees of freedom';probs.append(1.);links.append(f);continue
   yy=y-z@np.linalg.lstsq(z,y,rcond=None)[0];b=np.linalg.lstsq(xx,yy,rcond=None)[0];res=yy-xx@b;bread=np.linalg.inv(xx.T@xx);score=np.array([np.sum(xx[countries==c]*res[countries==c,None],axis=0) for c in sorted(set(countries))]);v=bread@(score.T@score)@bread
   maxb=max(maxb,float(np.max(np.abs(b-np.array(f['beta'])))));maxv=max(maxv,float(np.max(np.abs(v-np.array(f['covariance_country_cr0'])))));np.testing.assert_allclose(b,f['beta'],rtol=1e-6,atol=1e-8);np.testing.assert_allclose(v,f['covariance_country_cr0'],rtol=1e-5,atol=1e-10);np.testing.assert_allclose(res@res,f['rss'],rtol=1e-7,atol=1e-10)
   prob=math.erfc(abs(float(b[-1]))/math.sqrt(2*float(v[-1,-1]))) if v[-1,-1]>0 else 1.;np.testing.assert_allclose(prob,f['interaction_p_normal_cr0'],rtol=1e-6,atol=1e-10);probs.append(prob);links.append(f);fits+=1
 pp=np.array(probs+[1.]*(30-len(probs)));order=np.argsort(pp);ranks=np.arange(1,31);hh=sum(1/i for i in range(1,31))
 for field,factor in [('interaction_bh',1.),('interaction_by',hh)]:
  q=np.minimum(1,np.minimum.accumulate((pp[order]*30/ranks*factor)[::-1])[::-1]);adjusted=np.empty(30);adjusted[order]=q
  for f,value in zip(links,adjusted):np.testing.assert_allclose(f[field],value,rtol=1e-6,atol=1e-10)
 rec=dict(status='verified',raw_product_rows_checked=rawchecks,estimated_outcome_fits= fits,max_beta_absolute_error=maxb,max_cov_absolute_error=maxv,elapsed_seconds=time.monotonic()-start,manifest_sha256=hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest(),scope='Independent raw-row product/identity, dense OLS and country-score CR0 plus analytic normal p and BH/BY audit. Numerical agreement is not causal or small-cluster certification.')
 out=p.parent/(p.name+'.verify.json')
 if out.exists():raise FileExistsError(out)
 out.write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps(rec))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--panel',required=True);p.add_argument('--original',required=True);run(p.parse_args())
