"""Limited proposal 9.3 products, preserving original A/M2 sample and main effects."""
import numpy as np
from .heat_associations import design

def interaction_design(rows,kind):
 if kind not in ('ntrd','dewpoint'):raise ValueError('Unknown fixed interaction')
 x,z,names,_=design(rows,'A','M2');modifier='ntrd_c_days' if kind=='ntrd' else 'dewpoint_mean_c'
 heat=x[:,names.index('hd_c_days')];m=x[:,names.index(modifier)];hc=float(heat.mean());mc=float(m.mean())
 if not np.isfinite(x).all():raise ValueError('Missing original exposure')
 return np.column_stack((x,(heat-hc)*(m-mc))),z,names+['hd_x_'+kind],dict(heat_mean=hc,modifier_mean=mc,modifier=modifier)
