"""Exact common-event support descriptors; no cross-signal causal comparison."""
import argparse,json,time
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
from .run_connection_baseline import Sources,Stage

SIGNALS=('ping-slash24','bgp','merit-nt')
OUTCOMES=('dhrd_hours','mean_deficit','mean_deficit_core','maintenance_core','peak_loss_core')
def select(rows,matched):
    groups=defaultdict(dict)
    for r in rows:
        if r['signal'] in groups[r['event_id']]:raise ValueError('Duplicate event/signal')
        groups[r['event_id']][r['signal']]=r
    ids={event for event,v in groups.items() if set(v)==set(SIGNALS) and all(r['full_observed_unconfounded'] and (not matched or r['matched_integral']) for r in v.values())}
    return [r for r in rows if r['event_id'] in ids]

def run(args):
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources();stage=Stage(args.panel,sources,status_key='status',manifest_key=('status','completed'));rows=stage.json('rows.json');groups={};identities={}
    for label,matched in [('common_full_clean',False),('common_main_integral',True)]:
        rr=select(rows,matched);ids=sorted({r['event_id'] for r in rr});identities[label]=ids;summary={}
        for signal in SIGNALS:
            vv=[r for r in rr if r['signal']==signal];stats={}
            for name in OUTCOMES:
                vals=np.array([r['metrics'][name] for r in vv],dtype=float)
                if not np.isfinite(vals).all():raise ValueError('Incomplete common metric')
                stats[name]=dict(n=len(vals),mean=float(vals.mean()),median=float(np.median(vals)),q25=float(np.quantile(vals,.25)),q75=float(np.quantile(vals,.75)),min=float(vals.min()),max=float(vals.max())) if len(vals) else dict(n=0)
            summary[signal]=dict(events=len(vv),countries=len({r['country_id'] for r in vv}),states=dict(Counter(r['metrics']['state'] for r in vv)),outcomes=stats)
        groups[label]=summary
    sources.verify(Path(__file__));sources.check();out.mkdir(parents=True)
    def publish(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    publish('common_events.json',identities);publish('summary.json',dict(groups=groups,elapsed_seconds=time.monotonic()-start,scope='Same heat-event identities across all3signals; complete clean technical windows required. Equal-event descriptive summaries only. Common main integral means matching membership across signals, not identical control windows or common refitted effects. No imputation, rankings, significance or causal equivalence. Conditions on full followup.'))
    publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs={n:Sources().verify(out/n) for n in ('common_events.json','summary.json')}));publish('status.json',dict(status='completed'));print((out/'summary.json').read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--panel',required=True);p.add_argument('--output',required=True);run(p.parse_args())
