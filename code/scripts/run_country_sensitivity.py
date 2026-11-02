"""Primary AP A/M1 leave-one-country diagnostic using unchanged event estimator."""
import argparse,json,time
from pathlib import Path
import numpy as np
from .leave_country import samples
from .country_sensitivity import select_rows
from .heat_associations_v2 import design,estimate
from .run_heat_associations_v2 import OUTCOMES
from .run_connection_baseline import Sources,Stage,_json

def run(args):
    started=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources();stage=Stage(args.panel,sources,status_key='status',manifest_key=('status','completed'))
    rows=_json(sources.read(Path(args.panel)/'rows.json',stage.manifest['outputs']['rows.json']))
    rows=select_rows(rows,args.signal)
    if not rows or any(not r['metrics']['full_window_complete'] or not r['full_observed_unconfounded'] for r in rows):
        raise ValueError('Invalid matched sample')
    for n in ('run_country_sensitivity.py','country_sensitivity.py','leave_country.py','heat_associations_v2.py','run_heat_associations_v2.py','event_curve_core.py','curve_inference.py','run_connection_baseline.py'):
        sources.verify(Path(__file__).parent/n)
    selected=list(samples(rows))
    if args.limit_omissions:selected=selected[:args.limit_omissions]
    out.mkdir(parents=True);results=[];products={}
    def publish(name,data):(out/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    publish('status.json',dict(status='running'))
    try:
        for omitted,subset in selected:
            x,z,terms,dropped=design(subset,args.setting,args.model);countries=[r['country_id'] for r in subset]
            outcomes={o:np.array([np.log1p(r['metrics']['dhrd_hours']) if o=='log1p_dhrd' else r['metrics'][o] for r in subset]) for o in OUTCOMES}
            filename=omitted+'.npz'
            np.savez_compressed(out/filename,x=x,z=z.toarray(),countries=np.array(countries),event_ids=np.array([r['event_id'] for r in subset]),**outcomes)
            products[filename]=Sources().verify(out/filename)
            results.append(dict(omitted_country=omitted,terms=terms,matrix=filename,results={o:estimate(x,y,z,countries,o!='log1p_dhrd') for o,y in outcomes.items()}))
            publish('status.json',dict(status='running',completed_omissions=len(results),total=len(selected)))
        sources.check();publish('results.json',results)
        publish('summary.json',dict(status='completed',signal=args.signal,setting=args.setting,model=args.model,omissions=len(results),source_rows=len(rows),source_countries=len({r['country_id'] for r in rows}),pilot=args.limit_omissions is not None,elapsed_seconds=time.monotonic()-started,scope='Country deletion sensitivity only; not region deletion, independent replications, multiplicity-adjusted inference or causal identification. Same event eligibility and estimator; focal design rebuilt after each omission; nonestimability retained.'))
        for n in ('results.json','summary.json'):products[n]=Sources().verify(out/n)
        publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products));publish('status.json',dict(status='completed'))
        print(json.dumps(dict(omissions=len(results),elapsed_seconds=time.monotonic()-started)))
    except BaseException as e:publish('status.json',dict(status='failed',error=str(e)));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--panel',required=True);p.add_argument('--output',required=True);p.add_argument('--limit-omissions',type=int)
    p.add_argument('--signal',required=True,choices=('ping-slash24','bgp','merit-nt'))
    p.add_argument('--setting',required=True,choices=('A','B'));p.add_argument('--model',required=True,choices=('M1','M2'));run(p.parse_args())
