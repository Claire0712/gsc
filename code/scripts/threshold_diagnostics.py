"""Q95 candidates and leave-reference-year-out Q90 diagnostics; never replace main."""
import argparse,csv,io,json,math,time,datetime
from collections import defaultdict
from pathlib import Path
import numpy as np
from .run_connection_baseline import Sources

def quantile(values,years,q,omit=None):
    needed=set(range(2018,2022))-{omit};mask=np.isfinite(values)&np.isin(years,list(needed));n=int(mask.sum())
    if n<math.ceil(.9*31*len(needed)) or set(years[mask])!=needed:return None,n
    return float(np.quantile(values[mask],q,method='linear')),n

def run(a):
    start=time.monotonic();out=Path(a.output)
    if out.exists():raise FileExistsError(out)
    src=Sources();root=Path(a.catalogue);m=json.loads(src.read(root/'manifest.json'));assert m['state']=='complete'
    expected=m['outputs']['thresholds.csv'];raw=src.read(root/'thresholds.csv',expected)
    old={(r['country_id'],int(r['calendar_day'])):r for r in csv.DictReader(io.StringIO(raw.decode()))}
    countries=sorted({c for c,d in old})
    if a.country:countries=[c for c in countries if c==a.country]
    assert countries;selected=set(countries);data=defaultdict(list)
    for y in range(2018,2022):
        for mo in range(1,13):
            p=Path(a.daily)/f'era5_country_daily_{y}{mo:02}.csv';audit=json.loads(src.read(p.with_suffix('.audit.json')))
            for r in csv.DictReader(io.StringIO(src.read(p,{'sha256':audit['output_sha256']}).decode())):
                if r['country_id'] not in selected:continue
                d=datetime.date.fromisoformat(r['date'])
                if (d.month,d.day)==(2,29):continue
                j=(datetime.date(2001,d.month,d.day)-datetime.date(2001,1,1)).days
                data[r['country_id']].append((d.year,j,float(r['tmax_c']),float(r['tmin_c'])))
    output=[];shifts={'tmax':[],'tmin':[]};raises={'tmax':[],'tmin':[]};maxerr=0.
    for c in countries:
        arr=np.array(data[c]);assert len(arr)==1460
        for day in range(365):
            delta=abs(arr[:,1]-day);v=arr[np.minimum(delta,365-delta)<=15]
            r=dict(country_id=c,calendar_day=day)
            for metric,column in [('tmax',2),('tmin',3)]:
                base,n=quantile(v[:,column],v[:,0],.9);previous=float(old[c,day][f'q90_{metric}_c'])
                assert base is not None and math.isclose(base,previous,abs_tol=1e-10)
                maxerr=max(maxerr,abs(base-previous));r[f'q90_{metric}_c']=base;r[f'{metric}_reference_n']=n
                higher,_=quantile(v[:,column],v[:,0],.95);r[f'q95_{metric}_c']=higher
                if higher is not None:raises[metric].append(higher-base)
                for omit in range(2018,2022):
                    q,nn=quantile(v[:,column],v[:,0],.9,omit);r[f'q90_{metric}_omit_{omit}_c']=q;r[f'{metric}_omit_{omit}_n']=nn
                    if q is not None:shifts[metric].append(abs(q-base))
            output.append(r)
    src.verify(Path(__file__));src.check();out.mkdir(parents=True)
    with (out/'thresholds.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(output[0]));w.writeheader();w.writerows(output)
    def stats(v):return {str(q):float(np.quantile(v,q)) for q in [0,.5,.95,1]} if v else {}
    def save(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    save('summary.json',dict(countries=len(countries),rows=len(output),max_main_q90_error=maxerr,loyo_absolute_shift_c={k:stats(v) for k,v in shifts.items()},q95_minus_q90_c={k:stats(v) for k,v in raises.items()},elapsed_seconds=time.monotonic()-start,scope='Fixed2018–2021 circular31day calendar; omitFeb29. Main112/124 and all4years; LOYO84/93 and all3remaining years. Each country-day equally weighted descriptive quantiles, not uncertainty intervals. Q95 candidates and LOYO not event catalogues or connectivity sensitivities; main unchanged.'))
    save('manifest.json',dict(status='completed',inputs=src.entries,outputs={n:Sources().verify(out/n) for n in ['thresholds.csv','summary.json']}));save('status.json',dict(status='completed'));print((out/'summary.json').read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['catalogue','daily','output']:p.add_argument('--'+n,required=True)
    p.add_argument('--country');run(p.parse_args())
