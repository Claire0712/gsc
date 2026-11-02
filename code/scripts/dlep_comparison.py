"""Complete descriptive pair comparisons, no national resilience ranking or p-value."""
import argparse,json,math,time
from itertools import combinations
from pathlib import Path
from .run_connection_baseline import Sources,Stage

def compare(rows):
    rr=[r for r in rows if r['dlep_proxy'] is not None]
    if len({r['event_id'] for r in rr})!=len(rr):raise ValueError('Duplicate event')
    for r in rr:
        if not all(math.isfinite(r[k]) and r[k]>=0 for k in ['dhrd_hours','dlep_proxy']):raise ValueError('Invalid available metric')
    result={k:dict(concordant=0,inverted=0,tied=0) for k in ['all','same_country','cross_country']}
    for a,b in combinations(rr,2):
        x=a['dhrd_hours']-b['dhrd_hours'];y=a['dlep_proxy']-b['dlep_proxy']
        kind='tied' if x==0 or y==0 else ('concordant' if (x>0)==(y>0) else 'inverted')
        result['all'][kind]+=1;result['same_country' if a['country_id']==b['country_id'] else 'cross_country'][kind]+=1
    for v in result.values():
        v['pairs']=v['concordant']+v['inverted']+v['tied'];den=v['concordant']+v['inverted']
        v['inverted_fraction_non_tied']=v['inverted']/den if den else None
    return dict(records=len(rr),countries=len({r['country_id'] for r in rr}),**result)

def run(a):
    start=time.monotonic();out=Path(a.output)
    if out.exists():raise FileExistsError(out)
    src=Sources();s=Stage(a.dlep,src,status_key='status',manifest_key=('status','completed'));rows=s.json('rows.json')
    if a.country:rows=[r for r in rows if r['country_id']==a.country]
    results={k:compare(rr) for k,rr in [('full_clean_available',rows),('matched_integral_available',[r for r in rows if r['matched_integral']])]}
    src.verify(Path(__file__));src.check();out.mkdir(parents=True)
    def save(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    save('summary.json',dict(groups=results,elapsed_seconds=time.monotonic()-start,
        scope='Every unordered available-event pair; exact numeric ties if either outcome equal, no p-values or independence assumption. Inverted means smaller technical DHRD but larger weighted proxy. Cross-country pairs are descriptive weighting contrasts, not comparable-heat resilience effects. Same-country contrasts may reflect indicator-year changes. No ranking or real disconnected person-hours.'))
    save('manifest.json',dict(status='completed',inputs=src.entries,outputs={'summary.json':Sources().verify(out/'summary.json')}));save('status.json',dict(status='completed'));print((out/'summary.json').read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dlep',required=True);p.add_argument('--output',required=True);p.add_argument('--country');run(p.parse_args())
