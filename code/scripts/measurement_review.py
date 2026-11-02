"""Diagnostic candidates only: real network changes can produce these flags."""
import numpy as np

def diagnose(times,values,pre):
    t=np.asarray(times);v=np.asarray(values,dtype=float);pre=np.asarray(pre,dtype=bool)
    if t.ndim!=1 or v.shape!=t.shape or pre.shape!=t.shape or len(t)<144 or np.any(np.diff(t)!=600):raise ValueError('Invalid grid')
    valid=np.isfinite(v)&(v>=0)
    available=int(pre.sum())==1008 and bool(valid[pre].all())
    median=float(np.median(v[pre])) if available else None
    available=available and median>0
    result=dict(normalized_diagnostics_available=bool(available),pre_median=median,pre_iqr_over_median=None,last_day_ratio=None,longest_nearzero_slots=None,flags=[],confirmed_measurement_fault=False,primary_exclusion=False)
    if not available:return result
    q=np.quantile(v[pre],[.25,.75],method='linear')
    iqr=float((q[1]-q[0])/median)
    near=valid&(v<=median*.01)
    longest=run=0
    for flag in near:
        run=run+1 if flag else 0;longest=max(run,longest)
    ratio=float(np.median(v[-144:])/median) if valid[-144:].all() else None
    result.update(pre_iqr_over_median=iqr,last_day_ratio=ratio,longest_nearzero_slots=longest)
    if longest>=144:result['flags'].append('nearzero_24h')
    if iqr>1:result['flags'].append('pre_variability_candidate')
    if ratio is not None and (ratio<=.5 or ratio>=2):result['flags'].append('level_change_candidate')
    return result
