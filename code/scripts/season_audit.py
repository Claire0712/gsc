"""Independent reference warm-season reconstruction; no catalogue producer imports."""
import argparse,csv,json,math,hashlib,time
from pathlib import Path
from collections import defaultdict,Counter

def choose(rows):
    scores=[]
    for start in range(1,13):
        months={(start+i-1)%12+1 for i in range(3)}
        values=[v for y,m,v in rows if m in months and math.isfinite(v)]
        scores.append(math.fsum(values)/len(values) if values else -math.inf)
    if max(scores)==-math.inf:return None,None
    start=scores.index(max(scores))+1
    return start,scores[start-1]

def main(a):
    start=time.monotonic();out=Path(a.output)
    if out.exists():raise FileExistsError(out)
    hashes={}
    def read(p):
        b=Path(p).read_bytes();hashes[str(p)]=hashlib.sha256(b).hexdigest();return b
    root=Path(a.catalogue);manifest=json.loads(read(root/'manifest.json'));assert manifest['state']=='complete'
    b=read(root/'warm_seasons.csv');expected=manifest['outputs']['warm_seasons.csv'];expected=expected['sha256'] if isinstance(expected,dict) else expected
    assert hashlib.sha256(b).hexdigest()==expected
    original={r['country_id']:r for r in csv.DictReader(b.decode().splitlines())}
    if a.country:original={c:r for c,r in original.items() if c==a.country}
    assert original;data=defaultdict(list);seen=set()
    for year in range(2018,2022):
        for month in range(1,13):
            p=Path(a.daily)/f'era5_country_daily_{year}{month:02}.csv';b=read(p);audit=json.loads(read(p.with_suffix('.audit.json')))
            assert hashes[str(p)]==audit['output_sha256']
            for r in csv.DictReader(b.decode().splitlines()):
                c=r['country_id']
                if c not in original:continue
                key=(c,r['date']);assert key not in seen;seen.add(key)
                y,m,_=map(int,r['date'].split('-'));assert y==year and m==month
                data[c].append((y,m,float(r['tmax_c'])))
    result=[]
    for c,r in original.items():
        rr=data[c];assert len(rr)==1461
        selected,mean=choose(rr);loo=[choose([v for v in rr if v[0]!=y])[0] for y in range(2018,2022)]
        agreement=sum(v==selected for v in loo)/4;valid=sum(math.isfinite(v) for y,m,v in rr)/len(rr)
        assert selected==int(r['warm_season_start_month']) and loo==json.loads(r['loyo_start_months'])
        assert agreement==float(r['loyo_agreement_fraction']) and math.isclose(mean,float(r['warm_season_mean_tmax_c']),abs_tol=1e-10)
        assert math.isclose(valid,float(r['reference_valid_fraction']),abs_tol=1e-12)
        result.append(dict(country_id=c,start_month=selected,leave_year_out_starts=loo,agreement_fraction=agreement,reference_valid_fraction=valid))
    for p,h in hashes.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
    out.mkdir(parents=True)
    def save(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    save('rows.json',result);save('summary.json',dict(status='verified',countries=len(result),agreement_distribution=dict(Counter(str(r['agreement_fraction']) for r in result)),elapsed_seconds=time.monotonic()-start,scope='Reconstructed daily-weighted three-month choice and all four leave-reference-year-out seasons from48 monthly source tables; exact frozen choices unchanged. Not threshold LOYO, new six-month/all-year event catalogue or connectivity effect sensitivity.'))
    save('manifest.json',dict(status='completed',inputs=hashes,outputs={n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in ['rows.json','summary.json']}));save('status.json',dict(status='completed'));print((out/'summary.json').read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['catalogue','daily','output']:p.add_argument('--'+n,required=True)
    p.add_argument('--country');main(p.parse_args())
