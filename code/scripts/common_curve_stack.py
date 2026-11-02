"""Restrict existing daily curves to exact common selected controls."""
import argparse,csv,io,json,time
from pathlib import Path
from .paired_responses import weights
from .run_connection_baseline import Sources,Stage
SIGNALS=('ping-slash24','bgp','merit-nt')

def input_entry(inputs,path):
    entries=[e for p,e in inputs.items() if Path(p).resolve()==Path(path).resolve()]
    if len(entries)!=1:raise ValueError('Missing or ambiguous input path')
    return entries[0]

def restrict(rows,support):
    selected={r['event_id']:r for r in support if r['purpose']=='curve' and r['common_controls']}
    kept=[]
    for r in rows:
        if r['purpose']!='curve' or r['group_id'] not in selected:continue
        q=selected[r['group_id']];controls=q['common_controls']
        if r['window_id'] not in [q['heat_id']]+controls:continue
        r=dict(r,base_weight=1. if r['role']=='heat' else 1./len(controls),matched_controls=len(controls))
        kept.append(r)
    membership={s:{(r['group_id'],r['window_id'],r['date_utc'],r['relative_day'],r['role'],r['country_id']) for r in kept if r['signal']==s} for s in SIGNALS}
    if not all(membership[s]==membership[SIGNALS[0]] for s in SIGNALS):raise ValueError('Different common daily support')
    for e,q in selected.items():
        for s in SIGNALS:
            rr=[r for r in kept if r['group_id']==e and r['signal']==s]
            if {r['window_id'] for r in rr}!={q['heat_id'],*q['common_controls']}:raise ValueError('Missing selected common window')
    return weights(kept)

def run(args):
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources();rs=Stage(args.responses,sources,status_key='status',manifest_key=('status','completed'))
    cs=Stage(args.common,sources,status_key='status',manifest_key=('status','completed'))
    support=cs.json('support.json')['events']
    if args.limit:
        ids=sorted(r['event_id'] for r in support if r['purpose']=='curve' and r['common_controls'])[:args.limit]
        support=[r for r in support if r['event_id'] in ids]
    # Require the common controls and responses to reference the same matching manifest.
    mp=next(Path(p) for p in rs.manifest['inputs'] if p.endswith('matching/v1/full_outputs/manifest.json'))
    sources.verify(mp,input_entry(rs.manifest['inputs'],mp));sources.verify(mp,input_entry(cs.manifest['inputs'],mp))
    rows=restrict(list(csv.DictReader(io.StringIO(rs.read('daily_1.csv').decode()))),support)
    if not rows:raise ValueError('Empty common curve')
    sources.verify(Path(__file__));sources.verify(Path(__file__).with_name('paired_responses.py'));sources.check()
    out.mkdir(parents=True)
    with (out/'daily_1.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    def save(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    save('summary.json',dict(groups=len({r['group_id'] for r in rows}),countries=len({r['country_id'] for r in rows}),rows=len(rows),elapsed_seconds=time.monotonic()-start,scope='Identical selected heat/control/date support across three signals; main caliper intersection only, recomputed date-reuse weights, no rematching. Daily sensitivity, not primary ten-minute model.'))
    save('manifest.json',dict(status='completed',inputs=sources.entries,outputs={n:Sources().verify(out/n) for n in ('daily_1.csv','summary.json')}))
    save('status.json',dict(status='completed'));print((out/'summary.json').read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('responses','common','output'):p.add_argument('--'+n,required=True)
    p.add_argument('--limit',type=int,default=0);run(p.parse_args())
