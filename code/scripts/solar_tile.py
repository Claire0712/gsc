"""Bounded vectorized exact solar-hour gathering; scalar-verified separately."""
import numpy as np
def reduce_tile(times,values,longitude,days):
 times=np.asarray(times,dtype=np.int64);values=np.asarray(values,dtype=float);longitude=np.asarray(longitude,dtype=float);days=np.asarray(days,dtype=np.int64)
 if not len(times) or np.any(times%3600) or np.any(np.diff(times)!=3600):raise ValueError('Continuous epoch-hour grid required; absent hours must remain explicit NaN')
 if values.shape!=(len(times),len(longitude)) or np.any(~np.isfinite(longitude)) or np.any(abs(longitude)>180):raise ValueError('Signed longitude and aligned hour/cell array required')
 begins=(days*86400-times[0])//3600
 offset=np.ceil(-longitude/15).astype(np.int64)
 index=begins[:,None,None]+np.arange(24)[None,:,None]+offset[None,None,:]
 available=(index>=0)&(index<len(times));hourly=values[np.clip(index,0,len(times)-1),np.arange(len(longitude))[None,None,:]]
 valid=available.all(axis=1)&np.isfinite(hourly).all(axis=1)
 result=dict(tmin_c=hourly.min(axis=1)-273.15,tmax_c=hourly.max(axis=1)-273.15,mean_c=hourly.mean(axis=1)-273.15)
 for v in result.values():v[~valid]=np.nan
 return result
