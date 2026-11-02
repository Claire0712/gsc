"""Local pixel Q90 and strict fixed-population spatial exceedance diagnostics."""
import warnings
import numpy as np

def pixel_thresholds(values,calendar_days,years,target_days):
 values=np.asarray(values,dtype=float);days=np.asarray(calendar_days,dtype=int);years=np.asarray(years,dtype=int);target=np.asarray(target_days,dtype=int)
 if values.ndim!=2 or values.shape[0]!=len(days) or days.shape!=years.shape or days.ndim!=1 or target.ndim!=1:raise ValueError('Reference day/cell arrays must align')
 if np.any((days<0)|(days>364)) or np.any((target<0)|(target>364)) or np.any(~np.isin(years,[2018,2019,2020,2021])):raise ValueError('Frozen four-year nonleap reference calendar required')
 if len(set(zip(years.tolist(),days.tolist())))!=len(days):raise ValueError('Duplicate reference date')
 q=np.full((len(target),values.shape[1]),np.nan);n=np.zeros(q.shape,dtype=int);ny=np.zeros(q.shape,dtype=int)
 for i,day in enumerate(target):
  take=np.minimum((days-day)%365,(day-days)%365)<=15;v=values[take];finite=np.isfinite(v);n[i]=finite.sum(axis=0)
  for year in range(2018,2022):ny[i]+=finite[years[take]==year].any(axis=0)
  if len(v):
   eligible=(n[i]>=112)&(ny[i]==4);complete=finite.all(axis=0)&eligible
   if complete.any():q[i,complete]=np.quantile(v[:,complete],.9,axis=0,method='linear')
   partial=eligible&~complete
   if partial.any():
    clean=np.where(finite[:,partial],v[:,partial],np.nan)
    with warnings.catch_warnings():
     warnings.simplefilter('ignore',RuntimeWarning);q[i,partial]=np.nanquantile(clean,.9,axis=0,method='linear')
  q[i,(n[i]<112)|(ny[i]!=4)]=np.nan
 return q,n,ny

def population_fraction(tmax,threshold,weights):
 tmax=np.asarray(tmax,dtype=float);threshold=np.asarray(threshold,dtype=float);weights=np.asarray(weights,dtype=float)
 if tmax.ndim!=2 or tmax.shape!=threshold.shape or weights.shape!=(tmax.shape[1],):raise ValueError('Day/cell arrays must align')
 if np.any(~np.isfinite(weights)) or np.any(weights<0) or not np.isclose(weights.sum(),1,rtol=0,atol=1e-10):raise ValueError('Original normalized finite nonnegative weights required')
 valid=np.isfinite(tmax)&np.isfinite(threshold);missing=(~valid)@weights
 result=((tmax>threshold)&valid)@weights
 result[np.any(~valid[:,weights>0],axis=1)]=np.nan
 return result,missing
