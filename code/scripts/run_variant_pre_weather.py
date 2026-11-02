"""Outcome-blind weather preparation; no matching or outcome computation."""
import argparse
import csv
from datetime import datetime, timezone, timedelta
import io
import json
from pathlib import Path
import time

from .pre_weather_features import pre_weather_features

IDENTITY=('window_id','parent_event_id','role','country_id','ioda_iso2','start','end')

def prepare(windows,weather):
    identities={}
    for row in windows:
        identity={key:row[key] for key in IDENTITY}
        key=row['window_id']
        if key in identities and identities[key]!=identity:
            raise ValueError('Conflicting window identity: '+key)
        identities[key]=identity
    index={}
    for row in weather:
        key=(row['country_id'],row['date'])
        if key in index:raise ValueError('Duplicate weather country/date')
        index[key]=row
    countries={key[0] for key in index}
    result=[]
    for key,identity in sorted(identities.items()):
        country=identity['country_id']
        if country not in countries:raise ValueError('Unknown weather country: '+country)
        stamp=int(identity['start'])
        if stamp%86400:raise ValueError('Window must start at UTC midnight')
        start=datetime.fromtimestamp(stamp,timezone.utc).date()
        dates=[(start-timedelta(days=i)).isoformat() for i in range(1,8)]
        prior=[index[country,day] for day in dates if (country,day) in index]
        result.append(dict(identity,**{k:v for k,v in pre_weather_features(prior,country,start.isoformat()).items() if k!='country_id'}))
    return result

def run(args):
    from .run_connection_baseline import Sources, Stage, _json
    from .build_heat_event_catalogue import load_inputs
    start=time.monotonic()
    out=Path(args.output)
    if out.exists():raise FileExistsError('Output already exists')
    sources=Sources()
    comparison=Stage(args.comparison,sources,status_key='status',manifest_key=('status','completed'))
    heat_path=Path(args.heat)/'manifest.json'
    expected=comparison.manifest['inputs'].get(str(heat_path.resolve()))
    if expected is None:raise ValueError('Heat manifest not in comparison ancestry')
    heat=_json(sources.read(heat_path,expected))
    if heat['state']!='complete':raise ValueError('Heat source incomplete')
    table_path=Path(args.comparison)/'window_audit.csv'
    windows=list(csv.DictReader(io.StringIO(sources.read(table_path,comparison.manifest['outputs']['window_audit.csv']).decode())))
    if args.country:
        windows=[r for r in windows if r['country_id']==args.country]
        if not windows:raise ValueError('Country not represented')
    from .variant_weather_sources import resolve_sources
    monthly=resolve_sources(heat,args.batch,args.source_heat,sources)
    ancestry={r['month']:r for r in monthly}
    if len(ancestry)!=96:raise ValueError('96 source months required')
    for month,record in ancestry.items():
        p=Path(args.weather)/f'era5_country_daily_{month}.csv'
        sources.verify(p,{'sha256':record['sha256']})
        sources.verify(p.with_suffix('.audit.json'),{'sha256':record['audit_sha256']})
    frame,_,_=load_inputs(args.weather,[args.country] if args.country else None)
    frame['date']=frame.date.dt.strftime('%Y-%m-%d')
    features=prepare(windows,frame[['country_id','date','tmax_c','tmin_c','dewpoint_c']].to_dict('records'))
    for name in ('run_variant_pre_weather.py','variant_weather_sources.py','pre_weather_features.py','build_heat_event_catalogue.py','run_connection_baseline.py'):
        sources.verify(Path(__file__).parent/name)
    sources.check()
    summary=dict(status='completed',unique_windows=len(features),signal_rows=len(windows),
                 complete_all_variables=sum(r['complete'] for r in features),
                 complete_by_variable={v:sum(r['valid_days'][v]==7 for r in features) for v in ('tmax_c','tmin_c','dewpoint_c')},
                 selected_country=args.country,elapsed_seconds=time.monotonic()-start,
                 matched=False,final_sample_eligible=False,
                 policy='Only seven complete UTC dates before start; Celsius; no imputation; Tmin descriptive, not inclusion criterion')
    out.mkdir(parents=True)
    def publish(name,data):
        (out/name).write_text(json.dumps(data,ensure_ascii=False,allow_nan=False,indent=2)+'\n')
    publish('features.json',features)
    publish('summary.json',summary)
    products={name:Sources().verify(out/name) for name in ('features.json','summary.json')}
    sources.check()
    publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products))
    publish('status.json',dict(status='completed',elapsed_seconds=time.monotonic()-start))
    print(json.dumps(summary))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for arg in ('comparison','heat','weather','output','batch','source-heat'):parser.add_argument('--'+arg,required=True)
    parser.add_argument('--country')
    run(parser.parse_args())

