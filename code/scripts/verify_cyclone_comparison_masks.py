"""Independent cyclone target/query mask audit; no production imports."""
import argparse,json,time,hashlib
from pathlib import Path
from datetime import datetime,timezone
import numpy as np

p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
p.add_argument('--cyclone',required=True,type=Path);a=p.parse_args();started=time.monotonic()
s=json.loads((a.output/'summary.json').read_text())
r,h=s['cyclone_radius_km'],s['cyclone_half_width_hours']
assert r in (100,300,500) and h in (24,72)
lo=int(datetime(2018,1,1,tzinfo=timezone.utc).timestamp())+h*3600
hi=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp())-h*3600
assert s['cyclone_complete_bounds']==[lo,hi]
cache={};files=sorted(a.output.glob('window_*.npz'));slots=0
def hit(t,windows):
    result=np.zeros(t.shape,dtype=bool)
    for start,end in windows:
        assert start<=end
        result|=(t>=start)&(t<=end)
    return result
for path in files:
    with np.load(path,allow_pickle=False) as z:
        country=str(z['country_id'])
        if country not in cache:
            d=json.loads((a.cyclone/(country+'.json')).read_text())
            assert d['country']==country
            cache[country]={m:[] for m in ('known','conservative')}
            for w in d['windows']:
                assert w['country']==country
                if w['radius_km']==r and w['half_width_hours']==h:
                    cache[country][w['mode']].append((w['start_utc_seconds'],w['end_utc_seconds']))
        t=z['target_timestamps'];q=t[:,None]+np.array([-28,-21,-14,-7,7,14,21,28])[None,:]*86400
        for stamps,name in ((t,'target_exclusion_bits'),(q,'reference_exclusion_bits')):
            conservative=hit(stamps,cache[country]['conservative']);known=hit(stamps,cache[country]['known'])
            assert not np.any(known&~conservative)
            expected=4*conservative.astype(np.uint8)+8*(conservative&~known)+16*((stamps<lo)|(stamps>=hi))
            np.testing.assert_array_equal(z[name]&28,expected)
        slots+=len(t)
assert len(files)==s['signal_windows'] and len(files)>0
print(json.dumps(dict(status='verified',windows=len(files),target_slots=slots,
    reference_occurrences=slots*8,seconds=time.monotonic()-started,
    verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    scope='Cyclone bits 4/8/16 only, every target and query; not raw medians or effects')))
