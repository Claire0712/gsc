"""Finite weighted descriptive quantities; no inference."""
import math
def summary(values,weights):
    if not values or len(values)!=len(weights):raise ValueError('Nonempty aligned inputs required')
    if any(v is None or not math.isfinite(v) for v in values) or any(not math.isfinite(w) or w<=0 for w in weights):raise ValueError('Finite data and positive weights required')
    total=math.fsum(weights);mean=math.fsum(v*w for v,w in zip(values,weights))/total
    return dict(mean=mean,variance=math.fsum(w*(v-mean)**2 for v,w in zip(values,weights))/total,total_weight=total,n=len(values))
def paired(heat,controls):
    return heat-summary(controls,[1]*len(controls))['mean']
