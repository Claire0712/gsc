"""Exact within-design-cell summaries; never fill missing ten-minute slots."""
import numpy as np

def summarize(times,values,baseline,available,day):
    t=np.asarray(times);v=np.asarray(values);b=np.asarray(baseline);a=np.asarray(available)
    if t.ndim!=1 or t.dtype.kind not in 'iu' or np.any(np.diff(t)<=0) or np.any(t%600):
        raise ValueError('Invalid timestamps')
    if any(q.shape!=t.shape for q in (v,b,a)) or a.dtype.kind!='b' or day%86400:
        raise ValueError('Invalid aligned day inputs')
    mask=(t>=day)&(t<day+86400)
    if not np.array_equal(t[mask],np.arange(day,day+86400,600)):
        raise ValueError('Missing slots')
    if not np.all(a[mask]&np.isfinite(v[mask])&(v[mask]>=0)&np.isfinite(b[mask])&(b[mask]>0)):
        raise ValueError('Unavailable slots')
    ratio=v[mask]/b[mask]
    if not np.isfinite(ratio).all():raise ValueError('Nonfinite ratio')
    out={'hour':np.arange(24),'count':np.full(24,6,dtype=np.int64)}
    for name,y in [('signed',ratio-1),('deficit',np.maximum(0,1-ratio)),('below95',(ratio<.95).astype(float))]:
        y=y.reshape(24,6);mean=y.mean(axis=1)
        out[name]=mean;out[name+'_within_ss']=np.sum((y-mean[:,None])**2,axis=1)
    return out
