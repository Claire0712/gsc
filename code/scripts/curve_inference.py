"""CR0 asymptotic covariance diagnostics on weighted residualized regressors."""
import numpy as np
from scipy.stats import chi2
def covariance(x,u,groups):
    x=np.asarray(x,dtype=float);u=np.asarray(u,dtype=float)
    if x.ndim!=2 or u.shape!=(len(x),) or len(groups)!=len(x) or not np.isfinite(x).all() or not np.isfinite(u).all():raise ValueError('Invalid inputs')
    labels={g:i for i,g in enumerate(dict.fromkeys(groups))}
    if len(labels)<2:raise ValueError('At least two clusters required')
    scores=np.zeros((len(labels),x.shape[1]));np.add.at(scores,[labels[g] for g in groups],x*u[:,None])
    bread=np.linalg.inv(x.T@x);v=bread@(scores.T@scores)@bread
    return (v+v.T)/2
def diagnostics(beta,v,lead_indices):
    eig=np.linalg.eigvalsh(v);tol=max(float(np.max(np.abs(eig))),1e-30)*1e-10
    psd=bool(eig.min()>=-tol and np.all(np.diag(v)>=0));interval=None;test=None
    reason=None
    if psd:
        se=np.sqrt(np.diag(v));interval=np.column_stack([beta-1.959963984540054*se,beta+1.959963984540054*se]).tolist()
        a=v[np.ix_(lead_indices,lead_indices)];ev=np.linalg.eigvalsh(a)
        if ev.min()>max(float(ev.max()),1e-30)*1e-10:
            b=np.asarray(beta)[lead_indices];stat=float(b@np.linalg.solve(a,b));test=dict(chi2=stat,df=len(b),p_asymptotic=float(chi2.sf(stat,len(b))))
        else:reason='lead_covariance_rank_deficient'
    else:reason='covariance_not_psd_no_repair'
    return dict(psd=psd,min_eigenvalue=float(eig.min()),interval95=interval,lead_test=test,reason=reason)
