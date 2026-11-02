"""Frozen observed common-support gate; no outcome-dependent peer selection."""
import numpy as np
from .heat_associations_v2 import design
DIMENSIONS=('hd_c_days','absolute_tmax_c','span_days','raw_pre_level','raw_pre_mad_over_median','coverage_fraction')
OUTCOMES=('mean_deficit_core','maintenance_core','peak_loss_core')
def joint_support(values,group,scales,caliper):
 x=np.asarray(values,float);g=np.asarray(group);s=np.asarray(scales,float)
 if x.ndim!=2 or len(g)!=len(x) or x.shape[1]!=len(s) or not np.isfinite(s).all() or np.any(s<0) or caliper<0:raise ValueError('Invalid support inputs')
 mask=np.zeros(len(x),bool);peer=np.full(len(x),-1,int);distance=np.full(len(x),np.inf)
 valid=np.isfinite(x).all(axis=1)
 for i in np.flatnonzero(valid):
  others=np.flatnonzero(valid&(g!=g[i]));delta=np.abs(x[others]-x[i]);scaled=np.zeros_like(delta)
  np.divide(delta,s,out=scaled,where=s>0);scaled[:,s==0]=np.where(delta[:,s==0]==0,0,np.inf)
  d=scaled.max(axis=1) if len(others) else np.array([])
  if len(d) and np.min(d)<=caliper:
   k=int(np.argmin(d));mask[i]=True;peer[i]=int(others[k]);distance[i]=float(d[k])
 return mask,peer,distance

def arm_counts(rows,group):
 return [dict(events=sum(int(v==g) for v in group),countries=len({r['country_id'] for r,v in zip(rows,group) if v==g})) for g in (0,1)]

def regional_design(rows,features,group):
 x,z,names,_=design(rows,'A','M2');f=np.asarray(features,float)
 return np.column_stack([x,f[:,1],f[:,3],f[:,4],x[:,0]*group]),z,names+['absolute_tmax_c','raw_pre_level','raw_pre_mad_over_median','hd_x_region']
