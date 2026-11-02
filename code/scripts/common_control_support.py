"""Audit shared, already selected controls; do not rematch or refit effects."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import time
from .run_connection_baseline import Sources, Stage

SIGNALS=('ping-slash24','bgp','merit-nt')
PURPOSES=('integral','curve')

def audit(rows):
    grouped=defaultdict(lambda:defaultdict(set));identities={}
    for r in rows:
        if r['signal'] not in SIGNALS or r['purpose'] not in PURPOSES:
            raise ValueError('Unknown signal or purpose')
        if not r['selected'] or not r['supported']:
            raise ValueError('Input must contain selected supported pairs only')
        event=r['parent_event_id'];identity=(r['country_id'],r['heat_id'])
        if event in identities and identities[event]!=identity:
            raise ValueError('Inconsistent event identity')
        identities[event]=identity
        controls=grouped[(r['purpose'],event)][r['signal']]
        if r['control_id'] in controls:raise ValueError('Duplicate selected pair')
        controls.add(r['control_id'])
    events=[];summary={}
    for purpose in PURPOSES:
        for (p,event),signals in sorted(grouped.items()):
            if p!=purpose:continue
            common=set.intersection(*(signals.get(s,set()) for s in SIGNALS))
            events.append(dict(purpose=p,event_id=event,country_id=identities[event][0],
                heat_id=identities[event][1],all_signals_present=set(signals)==set(SIGNALS),
                selected_by_signal={s:sorted(signals.get(s,set())) for s in SIGNALS},
                common_controls=sorted(common)))
        rr=[r for r in events if r['purpose']==purpose]
        cc=[r for r in rr if r['common_controls']]
        summary[purpose]=dict(any_signal_events=len(rr),
            all_signal_events=sum(r['all_signals_present'] for r in rr),
            common_control_events=len(cc),common_countries=len({r['country_id'] for r in cc}),
            common_pairs=sum(len(r['common_controls']) for r in cc))
    return dict(summary=summary,events=events)

def run(args):
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources();stage=Stage(args.matching,sources,status_key='status',manifest_key=('status','completed'))
    rows=stage.json('selected_1.json')
    if args.limit:
        ids=set(sorted({r['parent_event_id'] for r in rows})[:args.limit])
        rows=[r for r in rows if r['parent_event_id'] in ids]
    result=audit(rows)
    result.update(elapsed_seconds=time.monotonic()-start,input_pairs=len(rows),
        scope='Exact intersection of existing main-caliper selected controls, separately for integral and curve. No new matching, no effect estimation, no direction selection. A selected-pair support audit, not proof of full three-signal model identification. Legacy final_sample_eligible is not reinterpreted.')
    sources.verify(Path(__file__));sources.check();out.mkdir(parents=True)
    def save(n,x):(out/n).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
    save('support.json',result)
    save('manifest.json',dict(status='completed',inputs=sources.entries,
        outputs={'support.json':Sources().verify(out/'support.json')}))
    save('status.json',dict(status='completed'))
    print(json.dumps(result['summary'],indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--matching',required=True)
    p.add_argument('--output',required=True);p.add_argument('--limit',type=int,default=0)
    run(p.parse_args())
