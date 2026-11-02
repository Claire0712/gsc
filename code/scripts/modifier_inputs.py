"""Four socioeconomic modifiers with explicit reference-year lag and missingness."""
import argparse,csv,io,json,math,time
from pathlib import Path
from collections import Counter
from .run_connection_baseline import Sources,Stage
FIELDS={'electricity_access_share':('EG.ELC.ACCS.ZS',True),
        'gdp_per_capita_ppp_constant':('NY.GDP.PCAP.PP.KD',False),
        'urban_population_share':('SP.URB.TOTL.IN.ZS',True),
        'internet_share':('IT.NET.USER.ZS',True)}

def prior(rows,country,year,column,percent):
    selected={}
    for r in rows:
        if r['iso3']!=country:continue
        y=int(r['year'])
        if y in selected:raise ValueError('Duplicate country year')
        selected[y]=r
    for y in range(year-1,year-4,-1):
        try:v=float(selected[y][column])
        except (KeyError,ValueError,TypeError):continue
        if not math.isfinite(v) or v<0 or (percent and v>100):continue
        return dict(value=v/100 if percent else v,source_year=y,lag_years=year-y,status='lagged_reference_year')
    return dict(value=None,source_year=None,lag_years=None,status='missing_allowed_prior_years')

def run(args):
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources();stage=Stage(args.panel,sources,status_key='status',manifest_key=('status','completed'))
    events=stage.json('rows.json');raw=list(csv.DictReader(io.StringIO(sources.read(Path(args.worldbank)).decode('utf-8-sig'))))
    if args.country:events=[r for r in events if r['country_id']==args.country]
    if not events:raise ValueError('No selected events')
    cache={};records=[]
    for r in events:
        country=r['country_id'];year=int(r['year_month'][:4]);key=(country,year)
        if key not in cache:cache[key]={name:prior(raw,country,year,col,pct) for name,(col,pct) in FIELDS.items()}
        records.append(dict(event_id=r['event_id'],country_id=country,signal=r['signal'],year=year,
            matched_integral=r['matched_integral'],modifiers=cache[key]))
    summary={}
    for s in sorted({r['signal'] for r in records}):
        rr=[r for r in records if r['signal']==s and r['matched_integral']]
        summary[s]=dict(matched_events=len(rr),all_four_complete=sum(all(v['value'] is not None for v in r['modifiers'].values()) for r in rr),
            modifiers={name:dict(available=sum(r['modifiers'][name]['value'] is not None for r in rr),
                countries=len({r['country_id'] for r in rr if r['modifiers'][name]['value'] is not None}),
                lags=dict(Counter(str(r['modifiers'][name]['lag_years']) for r in rr))) for name in FIELDS})
    sources.verify(Path(__file__));sources.check();out.mkdir(parents=True)
    def save(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    save('rows.json',records)
    save('summary.json',dict(records=len(records),signals=summary,elapsed_seconds=time.monotonic()-start,
        scope='Exact country code equality using already crosswalk-qualified event panel; newest valid indicator-specific reference year 1 to 3 years before event year. Shares divide percent by100. No interpolation or current/future reference values. Publication dates unknown: not certified point-in-time availability. Four of six planned modifiers only; no fitted effects, support comparability or causal claim.'))
    save('manifest.json',dict(status='completed',inputs=sources.entries,outputs={n:Sources().verify(out/n) for n in ('rows.json','summary.json')}))
    save('status.json',dict(status='completed'));print((out/'summary.json').read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('panel','worldbank','output'):p.add_argument('--'+n,required=True)
    p.add_argument('--country');run(p.parse_args())
