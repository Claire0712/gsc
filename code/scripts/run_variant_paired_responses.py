"""Hash-linked response preparation for all fixed matching specifications."""
import argparse,csv,io,json,os,time
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
from .paired_responses import daily,weights
from .heat_resilience_metrics import event_metrics
from .run_connection_baseline import Sources,Stage,_json
from .run_variant_matching import ancestry_entry

def run(args):
    started=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError('Fresh output required')
    sources=Sources();stages={}
    for name in ('comparison','matching','measurement','stop_review'):
        stages[name]=Stage(getattr(args,name),sources,status_key='status',manifest_key=('status','completed'))
    comp=stages['comparison'];matching=stages['matching']
    for parent,child in [('comparison','matching'),('comparison','measurement'),('matching','stop_review')]:
        p=Path(getattr(args,parent))/'manifest.json'
        sources.verify(p,ancestry_entry(stages[child].manifest['inputs'],p))
    def read(stage,name):
        return sources.read(Path(getattr(args,stage))/name,stages[stage].manifest['outputs'][name])
    audits=list(csv.DictReader(io.StringIO(read('comparison','window_audit.csv').decode())))
    index={(r['window_id'],r['signal']):r for r in audits}
    if len(index)!=len(audits):raise ValueError('Duplicate audit identity')
    diag={(r['window_id'],r['signal']):r for r in _json(read('measurement','window_diagnostics.json'))}
    stop=_json(read('stop_review','pair_review.json'))
    selected={s:_json(read('matching','selected_'+s+'.json')) for s in ('0.5','1','2')}
    for s,rows in selected.items():
        stopkeys={(r['heat_id'],r['control_id'],r['signal'],r['purpose']):r for r in stop[s]}
        for p in rows:
            q=stopkeys[p['heat_id'],p['control_id'],p['signal'],p['purpose']]
            if any(any(v.values()) for v in q['evidence'].values()):raise ValueError('Selected STOP overlap requires disposition')
        if args.country:selected[s]=[r for r in rows if r['country_id']==args.country]
    needed=sorted({(p[role+'_id'],p['signal']) for rows in selected.values() for p in rows for role in ('heat','control')})
    if not needed:raise ValueError('No selected windows')
    for name in ('paired_responses.py','run_variant_paired_responses.py','run_variant_matching.py','heat_resilience_metrics.py','run_connection_baseline.py'):
        sources.verify(Path(__file__).parent/name)
    sources.verify(Path(args.design));out.mkdir(parents=True)
    def publish(name,obj):
        tmp=out/('.'+name);tmp.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n');os.replace(tmp,out/name)
    publish('status.json',dict(status='running',pid=os.getpid(),total=len(needed),processed=0))
    cached={};metrics=[]
    try:
        for wid,sig in needed:
            row=index[wid,sig];d=diag[wid,sig]
            if d['primary_exclusion'] or d['confirmed_measurement_fault']:raise ValueError('Unexpected confirmed exclusion')
            path=Path(args.comparison)/row['point_file'];sources.verify(path,comp.manifest['outputs'][row['point_file']])
            start,end=int(row['start']),int(row['end'])
            purposes={p['purpose'] for rows in selected.values() for p in rows if p['signal']==sig and wid in (p['heat_id'],p['control_id'])}
            with np.load(path,allow_pickle=False) as z:
                if str(z['window_id'])!=wid or str(z['signal'])!=sig or int(z['start_utc_seconds'])!=start or int(z['end_utc_seconds'])!=end:raise ValueError('NPZ identity mismatch')
                args0=(z['target_timestamps'],z['target_values'],z['baseline'])
                metric=event_metrics(*args0,start,end,analysis_available=z['target_technical_available'])
                if not metric['full_window_complete']:raise ValueError('Selected integral incomplete')
                days={purpose:daily(*args0,z['target_technical_available'],start-7*86400,end+3*86400 if purpose=='integral' else start+8*86400) for purpose in purposes}
            identity=dict(window_id=wid,signal=sig,country_id=row['country_id'],role=row['role'],group_id=row['parent_event_id'],point_file=row['point_file'],shape_flags=d['flags'])
            metrics.append(dict(identity,metrics=metric));cached[wid,sig]=(identity,days,start,end)
            if len(metrics)%100==0:publish('status.json',dict(status='running',pid=os.getpid(),processed=len(metrics),total=len(needed)))
        summary={}
        for scale,pairs in selected.items():
            groups=defaultdict(list)
            for p in pairs:groups[p['parent_event_id'],p['signal'],p['purpose']].append(p)
            stack=[]
            for (group,sig,purpose),pp in sorted(groups.items()):
                if len({p['heat_id'] for p in pp})!=1 or len({p['control_id'] for p in pp})!=len(pp):raise ValueError('Invalid selected group')
                windows=[(pp[0]['heat_id'],1)]+[(p['control_id'],1/len(pp)) for p in pp]
                for wid,base in windows:
                    identity,days,start,end=cached[wid,sig]
                    for day in days[purpose]:
                        stack.append(dict(identity,shape_flags='|'.join(identity['shape_flags']),purpose=purpose,scale=scale,relative_day=(day['date_utc']-start)//86400,core_days=(end-start)//86400,base_weight=base,matched_controls=len(pp),**day))
            stack=weights(stack)
            with (out/('daily_'+scale+'.csv')).open('w',newline='') as f:
                if stack:
                    writer=csv.DictWriter(f,fieldnames=list(stack[0]));writer.writeheader();writer.writerows(stack)
            summary[scale]=dict(pairs=len(pairs),groups=len(groups),daily_rows=len(stack),max_control_date_uses=max((r['control_date_uses'] for r in stack),default=0),by_signal_purpose=dict(Counter(s+'_'+p for _,s,p in groups)))
        sources.check();publish('metrics.json',metrics)
        publish('summary.json',dict(status='completed',unique_windows=len(metrics),specifications=summary,elapsed_seconds=time.monotonic()-started,scope='Unconfirmed candidates retained. Complete selected outcomes and unique-control-date weighted stack; not fitted effects or causal certification. Raw metrics unchanged.'))
        products={n:Sources().verify(out/n) for n in ('metrics.json','summary.json','daily_0.5.csv','daily_1.csv','daily_2.csv')}
        publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products))
        publish('status.json',dict(status='completed',processed=len(metrics),elapsed_seconds=time.monotonic()-started))
        print((out/'summary.json').read_text())
    except BaseException as exc:
        publish('status.json',dict(status='failed',error=str(exc),processed=len(metrics)));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('comparison','matching','measurement','stop-review','design','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--country');run(p.parse_args())

