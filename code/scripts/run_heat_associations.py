"""Frozen A/B M1/M2 batch on main matched integral heat events."""
import argparse,json,time
from pathlib import Path
import numpy as np
from .heat_associations import design,estimate
from .run_connection_baseline import Sources,Stage,_json

OUTCOMES=('mean_deficit_core','maintenance_core','peak_loss_core','mean_deficit','log1p_dhrd')
def run(args):
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources();stage=Stage(args.panel,sources,status_key='status',manifest_key=('status','completed'))
    allrows=_json(sources.read(Path(args.panel)/'rows.json',stage.manifest['outputs']['rows.json']))
    rows=[r for r in allrows if r['matched_integral'] and (not args.signal or r['signal']==args.signal)]
    if not rows or any(not r['metrics']['full_window_complete'] or not r['full_observed_unconfounded'] for r in rows):raise ValueError('Matched sample completeness/known-confound mismatch')
    for n in ('heat_associations.py','run_heat_associations.py','event_curve_core.py','curve_inference.py','run_connection_baseline.py'):sources.verify(Path(__file__).parent/n)
    out.mkdir(parents=True);results=[];products={}
    def publish(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    publish('status.json',dict(status='running'))
    try:
        for signal in sorted({r['signal'] for r in rows}):
            rr=[r for r in rows if r['signal']==signal];countries=[r['country_id'] for r in rr]
            ys={o:np.array([np.log1p(r['metrics']['dhrd_hours']) if o=='log1p_dhrd' else r['metrics'][o] for r in rr],dtype=float) for o in OUTCOMES}
            for setting in ('A','B'):
                for model in ('M1','M2'):
                    x,z,names,omitted=design(rr,setting,model)
                    file=f'{signal}_{setting}_{model}.npz'
                    np.savez_compressed(out/file,x=x,z=z.toarray(),countries=np.array(countries),event_ids=np.array([r['event_id'] for r in rr]),**ys)
                    products[file]=Sources().verify(out/file)
                    result={o:estimate(x,y,z,countries,o!='log1p_dhrd') for o,y in ys.items()}
                    results.append(dict(signal=signal,setting=setting,model=model,terms=names,omitted=omitted,matrix=file,results=result))
        sources.check();publish('results.json',results)
        report=dict(status='completed',rows=len(rows),models=len(results),estimable_models=sum(r['results']['mean_deficit_core']['estimable'] for r in results),elapsed_seconds=time.monotonic()-start,scope='Equal-event main integral matching support, country/event-start year-month fixed effects, contemporaneous dewpoint; nested same-sample NTRD. No precipitation, causal identification, predictive validation, multiplicity correction or small-cluster certification. CR0 intervals preliminary. Log outcome slopes are not marginal DHRD-hour differences.')
        publish('summary.json',report)
        for n in ('results.json','summary.json'):products[n]=Sources().verify(out/n)
        publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products));publish('status.json',dict(status='completed'));print(json.dumps(report))
    except BaseException as e:publish('status.json',dict(status='failed',error=str(e)));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--panel',required=True);p.add_argument('--output',required=True);p.add_argument('--signal');run(p.parse_args())
