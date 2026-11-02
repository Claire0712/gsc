"""Independent RIS covariates -> IODA active-probing pilot; no weather inputs.
Exploratory single-ASN eight-hour test. July targets never enter fitting.
"""
import json, hashlib, warnings
from pathlib import Path
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.structural import UnobservedComponents

ROOT=Path(__file__).resolve().parents[1]/'downloads/reconstruction_pilot'
raw=ROOT/'raw'
s=json.loads((raw/'ioda_AS812_2022.json').read_text())['data'][0][0]
assert s['entityCode']=='812' and s['datasource']=='ping-slash24' and s['step']==600
idx=pd.to_datetime(s['from']+np.arange(len(s['values']))*s['step'],unit='s',utc=True)
y=pd.Series(s['values'],index=idx,dtype=float)
y=y[y.index<pd.Timestamp('2022-08-01',tz='UTC')]
# Keep only bins with >=90% of expected 48 ten-minute observations.
count=y.resample('8h').count();y=y.resample('8h').mean().where(count>=44)
r=json.loads((raw/'ripe_AS812_2022.json').read_text())['data']
assert r['resolution']=='8h' and r['resource']=='812'
x=pd.DataFrame(r['ipv4']);x.index=pd.to_datetime(x.pop('timestamp'),utc=True)
# RIPE returns incremental changes, so forward-fill is its step-function encoding.
x=x.reindex(y.index.union(x.index)).sort_index().ffill().reindex(y.index)
train=y.index<pd.Timestamp('2022-07-01',tz='UTC');test=~train
assert train.sum()==183 and test.sum()==93
base=float(y[train].median());target=y/base
features=x[['address-space','prefixes']].astype(float)
mean=features[train].mean();scale=features[train].std().replace(0,1)
z=(features-mean)/scale
with warnings.catch_warnings(record=True) as caught:
 fit=UnobservedComponents(target[train],level='local level',exog=z[train]).fit(disp=False,maxiter=300)
pred=fit.get_forecast(steps=int(test.sum()),exog=z[test]);ci=np.asarray(pred.conf_int())
frame=pd.DataFrame({'observed_active_normalized':target[test], 'state_space_prediction':np.asarray(pred.predicted_mean),'lower95_model':ci[:,0],'upper95_model':ci[:,1], 'constant_training_median':1.0,'routing_ratio_proxy':x.loc[test,'address-space']/x.loc[train,'address-space'].median()})
# No fitting or tuning against the held-out month; proxy is a prespecified baseline.
def metrics(p):
 good=frame.observed_active_normalized.notna() & np.isfinite(p)
 a=frame.observed_active_normalized[good].to_numpy();b=np.asarray(p)[good]
 event=a<.8;det=b<.8
 return {'n':len(a),'mae':float(np.mean(abs(a-b))),'rmse':float(np.sqrt(np.mean((a-b)**2))), 'observed_drop_bins':int(event.sum()),'predicted_drop_bins':int(det.sum()),'drop_recall':float((event&det).sum()/event.sum()) if event.any() else None,'minimum_observed':float(a.min()),'minimum_prediction':float(b.min()),'observed_deficit_hours':float(np.maximum(0,1-a).sum()*8),'predicted_deficit_hours':float(np.maximum(0,1-b).sum()*8)}
report={'scope':'AS812 only; 8-hour bins, May-Jun 2022 training, all July 2022 held out. Not a country or historical reconstruction.', 'models':{k:metrics(frame[k]) for k in ('state_space_prediction','constant_training_median','routing_ratio_proxy')},'fit_converged':bool(fit.mle_retvals.get('converged',False)),'fit_warnings':[str(w.message) for w in caught], 'training_target_missing_bins':int(target[train].isna().sum()),'test_target_missing_bins':int(target[test].isna().sum()),'interval_coverage':float(((frame.observed_active_normalized>=frame.lower95_model)&(frame.observed_active_normalized<=frame.upper95_model))[frame.observed_active_normalized.notna()].mean()), 'historical_reconstruction_approved':False,'limitations':['Single network selected as an outage stress test, not a representative sample.','8-hour RIS series cannot validate hourly outage timing.','AS-level signals cannot substitute for country or ADM1 coverage.','Model intervals omit cross-era transfer and measurement-system uncertainty.','No Atlas result series incorporated yet; only measurement metadata acquired.','No 2018-2021 IODA observations generated.'], 'raw_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.glob('*.json')}}
frame.to_csv(ROOT/'heldout_july_predictions.csv',index_label='time_utc')
(ROOT/'validation.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps(report,indent=2))
