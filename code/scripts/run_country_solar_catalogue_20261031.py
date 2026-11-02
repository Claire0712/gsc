"""Solar vs UTC weather-only catalogue sensitivity using unchanged core rules."""
import argparse,json,time,io
from pathlib import Path
import pandas as pd
from .run_connection_baseline import Sources
from . import heat_catalogue_variants_core as core
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--countries');a=p.parse_args();out=Path(a.output);assert not out.exists();started=time.monotonic();src=Sources();frames=[]
for year in range(2018,2026):
 for month in range(1,13):
  d=Path('analysis/2026-10-31_country_solar/v1')/('full_'+str(year)+str(month).zfill(2));assert json.loads(src.read(d/'status.json'))['status']=='completed';mb=src.read(d/'manifest.json');m=json.loads(mb)
  import hashlib
  for suffix in ('.verify.json','.utc.verify.json'):
   receipt=json.loads(src.read(d.with_name(d.name+suffix)));assert receipt['status']=='verified' and receipt['manifest_sha256']==hashlib.sha256(mb).hexdigest()
  df=pd.read_csv(io.BytesIO(src.read(d/'country_daily.csv',m['outputs']['country_daily.csv'])),dtype={'country_id':str});assert df.complete_month_grid.all();frames.append(df)
data=pd.concat(frames,ignore_index=True);data['date']=pd.to_datetime(data.date);assert not data.duplicated(['country_id','date']).any()
meta=pd.read_csv(io.BytesIO(src.read(Path('analysis/2026-10-06_era5_existing_data/weights/country_metadata.csv'))),dtype={'country_id':str});positive=set(meta.loc[meta.total_population>0,'country_id']);excluded=sorted(set(data.country_id)-positive);data=data[data.country_id.isin(positive)]
if a.countries:data=data[data.country_id.isin(a.countries.split(','))]
assert len(data)>0
out.mkdir(parents=True);save=lambda n,d:(out/n).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');save('status.json',dict(status='running'));summaries={};identities={};products={}
for mode in ('solar','utc'):
 target=out/mode;target.mkdir();tables={n:[] for n in ('thresholds.csv','warm_seasons.csv','analysis_events.csv')}
 for country,ff in data.groupby('country_id',sort=True):
  fields=['tmin_c','tmax_c','dewpoint_c'];frame=ff[['country_id','date']].copy()
  for field in fields:frame[field]=ff[field if mode=='solar' else 'utc_'+field]
  q=core.build_thresholds(frame);season=core.warm_season(frame);assert season['warm_season_start_month'] is not None
  flagged=core.attach_thresholds(frame.loc[frame.date>='2021-01-01'],q);raw,process,events,daily=core.catalogue_country(flagged,season['warm_season_start_month']);q.insert(0,'country_id',country)
  tables['thresholds.csv'].append(q);tables['warm_seasons.csv'].append(pd.DataFrame([dict(country_id=country,**season)]));tables['analysis_events.csv'].append(events)
 for n,parts in tables.items():pd.concat(parts,ignore_index=True).to_csv(target/n,index=False);products[mode+'/'+n]=Sources().verify(target/n)
 events=pd.read_csv(target/'analysis_events.csv',dtype={'country_id':str});identities[mode]=set(zip(events.country_id,events.start_date));summaries[mode]=dict(countries=int(data.country_id.nunique()),events=len(events),weather_candidates=int(events.weather_candidate.sum()))
for n in ('run_country_solar_catalogue_20261031.py','heat_catalogue_variants_core.py'):src.verify(Path(__file__).with_name(n))
src.check();save('summary.json',dict(definitions=summaries,same_country_start=len(identities['solar']&identities['utc']),solar_only_country_start=len(identities['solar']-identities['utc']),utc_only_country_start=len(identities['utc']-identities['solar']),excluded_zero_population=excluded,elapsed_seconds=time.monotonic()-started,scope='Weather-only solar vs UTC catalogue diagnostic; source hourly day bins, own four-year thresholds/season. Each country uses its one fixed-population circular-mean longitude clock; this mean-solar date is not civil night or a new network effect. Not network eligibility, date-baseline or causal-effect acceptance.'))
products['summary.json']=Sources().verify(out/'summary.json');save('manifest.json',dict(status='completed',inputs=src.entries,outputs=products));save('status.json',dict(status='completed'));print((out/'summary.json').read_text())
