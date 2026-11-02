"""Independent scalar threshold/season audit; recompose with previously audited event core."""
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from . import heat_catalogue_variants_core as core
from .run_connection_baseline import Sources

def audit(a):
 t=time.monotonic();out=Path(a.output);mbytes=(out/'manifest.json').read_bytes();m=json.loads(mbytes);src=Sources()
 assert json.loads((out/'status.json').read_text())['status']=='completed'
 for n,h in m['outputs'].items():src.verify(out/n,h)
 for path,expected in m['inputs'].items():src.verify(path,expected)
 q=pd.read_csv(out/'thresholds.csv',dtype={'country_id':str});se=pd.read_csv(out/'seasons.csv',dtype={'country_id':str});ev=pd.read_csv(out/'events.csv',dtype={'country_id':str});cmp=pd.read_csv(out/'comparison.csv',dtype={'country_id':str})
 countries=sorted(q.country_id.unique());data,_,excluded=core.load_inputs(a.daily,countries)
 assert len(q)==len(countries)*4*365 and len(se)==len(countries)*4 and len(cmp)==len(se)
 assert not q.duplicated(['country_id','target_year','calendar_day']).any()
 errors=[];checks=0;eventchecks=0
 for country,f in data.groupby('country_id',sort=True):
  for year in range(2022,2026):
   ref=f.loc[f.date.dt.year!=year];assert set(ref.date.dt.year)==set(range(2018,2026))-{year}
   qr=q.loc[(q.country_id==country)&(q.target_year==year)].sort_values('calendar_day')
   assert len(qr)==365
   daycodes=[]
   for date in ref.date:
    daycodes.append(None if date.month==2 and date.day==29 else pd.Timestamp(2001,date.month,date.day).dayofyear-1)
   days=np.array([np.nan if d is None else d for d in daycodes]);refyears=ref.date.dt.year.to_numpy()
   for day in range(365):
    dist=np.abs(days-day);mask=np.isfinite(days)&(np.minimum(dist,365-dist)<=15);r=qr.iloc[day]
    for field in ('tmax','tmin'):
     vals=ref[field+'_c'].to_numpy(float);ok=mask&np.isfinite(vals);n=int(ok.sum());ny=len(set(refyears[ok]));assert r[field+'_reference_n']==n and r[field+'_reference_years']==ny
     actual=r['q90_'+field+'_c'];expected=np.quantile(vals[ok],.9,method='linear') if n>=196 and ny==7 else np.nan
     if np.isnan(expected):assert np.isnan(actual)
     else:errors.append(abs(actual-expected));assert np.isclose(actual,expected,rtol=0,atol=5e-12)
     checks+=1
   scores=[]
   for month in range(1,13):
    months={(month+i-1)%12+1 for i in range(3)};values=[r.tmax_c for r in ref.itertuples() if r.date.month in months and np.isfinite(r.tmax_c)];scores.append(float(np.mean(values)) if values else None)
   s=se.loc[(se.country_id==country)&(se.target_year==year)].iloc[0];start=int(np.nanargmax(scores))+1
   assert start==s.warm_season_start_month and np.allclose(scores,json.loads(s.scores),atol=5e-12,rtol=0)
   assert json.loads(s.reference_years)==sorted(set(range(2018,2026))-{year}) and json.loads(s.future_reference_years)==list(range(year+1,2026))
   # Recompose intervals with independently checked thresholds/season and immutable audited core.
   flagged=core.attach_thresholds(f.loc[f.date>='2021-01-01'],qr);re=core.catalogue_country(flagged,start)[2];re=re.loc[pd.to_datetime(re.start_date).dt.year==year];actual=ev.loc[(ev.country_id==country)&(ev.target_year==year)]
   assert list(zip(re.start_date,re.end_date,re.weather_candidate))==list(zip(actual.start_date,actual.end_date,actual.weather_candidate))
   for field in ('hd_c_days','ntrd_c_days','absolute_tmax_c','span_days'):
    assert np.allclose(re[field],actual[field],rtol=1e-12,atol=5e-10,equal_nan=True)
   row=cmp.loc[(cmp.country_id==country)&(cmp.target_year==year)].iloc[0];assert row.events==len(actual) and row.weather_candidates==actual.weather_candidate.sum();eventchecks+=len(actual)
 src.check();receipt=dict(status='verified',manifest_sha256=hashlib.sha256(mbytes).hexdigest(),scalar_threshold_checks=checks,max_threshold_error=max(errors,default=0),country_target_year_seasons=len(se),recomposed_intervals=eventchecks,elapsed_seconds=time.monotonic()-t,scope='Independent reference membership, scalar Q90/support, all season choices; catalogue recomposition reuses previously audited immutable core, not a second event algorithm. Weather definition only.')
 receiptpath=Path(str(out)+'.verify.json');assert not receiptpath.exists();receiptpath.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--daily',required=True);audit(p.parse_args())
