"""Coverage-aware multi-probe summary and fixed linear development comparison."""
import gzip,json,hashlib,warnings
from pathlib import Path
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.structural import UnobservedComponents
ROOT=Path(__file__).resolve().parents[1]/'downloads/reconstruction_pilot'
EXP=ROOT/'expanded_cohort'
selection=json.loads((EXP/'selection.json').read_text())
rows=[]
for p in sorted(EXP.glob('msm*.json.gz')):
 for r in json.loads(gzip.decompress(p.read_bytes())):
  rows.append((r['timestamp'],r['prb_id'],r['msm_id'],r.get('sent',0),r.get('rcvd',0)))
assert len(list(EXP.glob('msm*.json.gz')))==6
x=pd.DataFrame(rows,columns=['timestamp','probe','measurement','sent','received'])
assert not x.duplicated(['timestamp','probe','measurement']).any()
x['bin']=pd.to_datetime(x.timestamp,unit='s',utc=True).dt.floor('8h')
a=x.groupby(['bin','probe','measurement']).agg(sent=('sent','sum'),received=('received','sum'),records=('timestamp','size'))
a['success']=(a.received/a.sent).where((a.sent>0)&(a.records>=108))
# A probe enters only when BOTH destinations have >=90% of expected 120 reports.
b=a.success.unstack('measurement')
valid=b.notna().all(axis=1)
b['both_destination_success']=b.mean(axis=1).where(valid)
f=b['both_destination_success'].groupby('bin').agg(['median','mean','count'])
minimum=int(np.ceil(.8*len(selection['probe_ids'])))
f['robust_atlas_success']=f['median'].where(f['count']>=minimum)
f.to_csv(EXP/'coverage_and_success_8h.csv',index_label='time_utc')
a.to_csv(EXP/'probe_target_8h.csv')
s=json.loads((ROOT/'raw/ioda_AS812_2022.json').read_text())['data'][0][0]
y=pd.Series(s['values'],index=pd.to_datetime(s['from']+np.arange(len(s['values']))*s['step'],unit='s',utc=True),dtype=float).loc[:'2022-07-31 23:59:59']
n=y.resample('8h').count();y=y.resample('8h').mean().where(n>=44)
train=y.index<pd.Timestamp('2022-07-01',tz='UTC');test=~train
target=y/y[train].median()
r=pd.DataFrame(json.loads((ROOT/'raw/ripe_AS812_2022.json').read_text())['data']['ipv4']);r.index=pd.to_datetime(r.pop('timestamp'),utc=True)
r=r.reindex(r.index.union(y.index)).sort_index().ffill().reindex(y.index)
features=r[['address-space','prefixes']].astype(float).assign(atlas_robust=f.robust_atlas_success.reindex(y.index))
report={'scope':'AS812 21-probe two-target DEVELOPMENT comparison, not independent validation or historical IODA reconstruction','records':len(x),'selection_minimum_probes':minimum,'bins_failing_coverage':int(features.atlas_robust.isna().sum()),'historical_backfill_approved':False,'limitations':['Only one ASN and one previously viewed outage, no global validation.','Probe silence remains missing; sustained disappearance is not counted as failed ping.','Per-probe and per-bin reporting thresholds can select reporting survivors.','Median is a typical-probe measure, not IP-space-weighted reachability.','No temperature inputs or generated IODA observations.']}
def metrics(p):
 truth=target[test];good=truth.notna()&p.notna();truth=truth[good];p=p[good]
 return {'n':int(good.sum()),'mae':float(abs(truth-p).mean()),'rmse':float(np.sqrt(((truth-p)**2).mean())),'minimum_prediction':float(p.min()),'observed_drop_bins':int((truth<.8).sum()),'detected_drop_bins':int(((truth<.8)&(p<.8)).sum()),'false_positive_bins':int(((truth>=.8)&(p<.8)).sum()),'observed_deficit_hours':float(np.maximum(0,1-truth).sum()*8),'predicted_deficit_hours':float(np.maximum(0,1-p).sum()*8)}
out=pd.DataFrame({'observed':target[test],'robust_atlas_proxy':features.loc[test,'atlas_robust']/features.loc[train,'atlas_robust'].median()})
report['models']={'robust_atlas_proxy':metrics(out.robust_atlas_proxy)}
if features.notna().all().all():
 z=(features-features[train].mean())/features[train].std().replace(0,1)
 with warnings.catch_warnings(record=True) as caught:
  fit=UnobservedComponents(target[train],level='local level',exog=z[train]).fit(disp=False,maxiter=500)
 out['robust_fusion']=np.asarray(fit.get_forecast(int(test.sum()),exog=z[test]).predicted_mean)
 report.update(fit_converged=bool(fit.mle_retvals.get('converged',False)),warnings=[str(w.message) for w in caught])
 report['models']['robust_fusion']=metrics(out.robust_fusion)
else:report['fit_skipped']='Covariates fail predeclared coverage; no interpolation of missing measurements.'
out.to_csv(EXP/'july_development_comparison.csv',index_label='time_utc')
report['raw_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in EXP.glob('msm*.json.gz')}
(EXP/'validation.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps(report,indent=2))
