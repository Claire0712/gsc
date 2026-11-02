"""Calendar and positive-population support audit, not weather certification."""
import argparse,csv,io,json,math,time
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from .build_climate_pilot import climate_files,load_climate
from .run_connection_baseline import Sources,Stage
PAIRS={'wind':('u10_m_s','v10_m_s'),'old_temperature':('tmax_degC','tmin_degC')}
def group_complete(rows,lookup,fields,cutoff):
    for r in rows:
        values=lookup.get((r['country_id'],r['date']),{})
        for f in fields:
            v=values.get(f);p=values.get(f+'_population_fraction')
            if v is None or p is None or not math.isfinite(v) or not math.isfinite(p) or p<=0 or p<cutoff:return False
    return bool(rows)

def run(args):
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources();stage=Stage(args.responses,sources,status_key='status',manifest_key=('status','completed'))
    raw=list(csv.DictReader(io.StringIO(stage.read('daily_1.csv').decode())))
    if args.country:raw=[r for r in raw if r['country_id']==args.country]
    for p in climate_files(Path(args.data)):sources.verify(p)
    panel,metadata=load_climate(Path(args.data));lookup={}
    for r in panel.values():
        if not r['iso3']:continue
        key=(r['iso3'],r['date_utc'])
        if key in lookup:raise ValueError('Ambiguous ISO day')
        lookup[key]=r
    groups=defaultdict(list)
    for r in raw:
        r=dict(r,date=datetime.fromtimestamp(int(r['date_utc']),timezone.utc).strftime('%Y-%m-%d'))
        groups[r['signal'],r['purpose'],r['group_id']].append(r)
    records=[]
    for (signal,purpose,event),rr in sorted(groups.items()):
        record=dict(signal=signal,purpose=purpose,event_id=event,country_id=rr[0]['country_id'],windows=len({r['window_id'] for r in rr}),daily_rows=len(rr))
        for name,fields in PAIRS.items():
            record[name]={str(c):group_complete(rr,lookup,fields,c) for c in (0,.8,.9,.95,.99,1.)}
        records.append(record)
    summary={}
    for name in PAIRS:
        summary[name]={}
        for s,p in sorted({(r['signal'],r['purpose']) for r in records}):
            rr=[r for r in records if r['signal']==s and r['purpose']==p]
            summary[name][s+'_'+p]=dict(total_groups=len(rr),cutoffs={str(c):dict(events=sum(r[name][str(c)] for r in rr),countries=len({r['country_id'] for r in rr if r[name][str(c)]})) for c in (0,.8,.9,.95,.99,1.)})
    for n in ('weather_support.py','build_climate_pilot.py'):sources.verify(Path(__file__).with_name(n))
    sources.check();out.mkdir(parents=True)
    def save(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    save('groups.json',records);save('summary.json',dict(groups=len(records),support=summary,source_files=metadata['files'],elapsed_seconds=time.monotonic()-start,
        scope='Existing2024 final daily products only, segment files excluded. Entire original main-caliper heat+all selected control windows must have finite paired fields and positive support. Thresholds are descriptive not certified eligibility; exact1 is numeric not strict missing-population-zero proof. Source spatial weights/day semantics require separate certification. Wind vector magnitude is not gust; no refit or full-period wind adjustment.'))
    save('manifest.json',dict(status='completed',inputs=sources.entries,outputs={n:Sources().verify(out/n) for n in ('groups.json','summary.json')}))
    save('status.json',dict(status='completed'));print((out/'summary.json').read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('responses','data','output'):p.add_argument('--'+n,required=True)
    p.add_argument('--country');run(p.parse_args())
