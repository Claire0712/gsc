"""All six precipitation nested daily curve models, hash checked without selection."""
import json,hashlib
from .summarize_stop_target_curves_20261023 import ROOT,verified
base='analysis/2026-10-29_precip_curve/v1/'
stack=json.loads((ROOT/base/'full_outputs.stack.verify.json').read_text());assert stack['status']=='verified'
assert stack['manifest_sha256']==hashlib.sha256((ROOT/base/'full_outputs/manifest.json').read_bytes()).hexdigest()
rows=[];diagnostics=[];dayzero=[]
for signal in ('ping-slash24','bgp','merit-nt'):
 for model in ('base','precip'):
  key=signal+'_'+model
  fit=verified(base+'full_outputs/'+key,'estimates.json')
  inf=verified(base+key+'_inference','inference.json')
  wild=verified(base+key+'_wild','bootstrap.json')
  assert fit['signal']==inf['signal']==wild['signal']==signal
  assert fit['countries']==inf['country_clusters']==wild['countries']
  for suffix,directory in [('point','full_outputs/'+key),('inference',key+'_inference'),('wild',key+'_wild')]:
   receipt=json.loads((ROOT/base/(key+'.'+suffix+'.verify.json')).read_text())
   assert receipt['status']=='verified'
   assert receipt['manifest_sha256']==hashlib.sha256((ROOT/base/directory/'manifest.json').read_bytes()).hexdigest()
  assert len(fit['terms'])==(15 if model=='base' else 16)
  for outcome in ('signed','deficit','below95'):
   for i,term in enumerate(fit['terms']):
    row=dict(signal=signal,model=model,outcome=outcome,term=term,beta=fit['results'][outcome]['beta'][i],country_wild_basic95=wild['results'][outcome]['basic_interval95'][i],groups=fit['groups'],countries=fit['countries'],draws=wild['draws'])
    rows.append(row)
    if outcome=='signed' and term=='heat_day_0':dayzero.append(row)
   for covariance,report in inf['results'][outcome].items():diagnostics.append(dict(signal=signal,model=model,outcome=outcome,covariance=covariance,**{k:v for k,v in report.items() if k not in ('covariance','interval95')}))
assert len(rows)==279 and len(diagnostics)==72 and len(dayzero)==6
output=ROOT/'deliverables/2026-10-29_PRECIPITATION_DAILY_CURVES.json';assert not output.exists()
output.write_text(json.dumps(dict(scope='Identical95percent finite-population-supported original paired daily samples, before/after daily precipitation accumulation covariate. Daily sensitivity design, not primary ten-minute design. All terms/outcomes/diagnostics retained, non-PSD not repaired. Country wild basic intervals are nonstudentized, unadjusted; six Telescope countries cannot support strong inference. Not causal, equivalence, whole-study acceptance or precipitation-adjusted dose/Cox models.',coefficients=rows,diagnostics=diagnostics,day_zero=dayzero),indent=2,allow_nan=False)+'\n')
for r in dayzero:print(json.dumps(r))
