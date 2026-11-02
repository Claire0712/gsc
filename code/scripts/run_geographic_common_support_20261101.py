"""Proposal 9.5: fixed archived-region conditional HD slopes, immutable output."""
import argparse,csv,io,json,time,datetime,platform
from pathlib import Path
import numpy as np
from scipy.stats import norm
from statsmodels.stats.multitest import multipletests
from .geographic_common_support import joint_support,arm_counts,regional_design,DIMENSIONS,OUTCOMES
from .heat_associations_v2 import estimate
from .run_connection_baseline import Sources,Stage

def run(args):
 start=time.monotonic();out=Path(args.output)
 if out.exists():raise FileExistsError(out)
 sources=Sources();panel=Stage(args.panel,sources,status_key='status',manifest_key=('status','completed'));comp=Stage(args.comparison,sources,status_key='status',manifest_key=('status','completed'))
 rows=[r for r in panel.json('rows.json') if r['matched_integral']]
 assert all(r['metrics']['full_window_complete'] and r['full_observed_unconfounded'] for r in rows)
 metadata=json.loads(sources.read(Path('data/worldbank/countries.json'),dict(sha256='d29d57f8adf954c5e2a1520a02fb2c7b45575d8db3bd327a9dff47d66914231c')))
 assert len(metadata)==2 and metadata[0]['total']==len(metadata[1]);idx={r['id']:r for r in metadata[1]};assert len(idx)==len(metadata[1])
 labels={};mapping={}
 for r in metadata[1]:
  reg=r.get('region',{});code=reg.get('id');label=reg.get('value')
  if code and code!='NA' and label:
   if code in labels:assert labels[code]==label
   labels[code]=label;mapping[r['id']]=code
 assert len(labels)==7
 audits={}
 for r in csv.DictReader(io.StringIO(comp.read('window_audit.csv').decode())):
  key=r['window_id'],r['signal'];assert key not in audits;audits[key]=r
 for n in ['geographic_common_support.py','run_geographic_common_support_20261101.py','heat_associations_v2.py','event_curve_core.py','curve_inference.py','run_connection_baseline.py']:sources.verify(Path('scripts')/n)
 sources.verify(Path('docs/superpowers/specs/2026-11-01-geographic-common-support.md'));sources.verify(Path('tests/test_geographic_common_support.py'))
 out.mkdir(parents=True);save=lambda n,v:(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n');save('status.json',dict(status='running'));results=[];inputs=[];products={}
 for sig in ('ping-slash24','bgp','merit-nt'):
  if args.pilot and sig!='ping-slash24':continue
  rr=[];features=[];excluded=[]
  for row in rows:
   if row['signal']!=sig:continue
   a=audits['heat:'+row['event_id'],sig]
   try:f=[row['exposure'][k] for k in DIMENSIONS[:3]]+[float(a['raw_pre_level']),float(a['raw_pre_mad_over_median']),row['metrics']['coverage_fraction']]
   except (ValueError,TypeError,KeyError):f=[float('nan')]*6
   if row['country_id'] not in mapping:excluded.append(dict(event_id=row['event_id'],reason='unknown_archived_region'));continue
   if not np.isfinite(f).all():excluded.append(dict(event_id=row['event_id'],reason='nonfinite_support_predictor'));continue
   rr.append(row);features.append(f)
  f=np.array(features,float);band=np.quantile(f[:,0],[.25,.75]);scales=np.quantile(f,.75,axis=0)-np.quantile(f,.25,axis=0);keep=(f[:,0]>=band[0])&(f[:,0]<=band[1]);band_rows=[r for r,k in zip(rr,keep) if k];bf=f[keep]
  inputs.append(dict(signal=sig,dimensions=DIMENSIONS,hd_band=band.tolist(),iqr_scales=scales.tolist(),excluded=excluded,predictor_complete=[dict(event_id=r['event_id'],country_id=r['country_id'],region=mapping[r['country_id']],features=v.tolist(),in_hd_band=bool(k)) for r,v,k in zip(rr,f,keep)],country_counts=[dict(country_id=c,matched_events=sum(r['country_id']==c for r in rr),in_hd_band=sum(r['country_id']==c for r in band_rows)) for c in sorted({r['country_id'] for r in rr})]))
  for reg in sorted(labels)[:1] if args.pilot else sorted(labels):
   g=np.array([int(mapping[r['country_id']]==reg) for r in band_rows])
   for policy,cal in [('primary',.5),('strict',.25)]:
    mask,peer,distance=joint_support(bf,g,scales,cal);selected=[r for r,k in zip(band_rows,mask) if k];counts=arm_counts(selected,g[mask]);rec=dict(signal=sig,region=reg,region_label=labels[reg],policy=policy,caliper_iqr=cal,hd_band=band.tolist(),before_joint_support=arm_counts(band_rows,g),after_joint_support=counts,peers=[dict(event_id=r['event_id'],peer_event_id=band_rows[peer[i]]['event_id'],max_scaled_distance=float(distance[i])) for i,r in enumerate(band_rows) if mask[i]],selected_event_ids=[r['event_id'] for r in selected],support_passed=all(c['events']>=10 and c['countries']>=5 for c in counts),results={})
    if not rec['support_passed']:
     rec['reason']='At least one arm below 10 events or 5 countries';results.append(rec);continue
    x,z,terms=regional_design(selected,bf[mask],g[mask]);scale=np.std(x,axis=0);safe=np.where(scale>0,scale,1.);sx=x/safe;countries=[r['country_id'] for r in selected];ys={o:np.array([r['metrics'][o] for r in selected],float) for o in OUTCOMES};filename=f'{sig}_{reg}_{policy}.npz';np.savez_compressed(out/filename,x=sx,raw_x=x,scales=safe,z=z.toarray(),countries=np.array(countries),event_ids=np.array(rec['selected_event_ids']),**ys);products[filename]=sources.__class__().verify(out/filename);rec.update(matrix=filename,terms=terms,focal_scales=safe.tolist())
    for outcome,y in ys.items():
     if np.ptp(y)<=1e-12:rec['results'][outcome]=dict(estimable=False,reason='Constant outcome');continue
     fit=estimate(sx,y,z,countries,True)
     if fit['estimable']:
      beta=np.array(fit['beta'])/safe;cov=np.array(fit['covariance_country_cr0'])/np.outer(safe,safe)
      if not np.isfinite(beta).all() or not np.isfinite(cov).all() or fit['condition']>1e8 or fit['rss']<=1e-20*max(1.,float(y@y)) or np.any(np.diag(cov)<=0):fit=dict(estimable=False,reason='Numerical variation/condition/variance gate')
      else:
       var=cov[0,0]+cov[-1,-1]+2*cov[0,-1]
       if var<=0:fit=dict(estimable=False,reason='Nonpositive regional slope variance')
       else:
        se=np.sqrt(np.diag(cov));fit.update(beta=beta.tolist(),covariance_country_cr0=cov.tolist(),interval95_normal=np.column_stack([beta-1.959963984540054*se,beta+1.959963984540054*se]).tolist(),regional_hd_slope=float(beta[0]+beta[-1]),regional_hd_interval95=[float(beta[0]+beta[-1]-1.959963984540054*np.sqrt(var)),float(beta[0]+beta[-1]+1.959963984540054*np.sqrt(var))],rest_hd_slope=float(beta[0]),difference_hd_slope=float(beta[-1]),difference_p_normal=float(2*norm.sf(abs(beta[-1]/se[-1]))))
     rec['results'][outcome]=fit
    results.append(rec)
 for policy in ('primary','strict'):
  refs=[(r,o) for r in results if r['policy']==policy for o in OUTCOMES];pv=[r['results'].get(o,{}).get('difference_p_normal',1.) for r,o in refs];assert len(pv)<=63
  for method,label in [('fdr_bh','q_bh'),('fdr_by','q_by')]:
   q=multipletests(pv+[1.]*(63-len(pv)),method=method)[1]
   for (r,o),v in zip(refs,q):
    f=r['results'].get(o)
    if f and f.get('estimable'):f[label]=float(v)
 sources.check();save('support_inputs.json',inputs);save('results.json',results)
 summary=dict(status='completed',pilot=bool(args.pilot),contrasts=len(results),support_passed=sum(r['support_passed'] for r in results),fits_estimable=sum(f.get('estimable',False) for r in results for f in r['results'].values()),fixed_comparison_family_per_policy=63,elapsed_seconds=time.monotonic()-start,scope='Post-hoc archived-region HD slope contrasts within fixed observed joint support, not regional levels, country rankings, independent geographic replications or causal effects. Approximate country-CR0 normal inference; no precipitation adjustment. Unsupported fits retained.')
 save('summary.json',summary)
 for n in ['support_inputs.json','results.json','summary.json']:products[n]=sources.__class__().verify(out/n)
 save('manifest.json',dict(status='completed',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),python=platform.python_version(),numpy=np.__version__,inputs=sources.entries,outputs=products));save('status.json',dict(status='completed'));print(json.dumps(summary))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--panel',default='analysis/2026-10-13_event_panel/v1/full_outputs');p.add_argument('--comparison',default='analysis/2026-10-12_comparison_windows/v1/full_outputs');p.add_argument('--output',required=True);p.add_argument('--pilot',action='store_true');run(p.parse_args())
