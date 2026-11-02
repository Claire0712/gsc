"""Low-degree event associations; explicit nonidentification and CR0 diagnostics."""
import numpy as np
from scipy import sparse,linalg
from .event_curve_core import fit
from .curve_inference import covariance

def design(rows,setting,model):
    if setting not in ('A','B') or model not in ('M1','M2'):raise ValueError('Unknown specification')
    names=['hd_c_days','span_days','dewpoint_mean_c'] if setting=='A' else ['peak_excess_c','hot_days','bridge_days','dewpoint_mean_c']
    omitted=[]
    if setting=='B' and all(r['exposure']['bridge_days']==0 for r in rows):
        names.remove('bridge_days');omitted=['bridge_days:identically_zero']
    if model=='M2':names.append('ntrd_c_days')
    x=np.array([[r['exposure'][k] for k in names] for r in rows],dtype=float)
    labels=[[('country',r['country_id']),('month',r['year_month'])] for r in rows]
    codes={k:i for i,k in enumerate(sorted({k for rr in labels for k in rr}))}
    z=sparse.csr_matrix((np.ones(2*len(rows)),(np.repeat(np.arange(len(rows)),2),[codes[k] for rr in labels for k in rr])),shape=(len(rows),len(codes)))
    return x,z,names,omitted

def estimate(x,y,z,countries,bounded):
    q=linalg.orth(z.toarray());xx=x-q@(q.T@x);norms=np.linalg.norm(xx,axis=0)
    rank_z=q.shape[1];base=dict(n=len(y),nuisance_rank=rank_z,countries=len(set(countries)))
    if len(y)-rank_z<=x.shape[1]:return dict(base,estimable=False,reason='No residual degrees of freedom')
    if np.any(norms<1e-9*np.maximum(1,np.linalg.norm(x,axis=0))):return dict(base,estimable=False,reason='Absorbed focal column')
    singular=np.linalg.svd(xx/norms,compute_uv=False)
    if singular[-1]/singular[0]<1e-9:return dict(base,estimable=False,reason='Focal design rank deficient')
    f=fit(x,y,z,np.ones(len(y)));v=covariance(f['residualized_x'],f['residual'],countries)
    beta=f['beta'];se=np.sqrt(np.diag(v));pred=y-f['residual']
    return dict(base,estimable=True,beta=beta.tolist(),covariance_country_cr0=v.tolist(),interval95_normal=np.column_stack([beta-1.959963984540054*se,beta+1.959963984540054*se]).tolist(),condition=f['condition'],rss=float(f['residual']@f['residual']),residual_df=len(y)-rank_z-x.shape[1],boundary_tolerance=1e-10,predicted_min=float(pred.min()),predicted_max=float(pred.max()),predicted_outside_unit_interval=int(np.count_nonzero((pred < -1e-10)|(pred > 1+1e-10))) if bounded else None)
