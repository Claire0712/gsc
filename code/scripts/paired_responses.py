"""Complete UTC-day responses and control-date reuse weights; no inference."""
from collections import defaultdict,Counter
import math
import numpy as np

def daily(times,values,baseline,available,start,end):
    t=np.asarray(times);v=np.asarray(values);b=np.asarray(baseline);a=np.asarray(available)
    if t.ndim!=1 or t.dtype.kind not in 'iu' or np.any(np.diff(t)<=0) or np.any(t%600):raise ValueError('Invalid timestamps')
    if any(x.shape!=t.shape for x in (v,b,a)) or a.dtype.kind!='b':raise ValueError('Invalid aligned arrays')
    if start%86400 or end%86400 or end<=start:raise ValueError('Complete UTC days required')
    select=(t>=start)&(t<end)
    if not np.array_equal(t[select],np.arange(start,end,600)):raise ValueError('Missing target slots')
    if not np.all(a[select]&np.isfinite(v[select])&(v[select]>=0)&np.isfinite(b[select])&(b[select]>0)):raise ValueError('Unavailable selected day')
    r=v[select]/b[select]
    if not np.isfinite(r).all():raise ValueError('Nonfinite ratio')
    r=r.reshape(-1,144)
    return [dict(date_utc=int(d),signed=float((x-1).mean()),deficit=float(np.maximum(0,1-x).mean()),below95=float((x<.95).mean())) for d,x in zip(range(start,end,86400),r)]

def weights(rows):
    sums=defaultdict(float);counts=Counter();seen=set()
    def key(r):return (r['signal'],r['purpose'],r['country_id'],r['date_utc'])
    for r in rows:
        identity=(r['group_id'],r['window_id'],r['signal'],r['purpose'],r['date_utc'])
        if identity in seen:raise ValueError('Duplicate stack occurrence')
        seen.add(identity)
        if r['role'] not in ('heat','control') or not math.isfinite(r['base_weight']) or r['base_weight']<=0:raise ValueError('Invalid role/weight')
        if r['role']=='control':sums[key(r)]+=r['base_weight'];counts[key(r)]+=1
    return [dict(r,weight=r['base_weight']/sums[key(r)] if r['role']=='control' else r['base_weight'],control_date_uses=counts[key(r)] if r['role']=='control' else 0,control_date_base_sum=sums[key(r)] if r['role']=='control' else 0) for r in rows]
