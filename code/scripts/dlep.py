"""Descriptive AP social-weighted deficit proxy, never disconnected person-hours."""
import argparse,csv,io,json,math,time
from pathlib import Path
from collections import Counter
import numpy as np
from .run_connection_baseline import Sources,Stage

def internet(rows,country,year):
    index={}
    for r in rows:
        if r['iso3']!=country:continue
        y=int(r['year'])
        if y in index:raise ValueError('Duplicate country year')
        index[y]=r
    for y in range(year,year-4,-1):
        try:v=float(index[y]['IT.NET.USER.ZS'])
        except (KeyError,ValueError,TypeError):continue
        if math.isfinite(v) and 0<=v<=100:
            return dict(value=v/100,source_year=y,lag_years=year-y,status='current_reference_year' if y==year else 'past_reference_year')
    return dict(value=None,source_year=None,lag_years=None,status='missing_allowed_years')

def build(events,population,social):
    output=[];seen=set();cache={}
    for r in events:
        if r['signal']!='ping-slash24':continue
        if r['event_id'] in seen:raise ValueError('Duplicate AP event')
        seen.add(r['event_id']);c=r['country_id'];year=int(r['year_month'][:4]);key=(c,year)
        if key not in cache:cache[key]=internet(social,c,year)
        use=cache[key];pop=population.get(c);dh=r['metrics']['dhrd_hours'];reasons=[]
        if not r['full_observed_unconfounded']:reasons.append('not_full_observed_clean')
        if dh is None or not math.isfinite(dh) or dh<0:reasons.append('missing_invalid_dhrd')
        if pop is None or not math.isfinite(pop) or pop<=0:reasons.append('missing_invalid_population')
        if use['value'] is None:reasons.append('missing_internet_share')
        value=None if reasons else dh*pop*use['value']
        if value is not None and not math.isfinite(value):raise ValueError('Nonfinite DLEP')
        output.append(dict(event_id=r['event_id'],country_id=c,year=year,signal=r['signal'],
            matched_integral=r['matched_integral'],full_observed_unconfounded=r['full_observed_unconfounded'],
            dhrd_hours=dh,population_2025=pop,internet=use,dlep_proxy=value,exclusion_reasons=reasons))
    return output

def run(args):
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    src=Sources();stage=Stage(args.panel,src,status_key='status',manifest_key=('status','completed'))
    events=stage.json('rows.json')
    if args.country:events=[r for r in events if r['country_id']==args.country]
    poprows=list(csv.DictReader(io.StringIO(src.read(Path(args.population)).decode('utf-8-sig'))))
    pop={r['country_id']:float(r['total_population']) for r in poprows}
    if len(pop)!=len(poprows):raise ValueError('Duplicate population code')
    social=list(csv.DictReader(io.StringIO(src.read(Path(args.worldbank)).decode('utf-8-sig'))))
    rows=build(events,pop,social)
    if not rows:raise ValueError('No AP events')
    summaries={}
    for label,rr in [('all_forward_ap',rows),('full_clean_ap',[r for r in rows if r['full_observed_unconfounded']]),('matched_integral_ap',[r for r in rows if r['matched_integral']])]:
        good=[r for r in rr if r['dlep_proxy'] is not None];vals=[r['dlep_proxy'] for r in good]
        summaries[label]=dict(records=len(rr),available=len(good),countries=len({r['country_id'] for r in good}),
            source_lags=dict(Counter(str(r['internet']['lag_years']) for r in good)),
            exclusion_reasons=dict(Counter(x for r in rr for x in r['exclusion_reasons'])),
            proxy_quantiles={str(q):float(np.quantile(vals,q)) for q in [0,.25,.5,.75,1]} if vals else {})
    src.verify(Path(__file__));src.check();out.mkdir(parents=True)
    def save(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    save('rows.json',rows);save('summary.json',dict(groups=summaries,elapsed_seconds=time.monotonic()-start,
        scope='AP only. Fixed2025 assigned population mass; current reference year preferred then most recent past within3years, percent/100. Full observed clean technical window required; other rows retained with null proxy. Publication dates unknown. Proxy only: not actual disconnected people/person-hours or welfare loss; no ranking, national/global sum or causal claim.'))
    save('manifest.json',dict(status='completed',inputs=src.entries,outputs={n:Sources().verify(out/n) for n in ['rows.json','summary.json']}));save('status.json',dict(status='completed'));print((out/'summary.json').read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['panel','population','worldbank','output']:p.add_argument('--'+n,required=True)
    p.add_argument('--country');run(p.parse_args())
