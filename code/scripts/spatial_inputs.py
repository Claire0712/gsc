"""Exact source-grid coordinates and supported spatial comparison inputs."""
import math,datetime as dt

def signed_grid_longitude(index,longitudes):
 if int(index)!=index or index<0 or not len(longitudes):raise ValueError('Nonnegative integer cell index and source coordinate array required')
 value=float(longitudes[int(index)%len(longitudes)])
 if not math.isfinite(value):raise ValueError('Nonfinite source longitude')
 return (value+180)%360-180

def supported_country_day(pixel_fraction,tmax):
 return math.isfinite(float(pixel_fraction)) and math.isfinite(float(tmax))

def country_threshold(country,date,lookup):
 date=dt.date.fromisoformat(date)
 if date.month==2 and date.day==29:return (lookup[country,58]+lookup[country,59])/2
 return lookup[country,(dt.date(2001,date.month,date.day)-dt.date(2001,1,1)).days]
