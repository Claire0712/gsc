"""Proposal14.2 weather definition diagnostic only, separate target-year catalogues."""
import argparse,json,time
from pathlib import Path
import pandas as pd
from . import heat_catalogue_variants_core as c
from .seven_year_reference import reference_inputs,target_events
from .run_connection_baseline import Sources

def run(a):
 t=time.monotonic();out=Path(a.output)
 if out.exists():raise FileExistsError(out)
 data,inputs,excluded=c.load_inputs(a.daily,a.countries.split(',') if a.countries else None);src=Sources()
 for x in inputs:
  src.verify(x['path'],{'sha256':x['sha256']});src.verify(Path(x['path']).with_suffix('.audit.json'),{'sha256':x['audit_sha256']})
 for n in ('seven_year_reference.py','run_seven_year_reference_20261101.py','heat_catalogue_variants_core.py'):src.verify(Path(__file__).with_name(n))
 out.mkdir(parents=True);save=lambda n,d:(out/n).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');save('status.json',{'status':'running'})
 tables={n:[] for n in ('thresholds','seasons','events','primary_events')};summary=[]
 for idx,(country,f) in enumerate(data.groupby('country_id',sort=True),1):
  mainq=c.build_thresholds(f);mains=c.warm_season(f);maind=c.attach_thresholds(f.loc[f.date>='2021-01-01'],mainq);main=c.catalogue_country(maind,mains['warm_season_start_month'])[2]
  for year in range(2022,2026):
   q,s=reference_inputs(f,year);daily=c.attach_thresholds(f.loc[f.date>='2021-01-01'],q);ev=target_events(c.catalogue_country(daily,s['warm_season_start_month'])[2],year);base=target_events(main,year)
   astarts=set(ev.start_date);bstarts=set(base.start_date);same=astarts&bstarts
   enda=ev.set_index('start_date').end_date.to_dict();endb=base.set_index('start_date').end_date.to_dict()
   summary.append(dict(country_id=country,target_year=year,events=len(ev),weather_candidates=int(ev.weather_candidate.sum()),primary_events=len(base),primary_weather_candidates=int(base.weather_candidate.sum()),same_start=len(same),same_bounds=sum(enda[k]==endb[k] for k in same),warm_season_changed=s['warm_season_start_month']!=mains['warm_season_start_month']))
   for name,df in (('thresholds',q),('events',ev),('primary_events',base)):
    df=df.copy();df['target_year']=year;df['country_id']=country;tables[name].append(df)
   tables['seasons'].append(pd.DataFrame([dict(country_id=country,target_year=year,**{k:(json.dumps(v) if isinstance(v,list) else v) for k,v in s.items()})]))
  if idx%10==0:print(json.dumps(dict(countries_done=idx,elapsed_seconds=time.monotonic()-t)),flush=True)
 products={}
 for name,parts in tables.items():
  filename=name+'.csv';pd.concat(parts,ignore_index=True).to_csv(out/filename,index=False);products[filename]=Sources().verify(out/filename)
 pd.DataFrame(summary).to_csv(out/'comparison.csv',index=False);products['comparison.csv']=Sources().verify(out/'comparison.csv')
 save('summary.json',dict(countries=int(data.country_id.nunique()),country_target_years=len(summary),events=sum(x['events'] for x in summary),weather_candidates=sum(x['weather_candidates'] for x in summary),primary_events=sum(x['primary_events'] for x in summary),primary_weather_candidates=sum(x['primary_weather_candidates'] for x in summary),same_start=sum(x['same_start'] for x in summary),same_bounds=sum(x['same_bounds'] for x in summary),warm_season_changes=sum(x['warm_season_changed'] for x in summary),zero_population_exclusions=excluded,elapsed_seconds=time.monotonic()-t,scope='Retrospective seven-other-years weather-only diagnostic. Future data included for 2022–2024. Start-year cohorts use their own fixed reference; not a spliced network catalogue, forecast, eligibility or alternative effect estimate. Primary unchanged.'))
 products['summary.json']=Sources().verify(out/'summary.json');src.check();save('manifest.json',dict(status='completed',inputs=src.entries,outputs=products));save('status.json',dict(status='completed'));print((out/'summary.json').read_text(),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--daily',required=True);p.add_argument('--output',required=True);p.add_argument('--countries');run(p.parse_args())
