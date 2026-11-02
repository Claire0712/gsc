"""Pixel mean-solar day statistics, exact existing hourly samples, no filling."""
import numpy as np
def extrema(times,values,longitude,days):
 times=np.asarray(times,dtype=np.int64);values=np.asarray(values,dtype=float);longitude=np.asarray(longitude,dtype=float)
 if values.shape!=(len(times),len(longitude)) or np.any(np.diff(times)<=0):raise ValueError('Unique sorted hour by pixel input required')
 if np.any(~np.isfinite(longitude)) or np.any(abs(longitude)>180):raise ValueError('Signed longitude required')
 labels=np.floor((times[:,None]+longitude[None,:]*240)/86400).astype(np.int64)
 result={k:np.full((len(days),len(longitude)),np.nan) for k in ('tmin_c','tmax_c','mean_c')}
 for di,day in enumerate(days):
  for cell in range(len(longitude)):
   keep=labels[:,cell]==day;tt=times[keep];v=values[keep,cell]
   if len(v)!=24 or np.any(np.diff(tt)!=3600) or not np.isfinite(v).all():continue
   result['tmin_c'][di,cell]=v.min()-273.15;result['tmax_c'][di,cell]=v.max()-273.15;result['mean_c'][di,cell]=v.mean()-273.15
 return result
