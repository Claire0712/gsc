"""Fixed-population circular-mean country clock, exact hourly day selection."""
import numpy as np

def circular_longitudes(weights,longitude):
 longitude=np.asarray(longitude,dtype=float);data=np.asarray(weights.data if hasattr(weights,'data') else weights)
 if len(weights.shape)!=2 or weights.shape[1]!=len(longitude) or longitude.ndim!=1 or np.any(~np.isfinite(longitude)) or np.any(np.abs(longitude)>180):raise ValueError('Signed longitude must align with weight columns')
 if np.any(~np.isfinite(data)) or np.any(data<0):raise ValueError('Finite nonnegative population weights required')
 total=np.asarray(weights.sum(axis=1)).ravel();x=np.asarray(weights@np.cos(np.deg2rad(longitude))).ravel();y=np.asarray(weights@np.sin(np.deg2rad(longitude))).ravel();resultant=np.divide(np.hypot(x,y),total,out=np.full(len(total),np.nan),where=total>0)
 lon=(np.rad2deg(np.arctan2(y,x))+180)%360-180;lon[(total<=0)|(~np.isfinite(resultant))|(resultant<=1e-12)]=np.nan
 return lon,resultant

def fixed_offset_extrema(times,values,offset,days):
 times=np.asarray(times,dtype=np.int64);values=np.asarray(values);days=np.asarray(days,dtype=np.int64)
 if times.ndim!=1 or not len(times) or np.any(times%3600) or np.any(np.diff(times)!=3600) or values.ndim!=2 or values.shape[0]!=len(times) or days.ndim!=1:raise ValueError('Continuous aligned epoch-hour input required; gaps explicit NaN')
 if int(offset)!=offset or abs(offset)>12:raise ValueError('Bounded integer first-hour offset required')
 begins=(days*86400-times[0])//3600+int(offset);ix=begins[:,None]+np.arange(24)[None,:];available=(ix>=0)&(ix<len(times));v=values[np.clip(ix,0,len(times)-1)];valid=available.all(axis=1)[:,None]&np.isfinite(v).all(axis=1)
 result=dict(tmin_c=v.min(axis=1).astype(float)-273.15,tmax_c=v.max(axis=1).astype(float)-273.15,mean_c=np.mean(v,axis=1,dtype=float)-273.15)
 for x in result.values():x[~valid]=np.nan
 return result
