"""Frozen exploratory one-modifier heat interactions with support gates."""
import argparse,csv,io,json,time
from pathlib import Path
import numpy as np
from scipy import sparse
from scipy.stats import norm
from statsmodels.stats.multitest import multipletests
from .heat_associations_v2 import design,estimate
from .run_connection_baseline import Sources,Stage

MODIFIERS=('pre_connection_dispersion','electricity_access_share','gdp_per_capita_ppp_constant','urban_population_share','internet_share','first_warm_season_event')
OUTCOMES=('mean_deficit_core','maintenance_core','peak_loss_core')
def support_mask(values,group):
    if set(group)!={0,1}:raise ValueError('Two groups required')
    bounds=[(float(max(v[group==0].min(),v[group==1].min())),float(min(v[group==0].max(),v[group==1].max()))) for v in values.T]
    mask=np.ones(len(group),dtype=bool)
    for v,(lo,hi) in zip(values.T,bounds):mask&=(v>=lo)&(v<=hi)
    return mask,bounds

def value(r,name):
    if name=='pre_connection_dispersion':return r[name]['value']
    if name=='first_warm_season_event':return r['warm_season'][name]
    return r['modifiers'][name]['value']

def run(args):
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources();panel=Stage(args.panel,sources,status_key='status',manifest_key=('status','completed'))
    mods=Stage(args.modifiers,sources,status_key='status',manifest_key=('status','completed'))
    comp=Stage(args.comparison,sources,status_key='status',manifest_key=('status','completed'))
    index={(r['event_id'],r['signal']):r for r in mods.json('rows.json')}
    audits={(r['window_id'],r['signal']):r for r in csv.DictReader(io.StringIO(comp.read('window_audit.csv').decode()))}
    rows=[r for r in panel.json('rows.json') if r['matched_integral'] and (not args.signal or r['signal']==args.signal)]
    result=[];products={};out.mkdir(parents=True)
    def save(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    save('status.json',dict(status='running'))
    for sig in sorted({r['signal'] for r in rows}):
        for name in MODIFIERS:
            rr=[];vv=[];support=[]
            for r in rows:
                if r['signal']!=sig:continue
                mod=index[r['event_id'],sig];v=value(mod,name);a=audits['heat:'+r['event_id'],sig]
                if v is None:continue
                ss=[r['exposure'][k] for k in ('hd_c_days','absolute_tmax_c','span_days')]+[float(a['raw_pre_level']),float(a['raw_pre_mad_over_median'])]
                if not np.isfinite(ss).all():continue
                rr.append(r);vv.append(float(v));support.append(ss)
            v=np.array(vv);group=(v>(.5 if name=='first_warm_season_event' else np.median(v))).astype(int) if len(v) else np.array([])
            rec=dict(signal=sig,modifier=name,available=len(rr),family_size=54,results={})
            if set(group)!={0,1}:
                rec.update(supported=False,reason='Modifier split has fewer than two groups');result.append(rec);continue
            mask,bounds=support_mask(np.array(support),group);kept=[r for r,b in zip(rr,mask) if b]
            counts=[dict(events=int(np.sum(mask&(group==g))),countries=len({r['country_id'] for r,b,h in zip(rr,mask,group) if b and h==g})) for g in (0,1)]
            rec.update(support_bounds=bounds,post_support=counts,n=len(kept))
            if any(c['events']<10 or c['countries']<5 for c in counts):
                rec.update(supported=False,reason='Below10 events or5 countries in a support group');result.append(rec);continue
            scale=1. if name=='first_warm_season_event' else float(v.std())
            centered=(v-v.mean())/scale;mm=centered[mask]
            x,z,terms,_=design(kept,'A','M2');x=np.column_stack([x,x[:,0]*mm]);z=sparse.hstack([z,sparse.csr_matrix(mm[:,None])],format='csr')
            ys={o:np.array([r['metrics'][o] for r in kept]) for o in OUTCOMES};countries=[r['country_id'] for r in kept]
            filename=sig+'_'+name+'.npz';np.savez_compressed(out/filename,x=x,z=z.toarray(),countries=np.array(countries),event_ids=np.array([r['event_id'] for r in kept]),**ys)
            products[filename]=Sources().verify(out/filename)
            for outcome,y in ys.items():
                fit=estimate(x,y,z,countries,True)
                if fit['estimable']:
                    beta=fit['beta'][-1];se=float(np.sqrt(fit['covariance_country_cr0'][-1][-1]))
                    fit['interaction_p_normal']=float(2*norm.sf(abs(beta/se))) if se>0 else None
                rec['results'][outcome]=fit
            rec.update(supported=True,matrix=filename,modifier_center=float(v.mean()),modifier_scale=scale,terms=terms+['hd_x_modifier'])
            result.append(rec)
    family=[];links=[]
    for r in result:
        for o in OUTCOMES:
            p=r['results'].get(o,{}).get('interaction_p_normal');family.append(1. if p is None else p);links.append((r,o))
    # Pilot retains the full planned 54-test family as p=1 placeholders.
    padded=family+[1.]*(54-len(family));bh=multipletests(padded,method='fdr_bh')[1];by=multipletests(padded,method='fdr_by')[1]
    for (r,o),b,y in zip(links,bh,by):r.setdefault('adjustment',{})[o]=dict(bh=float(b),by=float(y))
    for n in ('modifier_models.py','heat_associations_v2.py','event_curve_core.py','curve_inference.py'):sources.verify(Path(__file__).with_name(n))
    sources.check();save('results.json',result)
    save('summary.json',dict(models=len(result),supported=sum(r['supported'] for r in result),estimated=sum(f['estimable'] for r in result for f in r['results'].values()),elapsed_seconds=time.monotonic()-start,scope='Exploratory equal-event conditional linear interactions;5-dimensional marginal range restriction, not joint overlap proof. Full54-test BH/BY using normal country-CR0 p values. No causality, predictive calibration, probability validity or country ranking.'))
    for n in ('results.json','summary.json'):products[n]=Sources().verify(out/n)
    save('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products));save('status.json',dict(status='completed'));print((out/'summary.json').read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('panel','modifiers','comparison','output'):p.add_argument('--'+n,required=True)
    p.add_argument('--signal');run(p.parse_args())
