"""Kalman model using valid training observations, with no imputed measurements."""
import json,warnings
from pathlib import Path
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.structural import UnobservedComponents
ROOT=Path(__file__).resolve().parents[1]/'downloads/reconstruction_pilot'
EXP=ROOT/'expanded_cohort'
s=json.loads((ROOT/'raw/ioda_AS812_2022.json').read_text())['data'][0][0]
y=pd.Series(s['values'],index=pd.to_datetime(s['from']+np.arange(len(s['values']))*s['step'],unit='s',utc=True),dtype=float).loc[:'2022-07-31 23:59:59']
n=y.resample('8h').count();y=y.resample('8h').mean().where(n>=44)
train=y.index<pd.Timestamp('2022-07-01',tz='UTC');test=~train
target=y/y[train].median()
r=pd.DataFrame(json.loads((ROOT/'raw/ripe_AS812_2022.json').read_text())['data']['ipv4']);r.index=pd.to_datetime(r.pop('timestamp'),utc=True)
r=r.reindex(r.index.union(y.index)).sort_index().ffill().reindex(y.index)
a=pd.read_csv(EXP/'coverage_and_success_8h.csv',index_col=0,parse_dates=True)
x=r[['address-space','prefixes']].astype(float).assign(atlas_robust=a.robust_atlas_success.reindex(y.index))
valid=x.notna().all(axis=1)
z=(x-x[train].mean())/x[train].std().replace(0,1)
# Missing covariates imply NO target observation in the likelihood. The zero
# design placeholder has no contribution at that missing-observation step;
# it is not an imputed measurement and is never emitted as an observed value.
fit_target=target[train].where(valid[train]);design=z.fillna(0)
with warnings.catch_warnings(record=True) as caught:
 fit=UnobservedComponents(fit_target,level='local level',exog=design[train]).fit(disp=False,maxiter=500)
pred=fit.get_forecast(int(test.sum()),exog=design[test])
f=pd.DataFrame({'observed':target[test],'state_space_prediction':np.asarray(pred.predicted_mean)},index=target[test].index)
f.loc[~valid[test],'state_space_prediction']=np.nan
paired=f.dropna();truth=paired.observed;p=paired.state_space_prediction
report={'scope':'AS812 July development, not independent validation','fit_converged':bool(fit.mle_retvals.get('converged',False)),'warnings':[str(w.message) for w in caught],'training_target_missing_after_coverage_mask':int(fit_target.isna().sum()),'training_covariate_missing_bins':int((~valid[train]).sum()),'missing_method':'Observation omitted from Kalman likelihood; dummy zero exogenous design only at missing-observation steps, not measurement imputation.','metrics':{'paired_bins':len(paired),'mae':float(abs(truth-p).mean()),'rmse':float(np.sqrt(((truth-p)**2).mean())),'minimum_prediction':float(p.min()),'detected_drop_bins':int(((truth<.8)&(p<.8)).sum()),'observed_drop_bins':int((truth<.8).sum()),'false_positive_bins':int(((truth>=.8)&(p<.8)).sum()),'observed_deficit_hours':float(np.maximum(0,1-truth).sum()*8),'predicted_deficit_hours':float(np.maximum(0,1-p).sum()*8)},'historical_backfill_approved':False}
f.to_csv(EXP/'state_space_july_development.csv',index_label='time_utc')
(EXP/'state_space_validation.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps(report,indent=2))
