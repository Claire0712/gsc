"""Versioned weather-only alternative catalogues, no network eligibility claim."""
import argparse,json,time
from pathlib import Path
import pandas as pd
from . import heat_catalogue_variants_core as core
from .run_connection_baseline import Sources,Stage

VARIANTS={'main_reproduction':('q90',2,3,None),'q95':('q95',2,3,None),
 'min3':('q90',3,3,None),'min6':('q90',6,3,None),'season6':('q90',2,6,None),
 'all_year':('q90',2,12,None),'absolute30':('q90',2,3,30.),'absolute35':('q90',2,3,35.)}

def run(a):
    started=time.monotonic();out=Path(a.output)
    if out.exists():raise FileExistsError(out)
    src=Sources();ts=Stage(a.thresholds,src,status_key='status',manifest_key=('status','completed'))
    thresholds=pd.read_csv(__import__('io').BytesIO(ts.read('thresholds.csv')),dtype={'country_id':str})
    oldroot=Path(a.original);oldm=json.loads(src.read(oldroot/'manifest.json'));assert oldm['state']=='complete'
    old=pd.read_csv(__import__('io').BytesIO(src.read(oldroot/'analysis_events.csv',oldm['outputs']['analysis_events.csv'])),dtype={'country_id':str})
    data,sources,exclusions=core.load_inputs(a.daily,a.countries.split(',') if a.countries else None)
    for item in sources:
        src.verify(item['path'],{'sha256':item['sha256']});src.verify(Path(item['path']).with_suffix('.audit.json'),{'sha256':item['audit_sha256']})
    for name in ['heat_catalogue_variants_core.py','run_heat_catalogue_variants.py']:src.verify(Path(__file__).with_name(name))
    out.mkdir(parents=True);results={};products={}
    for variant,(prefix,min_run,months,absolute) in VARIANTS.items():
        target=out/variant;target.mkdir();began=time.monotonic();tables={n:[] for n in ['raw_events.csv','process_events.csv','analysis_events.csv','daily_heat_flags.csv.gz','warm_seasons.csv']}
        for country,frame in data.groupby('country_id',sort=True):
            q=thresholds.loc[thresholds.country_id==country,['calendar_day',f'{prefix}_tmax_c',f'{prefix}_tmin_c']].copy()
            q=q.rename(columns={f'{prefix}_tmax_c':'q90_tmax_c',f'{prefix}_tmin_c':'q90_tmin_c'})
            assert len(q)==365
            # Absolute definitions use absolute Tmax only; secondary Tmin retains Q90.
            if absolute is not None:q['q90_tmax_c']=absolute
            season=core.warm_season(frame,months_count=months if months!=12 else 3)
            if months==12:season['warm_season_start_month']=1
            flagged=core.attach_thresholds(frame.loc[frame.date>='2021-01-01'],q)
            r,p,e,d=core.catalogue_country(flagged,season['warm_season_start_month'],min_run=min_run,season_months=months)
            for n,v in zip(['raw_events.csv','process_events.csv','analysis_events.csv','daily_heat_flags.csv.gz'],[r,p,e,d]):tables[n].append(v)
            tables['warm_seasons.csv'].append(pd.DataFrame([dict(country_id=country,**season)]))
        tables={n:pd.concat(v,ignore_index=True) for n,v in tables.items()}
        if variant=='main_reproduction':
            expected=old.loc[old.country_id.isin(data.country_id.unique())].reset_index(drop=True)
            pd.testing.assert_frame_equal(tables['analysis_events.csv'].reset_index(drop=True),expected,check_dtype=False,rtol=1e-11,atol=1e-10)
        for n,v in tables.items():
            v.to_csv(target/n,index=False,compression='gzip' if n.endswith('.gz') else None)
            products[variant+'/'+n]=Sources().verify(target/n)
        events=tables['analysis_events.csv'];result=dict(analysis_events=len(events),weather_candidates=int(events.weather_candidate.sum()),warm_start_events=int(events.in_warm_season.sum()),countries=int(events.country_id.nunique()),elapsed_seconds=time.monotonic()-began)
        results[variant]=result
        (target/'rules.json').write_text(json.dumps(dict(temperature_threshold=prefix if absolute is None else absolute,minimum_consecutive_days=min_run,season_months=months,secondary_tmin_threshold=prefix,network_screened=False),indent=2)+'\n');products[variant+'/rules.json']=Sources().verify(target/'rules.json')
        (out/'progress.json').write_text(json.dumps(dict(status='running',completed=results),indent=2)+'\n');print(variant,json.dumps(result),flush=True)
    src.check()
    summary=dict(variants=results,elapsed_seconds=time.monotonic()-started,scope='Weather-only definitions; main reproduced against original event table. All-year context retained for isolation. Q95 applies to secondary Tmin too; absolute Tmax uses Q90 Tmin. Absolute excess uses30/35C; not comparable relative HD. Full-year season mean/LOYO fields retain3month reference diagnostics, but start is1 and membership all12months. No network eligibility, reference/matching/effect robustness established.')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');products['summary.json']=Sources().verify(out/'summary.json')
    (out/'manifest.json').write_text(json.dumps(dict(status='completed',inputs=src.entries,outputs=products),indent=2)+'\n');(out/'status.json').write_text('{"status":"completed"}\n')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['daily','thresholds','original','output']:p.add_argument('--'+n,required=True)
    p.add_argument('--countries');run(p.parse_args())
