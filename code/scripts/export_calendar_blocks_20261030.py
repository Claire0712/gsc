"""All four frozen calendar translations, including absent and absorbed fits."""
import json,hashlib
from .summarize_stop_target_curves_20261023 import ROOT,verified
base='analysis/2026-10-30_calendar_blocks/v1/'
rows=[];diagnostics=[];dayzero=[];samples=[];unavailable=[];elapsed=[]
for key in ('minus56','minus28','plus28','plus56'):
 directory='full_'+key;summary=verified(base+directory,'summary.json');elapsed.append(summary['elapsed_seconds'])
 receipt=json.loads((ROOT/base/(directory+'.stack.verify.json')).read_text());assert receipt['status']=='verified'
 assert receipt['manifest_sha256']==hashlib.sha256((ROOT/base/directory/'manifest.json').read_bytes()).hexdigest()
 for sample in summary['signals']:
  samples.append(dict(offset=key,**sample));signal=sample['signal']
  if not sample['estimable']:unavailable.append(dict(offset=key,**sample));continue
  fit=verified(base+directory+'/'+signal,'estimates.json');inf=verified(base+key+'_'+signal+'_inference','inference.json');wild=verified(base+key+'_'+signal+'_wild','bootstrap.json')
  assert fit['signal']==inf['signal']==wild['signal']==signal
  assert fit['countries']==inf['country_clusters']==wild['countries']
  for suffix,sub in [('point',directory+'/'+signal),('inference',key+'_'+signal+'_inference'),('wild',key+'_'+signal+'_wild')]:
   r=json.loads((ROOT/base/(key+'_'+signal+'.'+suffix+'.verify.json')).read_text());assert r['status']=='verified'
   assert r['manifest_sha256']==hashlib.sha256((ROOT/base/sub/'manifest.json').read_bytes()).hexdigest()
  for outcome in ('signed','deficit','below95'):
   for i,term in enumerate(fit['terms']):
    r=dict(shift_days=sample['shift_days'],signal=signal,outcome=outcome,term=term,beta=fit['results'][outcome]['beta'][i],country_wild_basic95=wild['results'][outcome]['basic_interval95'][i],groups=fit['groups'],countries=fit['countries'],draws=wild['draws']);rows.append(r)
    if term=='heat_day_0' and outcome=='signed':dayzero.append(r)
   for covariance,report in inf['results'][outcome].items():diagnostics.append(dict(shift_days=sample['shift_days'],signal=signal,outcome=outcome,covariance=covariance,**{k:v for k,v in report.items() if k not in ('covariance','interval95')}))
assert (len(samples),len(rows),len(diagnostics),len(dayzero),len(unavailable))==(12,315,84,7,5)
target=ROOT/'deliverables/2026-10-30_CALENDAR_BLOCK_CURVES.json';assert not target.exists()
target.write_text(json.dumps(dict(scope='Posthoc supported intact15day calendar-block translations, offsets fixed -56/-28/+28/+56 days identically for all countries; source outcomes and dewpoint move together. Conditional on sparse original accepted-window calendar coverage; no wrap/imputation or rematching. Shifted pseudo-labels do not assert actual heat/nonheat status. Seven supported fits and five unavailable retained. No calibrated permutation p-value, complete country-year support, equivalence, causal or whole-study acceptance. Non-PSD records retained without repair.',samples=samples,coefficients=rows,diagnostics=diagnostics,day_zero=dayzero,unavailable=unavailable,production_seconds=elapsed),indent=2,allow_nan=False)+'\n')
print(json.dumps(dict(day_zero=dayzero,non_psd=sum(not r['psd'] for r in diagnostics),selected_daily_records=sum(r['rows'] for r in samples),production_seconds=sum(elapsed)),indent=2))
