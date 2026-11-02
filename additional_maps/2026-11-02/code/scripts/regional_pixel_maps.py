"""Descriptive pixel summaries. No interpolation, imputation or network inference."""
import numpy as np

def summarize_days(values,threshold,dates,national_hot):
 v=np.asarray(values,float);q=np.asarray(threshold,float);d=np.asarray(dates,dtype='datetime64[D]');nh=np.asarray(national_hot)
 if v.ndim!=2 or q.shape!=v.shape or len(d)!=len(v) or nh.shape!=d.shape or nh.dtype!=bool or len(np.unique(d))!=len(d) or np.any(np.diff(d.astype(int))<=0):raise ValueError('Aligned unique ordered day/cell arrays and boolean national flags required')
 years=d.astype('datetime64[Y]').astype(int)+1970;months=d.astype('datetime64[M]').astype(int)%12+1
 if np.any(~np.isin(years,[2022,2023,2024,2025])):raise ValueError('Frozen study years only')
 va=np.isfinite(v);vr=va&np.isfinite(q);hot=(v>q)&vr;absolute=(v>35)&va;nonhot=~nh
 def strict_count(mask,valid,hit):
  out=hit[mask].sum(axis=0).astype(float)
  if not mask.any():out[:]=np.nan
  else:out[~valid[mask].all(axis=0)]=np.nan
  return out
 allmask=np.ones(len(d),bool);a=strict_count(allmask,va,absolute)/4;b=strict_count(allmask,vr,hot)/4;c=strict_count(nonhot,vr,hot)/int(nonhot.sum()) if nonhot.any() else np.full(v.shape[1],np.nan)
 annual=np.stack([strict_count(years==y,vr,hot)/np.count_nonzero(years==y)*100 if (years==y).any() else np.full(v.shape[1],np.nan) for y in range(2022,2026)])
 season=np.stack([strict_count(np.isin(months,mm),vr,hot)/np.count_nonzero(np.isin(months,mm))*100 if np.isin(months,mm).any() else np.full(v.shape[1],np.nan) for mm in ((12,1,2),(3,4,5),(6,7,8),(9,10,11))])
 return dict(absolute_days_per_year=a,relative_days_per_year=b,local_hot_on_national_nonhot_fraction=c,annual_relative_percent=annual,season_relative_percent=season,absolute_valid_days=va.sum(axis=0),relative_valid_days=vr.sum(axis=0),national_nonhot_days=int(nonhot.sum()))

def json_scalar(value):
 if isinstance(value,np.generic):return value.item()
 raise TypeError('Unexpected JSON metadata type: '+type(value).__name__)
