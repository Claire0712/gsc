"""Audit all technically damaged-at-end records against original point masks."""
import argparse,io,json,time
from collections import Counter
from pathlib import Path
import numpy as np
from .recovery_qualification import qualify
from .run_connection_baseline import Sources,Stage,_json

def run(args):
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources();panel=Stage(args.panel,sources,status_key='status',manifest_key=('status','completed'));baseline=Stage(args.baseline,sources,status_key='status',manifest_key=('status','completed'))
    # Verify the panel's metrics parent points to exactly this baseline manifest.
    metricpath=next(Path(k) for k in panel.manifest['inputs'] if k.endswith('resilience_metrics/v1/full_outputs/manifest.json'))
    metric=_json(sources.read(metricpath,panel.manifest['inputs'][str(metricpath)]));bp=(Path(args.baseline)/'manifest.json').resolve();sources.verify(bp,metric['inputs'][str(bp)])
    rows=panel.json('rows.json');risk=[r for r in rows if r['metrics']['recovery']['survival_eligible_from_core']]
    if args.signal:risk=[r for r in risk if r['signal']==args.signal]
    result=[]
    for r in risk:
        with np.load(io.BytesIO(baseline.read(r['source_point_file'])),allow_pickle=False) as z:a={k:z[k] for k in z.files}
        for key in ('event_id','signal','country_id'):
            if str(a[key].item())!=r[key]:raise ValueError('Point identity mismatch')
        m=r['metrics'];q=qualify(a,m['event_start'],m['event_end_exclusive']);result.append(dict(r,qualified=q))
    for n in ('recovery_qualification.py','run_recovery_qualification.py','heat_resilience_metrics.py','run_connection_baseline.py'):sources.verify(Path(__file__).parent/n)
    summaries={}
    for sig in sorted({r['signal'] for r in result}):
        rr=[r for r in result if r['signal']==sig];qq=[r for r in rr if r['qualified']['risk_eligible']];positive=[r for r in qq if r['qualified']['recovery']['followup_hours']>0]
        summaries[sig]=dict(technical_risk=len(rr),core_excluded=len(rr)-len(qq),qualified_risk=len(qq),positive_followup=len(positive),countries=len({r['country_id'] for r in positive}),confirmed=sum(r['qualified']['recovery']['status']=='confirmed' for r in positive),status=dict(Counter(r['qualified']['recovery']['status'] for r in qq)),censor_cause=dict(Counter(r['qualified']['censor_cause'] for r in qq if r['qualified']['censor_cause'])))
    sources.check();out.mkdir(parents=True)
    def publish(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    publish('rows.json',result);report=dict(status='completed',rows=len(result),signals=summaries,elapsed_seconds=time.monotonic()-start,scope='Technical end-damaged risk set only. Core excludes mask bits2/4/8/16; first followup flagged/missing slot censors. Flags after confirmation do not remove recovered events. Unconfirmed anomalies and original unknown STOP metadata retained. No fitted survival model or causal certification.')
    publish('summary.json',report);publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs={n:Sources().verify(out/n) for n in ('rows.json','summary.json')}));publish('status.json',dict(status='completed'));print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('panel','baseline','output'):p.add_argument('--'+n,required=True)
    p.add_argument('--signal');run(p.parse_args())
