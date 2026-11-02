from pathlib import Path
import json,hashlib,datetime as dt,time
import numpy as np
import pandas as pd
from .run_connection_baseline import Sources
started=time.monotonic();out=Path('analysis/2026-10-31_pixel_exceedance/v1/comparison');assert not out.exists();src=Sources();p=out.parent/'full_outputs';mb=src.read(p/'manifest.json');m=json.loads(mb);r=json.loads(src.read(out.parent/'full_outputs.verify.json'));assert r['status']=='verified' and r['manifest_sha256']==hashlib.sha256(mb).hexdigest();src.verify(p/'country_daily.csv',m['outputs']['country_daily.csv']);data=pd.read_csv(p/'country_daily.csv',dtype={'country_id':str});frames=[]
for year in range(2022,2026):
 for month in range(1,13):
  old=Path('analysis/2026-10-06_era5_existing_data/country_daily')/f'era5_country_daily_{year}{month:02d}.csv';src.verify(old,m['inputs'][str(old)]);f=pd.read_csv(old,dtype={'country_id':str});frames.append(f[['country_id','date','tmax_c']])
original=pd.concat(frames,ignore_index=True);assert not original.duplicated(['country_id','date']).any();data=data.merge(original,on=['country_id','date'],validate='one_to_one');assert len(data)==318498
qp=Path('analysis/2026-10-07_event_inputs/heat_catalogue/thresholds.csv');src.verify(qp);qt=pd.read_csv(qp,dtype={'country_id':str});q={(r.country_id,int(r.calendar_day)):r.q90_tmax_c for r in qt.itertuples()}
def threshold(row):
 date=dt.date.fromisoformat(row.date)
 if date.month==2 and date.day==29:return (q[row.country_id,58]+q[row.country_id,59])/2
 day=(dt.date(2001,date.month,date.day)-dt.date(2001,1,1)).days;return q[row.country_id,day]
data['country_q90_tmax_c']=[threshold(row) for row in data.itertuples()];valid=np.isfinite(data.pixel_exceedance_population_fraction)&np.isfinite(data.tmax_c)&np.isfinite(data.country_q90_tmax_c);data=data[valid].copy();data['country_daily_exceedance']=data.tmax_c>data.country_q90_tmax_c
cols=[];groups={}
for flag in (False,True):
 f=data[data.country_daily_exceedance==flag].pixel_exceedance_population_fraction;groups[str(flag)]=dict(country_days=len(f),mean=float(f.mean()),quantiles={str(x):float(f.quantile(x,interpolation='linear')) for x in (0,.25,.5,.75,1)})
for country,frame in data.groupby('country_id',sort=True):
 row=dict(country_id=country,total_days=len(frame))
 for flag,label in ((False,'country_nonexceedance'),(True,'country_exceedance')):
  f=frame[frame.country_daily_exceedance==flag].pixel_exceedance_population_fraction;row[label+'_days']=len(f);row[label+'_mean_pixel_fraction']=float(f.mean()) if len(f) else None
 cols.append(row)
src.verify(Path(__file__));src.verify(Path('docs/superpowers/specs/2026-10-31-pixel-comparison.md'));src.check();out.mkdir();data.to_csv(out/'country_day_spatial_comparison.csv',index=False);pd.DataFrame(cols).to_csv(out/'country_summary.csv',index=False);summary=dict(supported_country_days=len(data),countries=len(cols),groups=groups,elapsed_seconds=time.monotonic()-started,scope='Descriptive local-Q90 population fraction versus exact original daily country-Q90 exceedance, all supported 2022-2025 country-days equally weighted. Not heat-event/network eligibility, independent samples, global population rank or causal inference.');(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(out/'manifest.json').write_text(json.dumps(dict(inputs=src.entries,outputs={n:Sources().verify(out/n) for n in ('country_day_spatial_comparison.csv','country_summary.csv','summary.json')}),indent=2)+'\n');print(json.dumps(summary))
