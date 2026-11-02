"""Export every supported negative-control coefficient and diagnostic."""
import json,hashlib
from .summarize_stop_target_curves_20261023 import ROOT,verified
base='analysis/2026-10-29_nonheat_placebo/v1/'
stack=json.loads((ROOT/base/'full_outputs.stack.verify.json').read_text());assert stack['status']=='verified'
assert stack['manifest_sha256']==hashlib.sha256((ROOT/base/'full_outputs/manifest.json').read_bytes()).hexdigest()
summary=verified(base+'full_outputs','summary.json');rows=[];diagnostics=[];dayzero=[];unsupported=[]
for report in summary['signals']:
 signal=report['signal']
 if not report['estimable']:
  unsupported.append(report);continue
 fit=verified(base+'full_outputs/'+signal,'estimates.json');inf=verified(base+signal+'_inference','inference.json');wild=verified(base+signal+'_wild','bootstrap.json')
 assert fit['signal']==inf['signal']==wild['signal']==signal
 assert fit['countries']==inf['country_clusters']==wild['countries']
 for suffix,directory in [('point','full_outputs/'+signal),('inference',signal+'_inference'),('wild',signal+'_wild')]:
  receipt=json.loads((ROOT/base/(signal+'.'+suffix+'.verify.json')).read_text());assert receipt['status']=='verified'
  assert receipt['manifest_sha256']==hashlib.sha256((ROOT/base/directory/'manifest.json').read_bytes()).hexdigest()
 assert len(fit['terms'])==15
 for outcome in ('signed','deficit','below95'):
  for i,term in enumerate(fit['terms']):
   r=dict(signal=signal,outcome=outcome,term=term,beta=fit['results'][outcome]['beta'][i],country_wild_basic95=wild['results'][outcome]['basic_interval95'][i],groups=fit['groups'],countries=fit['countries'],draws=wild['draws']);rows.append(r)
   if outcome=='signed' and term=='heat_day_0':dayzero.append(r)
  for covariance,report in inf['results'][outcome].items():diagnostics.append(dict(signal=signal,outcome=outcome,covariance=covariance,**{k:v for k,v in report.items() if k not in ('covariance','interval95')}))
assert (len(rows),len(diagnostics),len(dayzero),len(unsupported))==(90,24,2,1)
target=ROOT/'deliverables/2026-10-30_NONHEAT_PLACEBO_CURVES.json';assert not target.exists()
target.write_text(json.dumps(dict(scope='Posthoc earliest original nonheat control as pseudo-anchor vs later nonoverlapping original controls. Controls were matched to actual heat rather than freshly to pseudo-anchor. Original actual heat rows excluded. Country wild intervals nonstudentized/unadjusted; null results do not prove identification. Not separate calendar-block-shift placebo, primary heat effect or whole-study acceptance. Non-PSD diagnostics retained.',samples=summary['signals'],coefficients=rows,diagnostics=diagnostics,day_zero=dayzero,unavailable=unsupported),indent=2,allow_nan=False)+'\n')
print(json.dumps(dict(day_zero=dayzero,diagnostics=diagnostics),indent=2))
