"""Retrospective weather-only reference; never consumes target-year values."""
import numpy as np
import pandas as pd
from .heat_catalogue_variants_core import calendar_day

def reference_inputs(frame,target_year):
 if target_year not in range(2022,2026):raise ValueError('Target must be 2022–2025')
 if frame.date.duplicated().any():raise ValueError('Duplicate dates')
 years=set(range(2018,2026))-{target_year}
 ref=frame.loc[frame.date.dt.year.isin(years)].copy()
 day=ref.date.map(calendar_day);valid_day=day.notna();dd=day.loc[valid_day].to_numpy(int)
 yy=ref.loc[valid_day].date.dt.year.to_numpy();rows=[]
 for d in range(365):
  window=np.minimum((dd-d)%365,(d-dd)%365)<=15;r={'calendar_day':d}
  for field in ('tmax','tmin'):
   v=ref.loc[valid_day,field+'_c'].to_numpy(float);ok=window&np.isfinite(v);n=int(ok.sum());ny=len(set(yy[ok]))
   r[field+'_reference_n']=n;r[field+'_reference_years']=ny
   r['q90_'+field+'_c']=float(np.quantile(v[ok],.9,method='linear')) if n>=196 and ny==7 else np.nan
  rows.append(r)
 scores=[]
 for m in range(1,13):
  months=[(m-1+i)%12+1 for i in range(3)];vv=ref.loc[ref.date.dt.month.isin(months),'tmax_c'].to_numpy(float);ok=np.isfinite(vv)
  scores.append(float(vv[ok].mean()) if ok.any() else None)
 start=int(np.nanargmax([np.nan if x is None else x for x in scores]))+1 if any(x is not None for x in scores) else None
 return pd.DataFrame(rows),dict(warm_season_start_month=start,scores=scores,reference_years=sorted(years),reference_valid_fraction=float(np.isfinite(ref.tmax_c).mean()),future_reference_years=sorted(y for y in years if y>target_year))

def target_events(frame,target_year):
 return frame.loc[pd.to_datetime(frame.start_date).dt.year==target_year].copy()
