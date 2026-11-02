"""Versioned technical census and exposure panel, not fitted model eligibility."""
import argparse,csv,io,json,time
from pathlib import Path
from collections import Counter
from .event_panel import build
from .run_connection_baseline import Sources,Stage,_json

def run(args):
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources()
    metrics=Stage(args.metrics,sources,status_key='status',manifest_key=('status','completed'))
    matching=Stage(args.matching,sources,status_key='status',manifest_key=('status','completed'))
    def read(stage,path,name):return _json(sources.read(Path(path)/name,stage.manifest['outputs'][name]))
    records=read(metrics,args.metrics,'event_metrics.json')
    pairs=read(matching,args.matching,'selected_1.json')
    matched={(p['parent_event_id'],p['signal']) for p in pairs if p['purpose']=='integral'}
    if not matched<={(r['event_id'],r['signal']) for r in records}:raise ValueError('Matched event absent from census')
    root=Path(args.catalogue);manifest=_json(sources.read(root/'manifest.json'))
    if manifest['state']!='complete':raise ValueError('Incomplete heat catalogue')
    catalogue=list(csv.DictReader(io.StringIO(sources.read(root/'analysis_events.csv',manifest['outputs']['analysis_events.csv']).decode())))
    if args.country:records=[r for r in records if r['country_id']==args.country]
    rows=build(records,catalogue,matched)
    summaries={}
    for signal in sorted({r['signal'] for r in rows}):
        summaries[signal]={}
        for subset in ('all_forward','full_observed_unconfounded','matched_integral'):
            rr=[r for r in rows if r['signal']==signal and (subset=='all_forward' or r[subset])]
            risk=[r for r in rr if r['survival_time_hours'] is not None]
            summaries[signal][subset]=dict(rows=len(rr),countries=len({r['country_id'] for r in rr}),states=dict(Counter(r['metrics']['state'] for r in rr)),core_states=dict(Counter(r['metrics']['core_end_state'] for r in rr)),risk_rows=len(risk),risk_countries=len({r['country_id'] for r in risk}),risk_status=dict(Counter(r['metrics']['recovery']['status'] for r in risk)),zero_followup=sum(not r['positive_followup'] for r in risk))
    for name in ('event_panel.py','run_event_panel.py','run_connection_baseline.py'):sources.verify(Path(__file__).parent/name)
    sources.check();out.mkdir(parents=True)
    def publish(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    publish('rows.json',rows)
    report=dict(rows=len(rows),events=len({r['event_id'] for r in rows}),signals=summaries,elapsed_seconds=time.monotonic()-start,scope='Forward technical census only; retain original eligibility/review flags. Full-observed subset conditions on future completeness; not primary survival gate. Main integral matched subset separate. No fitted association, precipitation adjustment, or final sample certification.')
    publish('summary.json',report)
    publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs={n:Sources().verify(out/n) for n in ('rows.json','summary.json')}))
    publish('status.json',dict(status='completed'));print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('metrics','matching','catalogue','output'):p.add_argument('--'+n,required=True)
    p.add_argument('--country');run(p.parse_args())
