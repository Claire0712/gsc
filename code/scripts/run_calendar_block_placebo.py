"""Original daily design on supported exact calendar-block translations."""
import argparse,json,time
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from .run_connection_baseline import Sources,Stage
from .run_event_curve import design,DAYS
from .event_curve_core import fit
from .calendar_block_placebo import translated,source_lookup

def run(args):
 started=time.monotonic();out=Path(args.output)
 if out.exists():raise FileExistsError(out)
 sources=Sources();results=[];out.mkdir(parents=True)
 def save(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
 save(out/'status.json',dict(status='running'))
 for sig,label in [('ping-slash24','ap'),('bgp','bgp'),('merit-nt','merit-nt')]:
  if args.signal and sig!=args.signal:continue
  base=Stage(Path(args.base)/('full_'+label+'_outputs'),sources,status_key='status',manifest_key=('status','completed'))
  original=base.json('row_identity.json');path=Path(base.directory)/'model_inputs.npz';sources.verify(path,base.outputs['model_inputs.npz'])
  with np.load(path) as z:
   rows=[dict(r,signal=sig,purpose='curve',date=datetime.fromtimestamp(int(r['date_utc']),timezone.utc).strftime('%Y-%m-%d'),dewpoint=float(z['x'][i,-1]),**{o:float(z[o][i]) for o in ('signed','deficit','below95')}) for i,r in enumerate(original)]
  lookup,conflicts=source_lookup(rows);kept=translated(rows,args.shift,lookup,args.limit_groups)
  record=dict(signal=sig,shift_days=args.shift,conflicting_source_dates=conflicts,source_groups=len({r['group_id'] for r in rows}),groups=len({r['group_id'] for r in kept}),countries=len({r['country_id'] for r in kept}),rows=len(kept))
  if not kept:record.update(estimable=False,reason='No original group with complete translated anchor/control source dates');results.append(record);continue
  save(out/(sig+'_stack.json'),kept)
  x,z,w=design(kept);models={};reason=None
  try:
   for o in ('signed','deficit','below95'):
    f=fit(x,np.array([r[o] for r in kept]),z,w);models[o]=dict(beta=f['beta'].tolist(),condition=f['condition'],projection=f['projection'],weighted_residual_ss=float(f['residual']@f['residual']))
  except ValueError as e:reason=str(e)
  target=out/sig;target.mkdir()
  if reason:save(target/'status.json',dict(status='not_estimable',reason=reason));record.update(estimable=False,reason=reason);results.append(record);continue
  np.savez_compressed(target/'model_inputs.npz',x=x,z_data=z.data,z_indices=z.indices,z_indptr=z.indptr,z_shape=z.shape,weights=w,**{o:np.array([r[o] for r in kept]) for o in ('signed','deficit','below95')})
  save(target/'row_identity.json',[{k:r[k] for k in ('group_id','window_id','country_id','date_utc','relative_day','role')} for r in kept])
  save(target/'estimates.json',dict(signal=sig,rows=len(kept),groups=record['groups'],countries=record['countries'],terms=['heat_day_'+str(k) for k in DAYS]+['dewpoint_c'],reference_day=-1,results=models,scope='Original labels are translated pseudo-design roles, not actual shifted-date heat labels. Source responses/dewpoint move together in intact calendar blocks; exact shifted calendar nuisance effects. Sparse original-window support only; no rematching, wrapping, imputation, permutation p-value or causal identification.'))
  for n in ('run_calendar_block_placebo.py','calendar_block_placebo.py','run_event_curve.py','event_curve_core.py','paired_responses.py'):sources.verify(Path(__file__).with_name(n))
  sources.check();save(target/'manifest.json',dict(status='completed',inputs=sources.entries,outputs={n:Sources().verify(target/n) for n in ('model_inputs.npz','row_identity.json','estimates.json')}));save(target/'status.json',dict(status='completed'))
  record['estimable']=True;results.append(record)
 sources.check();save(out/'summary.json',dict(signals=results,elapsed_seconds=time.monotonic()-started,scope='Supported calendar-block translation only, not complete country-year source series, nonheat-only placebo or whole-study acceptance. Missing/conflicting source dates excluded, no wrapping or imputation, no selection of offsets by effects.'))
 save(out/'manifest.json',dict(status='completed',inputs=sources.entries,outputs={str(p.relative_to(out)):Sources().verify(p) for p in out.rglob('*') if p.is_file() and p.name not in ('status.json','manifest.json')}));save(out/'status.json',dict(status='completed'));print((out/'summary.json').read_text())

if __name__=='__main__':
 p=argparse.ArgumentParser()
 for name in ('base','output'):p.add_argument('--'+name,required=True)
 p.add_argument('--shift',type=int,required=True);p.add_argument('--signal');p.add_argument('--limit-groups',type=int,default=0);run(p.parse_args())
