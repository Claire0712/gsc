"""Preselected MYS January 2024 spatial fraction pilot from existing raw hours."""
from pathlib import Path
import json,csv,time,datetime as dt
import numpy as np
from netCDF4 import Dataset
from .aggregate_era5_country_daily import load_weight_bundle,validate_temperature_units
from .run_connection_baseline import Sources
from .pixel_exceedance import pixel_thresholds,population_fraction
started=time.monotonic();out=Path('analysis/2026-10-31_pixel_exceedance/v1/pilot_mys_202401');assert not out.exists();sources=Sources();wd=Path('analysis/2026-10-06_era5_existing_data/weights')
for name in ('weights.npz','country_metadata.csv','weights_metadata.json'):sources.verify(wd/name)
b=load_weight_bundle(wd/'weights.npz',wd/'country_metadata.csv',wd/'weights_metadata.json');meta=list(csv.DictReader((wd/'country_metadata.csv').open()));ci=next(i for i,r in enumerate(meta) if r['country_id']=='MYS');w=b['weights'].getrow(ci);rr=w.indices//1440;cc=w.indices%1440;mass=w.data;assert np.all(mass>0) and np.isclose(mass.sum(),1)
for p in (Path(__file__),Path(__file__).with_name('pixel_exceedance.py'),Path('docs/superpowers/specs/2026-10-31-pixel-exceedance.md')):sources.verify(p)
refvalues=[];refdates=[];timings=[]
def read(month):
 tick=time.monotonic();path=Path('/volume1/homes/Judy/GSC2027/era5')/('era5_2m_'+month+'.nc');sources.verify(path)
 dates=np.arange(np.datetime64(month[:4]+'-'+month[4:]+'-01'),np.datetime64(month[:4]+'-'+month[4:]+'-01')+np.timedelta64(1,'M').astype('timedelta64[D]')) if False else None
 start=np.datetime64(month[:4]+'-'+month[4:]+'-01');stop=(start.astype('datetime64[M]')+1).astype('datetime64[D]');dates=np.arange(start,stop)
 with Dataset(path) as nc:
  assert nc.variables['valid_time'].units=='seconds since 1970-01-01';validate_temperature_units(nc.variables['t2m'].units)
  np.testing.assert_array_equal(nc.variables['valid_time'][:],np.arange(int(start.astype(int))*86400,int(stop.astype(int))*86400,3600,dtype=np.int64))
  for key in ('latitude','longitude'):np.testing.assert_array_equal(nc.variables[key][:],b['grid'][key])
  tile=np.asarray(np.ma.filled(nc.variables['t2m'][:,rr.min():rr.max()+1,cc.min():cc.max()+1],np.nan),dtype=float)
  hourly=tile[:,rr-rr.min(),cc-cc.min()].reshape(len(dates),24,len(mass));daily=hourly.max(axis=1)-273.15;daily[~np.isfinite(hourly).all(axis=1)]=np.nan
 timings.append(dict(month=month,seconds=time.monotonic()-tick));print(json.dumps(timings[-1]),flush=True);return dates,daily
for year in range(2018,2022):
 for month in (1,2,12):
  dates,v=read(f'{year}{month:02d}');keep=np.array([str(d)[5:]!='02-29' for d in dates]);refdates.extend(dates[keep]);refvalues.append(v[keep])
refdates=np.array(refdates,dtype='datetime64[D]');reference=np.concatenate(refvalues);targetdates,values=read('202401')
cd=lambda d:(dt.date(2001,int(str(d)[5:7]),int(str(d)[8:10]))-dt.date(2001,1,1)).days
cal=np.array([cd(d) for d in refdates]);years=np.array([int(str(d)[:4]) for d in refdates]);target=np.array([cd(d) for d in targetdates]);tick=time.monotonic();q,n,ny=pixel_thresholds(reference,cal,years,target);fraction,missing=population_fraction(values,q,mass);threshold_seconds=time.monotonic()-tick
nationpath=Path('analysis/2026-10-31_solar_catalogue/v1/full_outputs/utc/thresholds.csv');sources.verify(nationpath);national={int(r['calendar_day']):float(r['q90_tmax_c']) for r in csv.DictReader(nationpath.open()) if r['country_id']=='MYS'}
sources.check();out.mkdir(parents=True);np.savez_compressed(out/'daily_pixels.npz',reference=reference,reference_days=refdates.astype(int),reference_calendar=cal,reference_years=years,target=values,target_days=targetdates.astype(int),target_calendar=target,threshold=q,reference_n=n,reference_year_count=ny,weights=mass,grid_indices=w.indices,fraction=fraction,missing_population_fraction=missing)
rows=[]
for i,date in enumerate(targetdates):
 mean=float(values[i]@mass) if np.isfinite(values[i]).all() else None;threshold=float(national[target[i]])
 rows.append(dict(country_id='MYS',date=str(date),pixel_exceedance_population_fraction=float(fraction[i]) if np.isfinite(fraction[i]) else None,missing_population_fraction=float(missing[i]),utc_country_tmax_c=mean,utc_country_q90_tmax_c=threshold,utc_country_hot=mean>threshold if mean is not None else None))
(out/'country_daily.json').write_text(json.dumps(rows,indent=2,allow_nan=False)+'\n')
summary=dict(country='MYS',target_month='202401',positive_cells=len(mass),country_days=len(targetdates),reference_dates_loaded=len(refdates),input_months=[x['month'] for x in timings],threshold_seconds=threshold_seconds,elapsed_seconds=time.monotonic()-started,scope='Preselected one-country/month pilot: pixel-specific four-year local Q90 and original fixed population masses. Not full spatial or network-effect acceptance.')
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(out/'manifest.json').write_text(json.dumps(dict(inputs=sources.entries,outputs={n:Sources().verify(out/n) for n in ('daily_pixels.npz','country_daily.json','summary.json')}),indent=2)+'\n');print(json.dumps(summary),flush=True)
