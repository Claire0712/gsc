"""Development comparison: add contemporaneous Atlas observations; no weather.
July was inspected in the preceding pilot and is not an independent final test.
"""
import json, hashlib, warnings
from pathlib import Path
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.structural import UnobservedComponents
ROOT=Path(__file__).resolve().parents[1]/'downloads/reconstruction_pilot'
raw=ROOT/'raw'
s=json.loads((raw/'ioda_AS812_2022.json').read_text())['data'][0][0]
assert s['entityCode']=='812' and s['step']==600
idx=pd.to_datetime(s['from']+np.arange(len(s['values']))*600,unit='s',utc=True)
y=pd.Series(s['values'],index=idx,dtype=float).loc[:'2022-07-31 23:59:59']
counts=y.resample('8h').count(); y=y.resample('8h').mean().where(counts>=44)
r=json.loads((raw/'ripe_AS812_2022.json').read_text())['data']
x=pd.DataFrame(r['ipv4']); x.index=pd.to_datetime(x.pop('timestamp'),utc=True)
x=x.reindex(y.index.union(x.index)).sort_index().ffill().reindex(y.index)
a=pd.read_csv(ROOT/'atlas_8h_observation_audit.csv',index_col=0,parse_dates=True).reindex(y.index)
# Require measured packets and all three probes; do not interpret silence as failure.
assert (a.sent>0).all() and (a.probes==3).all() and a.packet_success_observed.notna().all()
train=y.index<pd.Timestamp('2022-07-01',tz='UTC'); test=~train
target=y/y[train].median()
features=x[['address-space','prefixes']].astype(float).assign(atlas_packet_success=a.packet_success_observed)
z=(features-features[train].mean())/features[train].std().replace(0,1)
with warnings.catch_warnings(record=True) as caught:
 fit=UnobservedComponents(target[train],level='local level',exog=z[train]).fit(disp=False,maxiter=500)
pred=fit.get_forecast(steps=int(test.sum()),exog=z[test]); ci=np.asarray(pred.conf_int())
f=pd.read_csv(ROOT/'heldout_july_predictions.csv',index_col=0,parse_dates=True)
assert f.index.equals(target[test].index)
f['atlas_fusion_prediction']=np.asarray(pred.predicted_mean)
f['atlas_fusion_lower95']=ci[:,0]; f['atlas_fusion_upper95']=ci[:,1]
f['atlas_success_proxy']=a.loc[test,'packet_success_observed']/a.loc[train,'packet_success_observed'].median()
def metrics(p):
 good=f.observed_active_normalized.notna() & np.isfinite(p)
 actual=f.observed_active_normalized[good].to_numpy(); p=np.asarray(p)[good]
 event=actual<.8; detected=p<.8
 return dict(n=len(actual),mae=float(abs(actual-p).mean()),rmse=float(np.sqrt(((actual-p)**2).mean())),observed_drop_bins=int(event.sum()),predicted_drop_bins=int(detected.sum()),drop_recall=float((event&detected).sum()/event.sum()),false_positive_bins=int((~event&detected).sum()),minimum_prediction=float(p.min()),negative_predictions=int((p<0).sum()),observed_deficit_hours=float(np.maximum(0,1-actual).sum()*8),predicted_deficit_hours=float(np.maximum(0,1-p).sum()*8))
report=dict(scope='AS812, 8-hour, May-Jun fit; July DEVELOPMENT comparison (previously inspected).',models={k:metrics(f[k]) for k in ['atlas_fusion_prediction','state_space_prediction','routing_ratio_proxy','atlas_success_proxy','constant_training_median']},fit_converged=bool(fit.mle_retvals.get('converged',False)),fit_warnings=[str(w.message) for w in caught],parameters={k:float(v) for k,v in fit.params.items()},training_feature_ranges={c:[float(features.loc[train,c].min()),float(features.loc[train,c].max())] for c in features},july_feature_ranges={c:[float(features.loc[test,c].min()),float(features.loc[test,c].max())] for c in features},historical_reconstruction_approved=False,limitations=['Only three Atlas probes and one ping destination; not representative of whole ASN or country.','July inspected earlier; a fresh independent validation is required.','Training has little severe-outage variation; large covariate excursions are extrapolation.','Normalized signal may exceed one; negative predictions are physically invalid and are reported without clipping.','Missing observations are not treated as packet failures.','No 2018-2021 IODA observations generated; no ERA5 or weather inputs.','June snapshot probe selection can impose survival selection for May training.'],raw_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.glob('atlas_1010_2022_??.json.gz')})
f.to_csv(ROOT/'atlas_fusion_july_development.csv',index_label='time_utc')
(ROOT/'atlas_fusion_validation.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps(report,indent=2))
