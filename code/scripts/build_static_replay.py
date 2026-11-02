"""Self-contained offline replay of existing verified technical event traces."""
import argparse,io,json,hashlib,time,shutil
from pathlib import Path
import numpy as np
from .run_connection_baseline import Sources,Stage,_json

def hourly(t,v,b,available,start):
    good=available&np.isfinite(v)&(v>=0)&np.isfinite(b)&(b>0)
    ratio=np.full(len(v),np.nan);ratio[good]=v[good]/b[good]
    rows=[]
    for i in range(0,len(t),6):
        segment=ratio[i:i+6]
        value=float(segment.mean()) if len(segment)==6 and np.isfinite(segment).all() else None
        rows.append([(int(t[i])-start)/3600,value])
    return rows

def run(args):
    started=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources();panel=Stage(args.panel,sources,status_key='status',manifest_key=('status','completed'));baseline=Stage(args.baseline,sources,status_key='status',manifest_key=('status','completed'))
    metricpath=next(Path(k) for k in panel.manifest['inputs'] if k.endswith('resilience_metrics/v1/full_outputs/manifest.json'));metric=_json(sources.read(metricpath,panel.manifest['inputs'][str(metricpath)]));bp=(Path(args.baseline)/'manifest.json').resolve();sources.verify(bp,metric['inputs'][str(bp)])
    rows=panel.json('rows.json')
    if args.limit:ids=sorted({r['event_id'] for r in rows})[:args.limit];rows=[r for r in rows if r['event_id'] in ids]
    for r in rows:
        with np.load(io.BytesIO(baseline.read(r['source_point_file'])),allow_pickle=False) as z:
            for key in ('event_id','country_id','signal'):
                if str(z[key].item())!=r[key]:raise ValueError('Identity mismatch')
            r['hourly_ratio']=hourly(z['target_timestamps'],z['target_values'],z['baseline'],z['analysis_available'],r['metrics']['event_start'])
    template=sources.read(Path(args.template)).decode();payload=json.dumps(rows,separators=(',',':'),allow_nan=False).replace('</','<\\/')
    if template.count('__DATASET__')!=1:raise ValueError('Template marker')
    sources.verify(Path(__file__));sources.check();out.mkdir(parents=True)
    (out/'index.html').write_text(template.replace('__DATASET__',payload))
    figurepath=Path(args.figures);fm=_json(sources.read(figurepath/'manifest.json'));(out/'figures').mkdir()
    for name,h in fm['products'].items():
        raw=sources.read(figurepath/name)
        if hashlib.sha256(raw).hexdigest()!=h:raise ValueError('Figure hash mismatch')
        (out/'figures'/name).write_bytes(raw)
    sources.check();products={str(p.relative_to(out)):Sources().verify(p) for p in out.rglob('*') if p.is_file()}
    report=dict(status='completed',records=len(rows),events=len({r['event_id'] for r in rows}),countries=len({r['country_id'] for r in rows}),elapsed_seconds=time.monotonic()-started,scope='Offline technical forward-event replay; hourly display requires all6 valid slots. Original10min metrics preserved. No causal or real-time claims, no public hosting.')
    (out/'manifest.json').write_text(json.dumps(dict(summary=report,inputs=sources.entries,outputs=products),indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('panel','baseline','template','figures','output'):p.add_argument('--'+n,required=True)
    p.add_argument('--limit',type=int);run(p.parse_args())
