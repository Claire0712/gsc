"""Identical-sample daily curve sensitivity before/after vector wind control."""
import argparse,csv,io,json,math,time
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from .build_climate_pilot import climate_files,load_climate
from .weather_pair_support import valid_controls
from .paired_responses import weights
from .run_event_curve import design,DAYS
from .event_curve_core import fit
from .run_connection_baseline import Sources,Stage
OUTCOMES=('signed','deficit','below95')

def subset(rows,lookup,cutoff,limit=0):
    groups=defaultdict(list)
    for r in rows:groups[r['group_id']].append(r)
    kept=[];count=0
    for event,rr in sorted(groups.items()):
        controls=valid_controls(rr,lookup,('u10_m_s','v10_m_s'),cutoff)
        if not controls:continue
        if limit and count>=limit:break
        count+=1
        for r in rr:
            if r['role']=='heat' or r['window_id'] in controls:
                kept.append(dict(r,base_weight=1. if r['role']=='heat' else 1./len(controls),matched_controls=len(controls)))
    return weights(kept)

def run(args):
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources();wind=Stage(args.wind,sources,status_key='status',manifest_key=('status','completed'))
    for p in climate_files(Path(args.data)):sources.verify(p)
    panel,_=load_climate(Path(args.data));lookup={(r['iso3'],r['date_utc']):r for r in panel.values() if r['iso3']}
    for n in ('wind_202402.csv','wind_202403.csv'):
        for r in csv.DictReader(io.StringIO(wind.read(n).decode())):
            if r['unit']!='m s**-1' or r['day_definition']!='UTC' or r['weight_year']!='2025':raise ValueError('Wind metadata mismatch')
            if not r['iso3']:continue
            key=r['iso3'],r['date'];v=lookup.setdefault(key,{});name=r['variable']+'_m_s'
            if name in v:raise ValueError('Duplicate wind day')
            v[name]=float(r['value']) if r['value'] else None
            v[name+'_population_fraction']=float(r['valid_population_fraction']) if r['valid_population_fraction'] else None
    for n in ('wind_curve.py','weather_pair_support.py','build_climate_pilot.py','paired_responses.py','run_event_curve.py','event_curve_core.py'):sources.verify(Path(__file__).with_name(n))
    out.mkdir(parents=True);report=[]
    def save(root,n,obj):(root/n).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
    save(out,'status.json',dict(status='running'))
    mapping={'ping-slash24':'ap','bgp':'bgp','merit-nt':'merit-nt'}
    for sig,label in mapping.items():
        if args.signal and sig!=args.signal:continue
        base=Stage(Path(args.base)/('full_'+label+'_outputs'),sources,status_key='status',manifest_key=('status','completed'))
        old=base.json('estimates.json');identities=base.json('row_identity.json');matrix=Path(base.directory)/'model_inputs.npz';sources.verify(matrix,base.outputs['model_inputs.npz'])
        with np.load(matrix) as z:
            rows=[dict(r,signal=sig,purpose='curve',date=datetime.fromtimestamp(int(r['date_utc']),timezone.utc).strftime('%Y-%m-%d'),dewpoint=float(z['x'][i,-1]),**{o:float(z[o][i]) for o in OUTCOMES}) for i,r in enumerate(identities)]
        kept=subset(rows,lookup,.95,args.limit_groups)
        record=dict(signal=sig,rows=len(kept),groups=len({r['group_id'] for r in kept}),countries=len({r['country_id'] for r in kept}),models={})
        if not kept:
            record['reason']='No complete95percent-support paired windows';report.append(record);continue
        for r in kept:
            v=lookup[r['country_id'],r['date']];r['wind_m_s']=math.hypot(v['u10_m_s'],v['v10_m_s'])
        x,z,w=design(kept)
        stack=out/(sig+'_stack.json');save(out,stack.name,kept)
        for addwind in (False,True):
            name='wind' if addwind else 'base';root=out/(sig+'_'+name);root.mkdir()
            xx=np.column_stack([x,[r['wind_m_s'] for r in kept]]) if addwind else x
            results={};reason=None
            try:
                for o in OUTCOMES:
                    f=fit(xx,np.array([r[o] for r in kept]),z,w)
                    results[o]=dict(beta=f['beta'].tolist(),condition=f['condition'],projection=f['projection'],weighted_residual_ss=float(f['residual']@f['residual']))
            except ValueError as e:reason=str(e)
            if reason:
                save(root,'status.json',dict(status='not_estimable',reason=reason));record['models'][name]=dict(estimable=False,reason=reason);continue
            np.savez_compressed(root/'model_inputs.npz',x=xx,z_data=z.data,z_indices=z.indices,z_indptr=z.indptr,z_shape=z.shape,weights=w,**{o:np.array([r[o] for r in kept]) for o in OUTCOMES})
            save(root,'row_identity.json',[{k:r[k] for k in ('group_id','window_id','country_id','date_utc','relative_day','role')} for r in kept])
            save(root,'estimates.json',dict(signal=sig,rows=len(kept),groups=record['groups'],countries=record['countries'],terms=['heat_day_'+str(k) for k in DAYS]+['dewpoint_c']+(['wind_m_s'] if addwind else []),reference_day=-1,results=results,scope='Daily sensitivity, identical95percent-support paired sample; country-weekday rather than primary hour-weekday FE. Archived fine-grid weight limitation retained; no gust/causal/full-period claim.'))
            sources.check();save(root,'manifest.json',dict(status='completed',inputs=sources.entries,outputs={n:Sources().verify(root/n) for n in ('model_inputs.npz','row_identity.json','estimates.json')}));save(root,'status.json',dict(status='completed'));record['models'][name]=dict(estimable=True)
        report.append(record)
    sources.check();save(out,'summary.json',dict(signals=report,elapsed_seconds=time.monotonic()-start,coverage=.95,scope='Same supported records, recomputed control-date reuse weights. Wind is magnitude of country daily mean components, not mean speed/gust. Source native-population reassignment certification remains incomplete; exploratory sensitivity only.'))
    products={str(p.relative_to(out)):Sources().verify(p) for p in out.rglob('*') if p.is_file() and p.name!='status.json'}
    save(out,'manifest.json',dict(status='completed',inputs=sources.entries,outputs=products));save(out,'status.json',dict(status='completed'));print((out/'summary.json').read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('wind','data','base','output'):p.add_argument('--'+n,required=True)
    p.add_argument('--signal');p.add_argument('--limit-groups',type=int,default=0);run(p.parse_args())
