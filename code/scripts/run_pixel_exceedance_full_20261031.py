"""Bounded existing-source spatial diagnostic; per-tile independent audit gates."""
from pathlib import Path
import calendar,csv,datetime as dt,json,time,subprocess,sys
import numpy as np
from netCDF4 import Dataset
from .aggregate_era5_country_daily import load_weight_bundle,validate_temperature_units
from .run_connection_baseline import Sources
from .pixel_exceedance_v2 import pixel_thresholds
started=time.monotonic();out=Path('analysis/2026-10-31_pixel_exceedance/v1/full_outputs');assert not out.exists();out.mkdir(parents=True);sources=Sources()
save=lambda name,value:(out/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
save('status.json',dict(status='running',phase='input_hashes'))
pilot=Path('analysis/2026-10-31_pixel_exceedance/v1/pilot_mys_202401');verified=json.loads(sources.read(pilot.parent/'pilot_mys_202401.verify.json'));assert verified['status']=='verified';import hashlib;assert hashlib.sha256(sources.read(pilot/'manifest.json')).hexdigest()==verified['manifest_sha256']
wd=Path('analysis/2026-10-06_era5_existing_data/weights');b=load_weight_bundle(wd/'weights.npz',wd/'country_metadata.csv',wd/'weights_metadata.json');w=b['weights'].tocsr();meta=list(csv.DictReader((wd/'country_metadata.csv').open()));assert len(meta)==w.shape[0]
for name in ('weights.npz','country_metadata.csv','weights_metadata.json'):sources.verify(wd/name)
for p in (Path(__file__),Path(__file__).with_name('pixel_exceedance_v2.py'),Path('outputs/2026-10-31_verify_pixel_sample.py'),Path('docs/superpowers/specs/2026-10-31-pixel-exceedance.md')):sources.verify(p)
months=[f'{y}{m:02d}' for y in range(2018,2026) for m in range(1,13)]
for month in months:
 path=Path('/volume1/homes/Judy/GSC2027/era5')/('era5_2m_'+month+'.nc');previous=json.loads(sources.read(Path('analysis/2026-10-30_solar_day/v1')/('full_'+month)/'manifest.json'));expected=previous['inputs'][str(path)];sources.verify(path,expected)
 print(json.dumps(dict(phase='input_hashes',month=month,elapsed_seconds=time.monotonic()-started)),flush=True)
ref_dates=np.arange(np.datetime64('2018-01-01'),np.datetime64('2022-01-01'));ref_dates=ref_dates[np.array([str(d)[5:]!='02-29' for d in ref_dates])];target_dates=np.arange(np.datetime64('2022-01-01'),np.datetime64('2026-01-01'));nd=len(target_dates);nc=w.shape[0]
cd=lambda date:-1 if str(date)[5:]=='02-29' else (dt.date(2001,int(str(date)[5:7]),int(str(date)[8:10]))-dt.date(2001,1,1)).days
refcal=np.array([cd(d) for d in ref_dates]);refyears=np.array([int(str(d)[:4]) for d in ref_dates]);targetcal=np.array([cd(d) for d in target_dates]);target0=int(target_dates[0].astype(int));total=np.zeros((nd,nc));missing=np.zeros_like(total);utc=np.zeros_like(total);utc_missing=np.zeros_like(total);sample_index=[];timings=[]
def read(month,lat0,lat1,lon0,lon1,occupied):
 begin=np.datetime64(month[:4]+'-'+month[4:]+'-01');end=(begin.astype('datetime64[M]')+1).astype('datetime64[D]');dates=np.arange(begin,end);path=Path('/volume1/homes/Judy/GSC2027/era5')/('era5_2m_'+month+'.nc')
 with Dataset(path) as f:
  assert f.variables['valid_time'].units=='seconds since 1970-01-01';validate_temperature_units(f.variables['t2m'].units)
  np.testing.assert_array_equal(f.variables['valid_time'][:],np.arange(int(begin.astype(int))*86400,int(end.astype(int))*86400,3600,dtype=np.int64))
  for coordinate in ('latitude','longitude'):np.testing.assert_array_equal(f.variables[coordinate][:],b['grid'][coordinate])
  raw=np.asarray(np.ma.filled(f.variables['t2m'][:,lat0:lat1,lon0:lon1],np.nan),dtype=np.float32).reshape(len(dates)*24,-1);hourly=raw[:,occupied].astype(float).reshape(len(dates),24,len(occupied));v=hourly.max(axis=1)-273.15;v[~np.isfinite(hourly).all(axis=1)]=np.nan
 return dates,v
for lat0 in range(0,721,121):
 for lon0 in range(0,1440,240):
  lat1=min(721,lat0+121);lon1=min(1440,lon0+240);indices=(np.arange(lat0,lat1)[:,None]*1440+np.arange(lon0,lon1)[None,:]).ravel();tw=w[:,indices];occupied=np.flatnonzero(np.asarray(tw.sum(axis=0)).ravel()>0)
  if not len(occupied):continue
  tick=time.monotonic();tw=tw[:,occupied].tocsr();indices=indices[occupied];pieces=[];dates_list=[]
  for month in months[:48]:
   dates,v=read(month,lat0,lat1,lon0,lon1,occupied);keep=np.array([str(d)[5:]!='02-29' for d in dates]);pieces.append(v[keep]);dates_list.extend(dates[keep])
  reference=np.concatenate(pieces);del pieces;np.testing.assert_array_equal(np.array(dates_list),ref_dates);qtick=time.monotonic();q,n,ny=pixel_thresholds(reference,refcal,refyears,np.arange(365));qsec=time.monotonic()-qtick;pick=np.arange(min(8,len(indices)));target_sample=np.full((nd,len(pick)),np.nan)
  for month in months[48:]:
   dates,v=read(month,lat0,lat1,lon0,lon1,occupied);row=dates.astype(int)-target0;cal=targetcal[row];threshold=q[np.maximum(cal,0)].copy();threshold[cal<0]=(q[58]+q[59])/2
   valid=np.isfinite(v)&np.isfinite(threshold);total[row]+=np.asarray(tw.dot(((v>threshold)&valid).astype(float).T)).T;missing[row]+=np.asarray(tw.dot((~valid).astype(float).T)).T
   finite=np.isfinite(v);utc[row]+=np.asarray(tw.dot(np.where(finite,v,0.).T)).T;utc_missing[row]+=np.asarray(tw.dot((~finite).astype(float).T)).T;target_sample[row]=v[:,pick]
  sample=out/f'sample_{lat0:03d}_{lon0:04d}.npz';np.savez_compressed(sample,reference=reference[:,pick],reference_days=ref_dates.astype(int),reference_calendar=refcal,reference_years=refyears,target=target_sample,target_days=target_dates.astype(int),threshold=q[:,pick],reference_n=n[:,pick],reference_year_count=ny[:,pick],grid_indices=indices[pick]);del reference,q,n,ny
  subprocess.run([sys.executable,'outputs/2026-10-31_verify_pixel_sample.py',str(sample)],check=True)
  receipt=sample.with_suffix('.verify.json');sample_index.append(dict(sample=sample.name,sample_hash=Sources().verify(sample),verification=receipt.name,verification_hash=Sources().verify(receipt)));timings.append(dict(latitude_start=lat0,longitude_start=lon0,populated_cells=len(occupied),threshold_seconds=qsec,tile_seconds=time.monotonic()-tick))
  save('status.json',dict(status='running',phase='tiles',completed_tiles=len(timings),positive_cells_completed=sum(t['populated_cells'] for t in timings),elapsed_seconds=time.monotonic()-started));print(json.dumps(timings[-1]),flush=True)
positive=np.asarray(w.sum(axis=1)).ravel()>0;assert sum(t['populated_cells'] for t in timings)==len(np.unique(w.indices));fraction=total.copy();fraction[(missing>0)|(~positive[None,:])]=np.nan;utc[(utc_missing>0)|(~positive[None,:])]=np.nan;assert np.nanmin(fraction)>=-1e-10 and np.nanmax(fraction)<=1+1e-10
checks=0;maxerr=0
for month in months[48:]:
 p=Path('analysis/2026-10-06_era5_existing_data/country_daily')/('era5_country_daily_'+month+'.csv');sources.verify(p)
 lookup={r['country_id']:i for i,r in enumerate(meta)}
 for r in csv.DictReader(p.open()):
  di=int(np.datetime64(r['date']).astype(int))-target0;ci=lookup[r['country_id']];old=float(r['tmax_c']) if r['tmax_c'] else float('nan');value=utc[di,ci];assert np.isfinite(old)==np.isfinite(value)
  if np.isfinite(old):error=abs(old-value);assert error<1e-6;maxerr=max(maxerr,error)
  checks+=1
sources.check()
with (out/'country_daily.csv').open('w',newline='') as f:
 writer=csv.writer(f);writer.writerow(['country_id','date','pixel_exceedance_population_fraction','missing_population_fraction','utc_country_tmax_c'])
 for di,date in enumerate(target_dates):
  for ci,r in enumerate(meta):writer.writerow([r['country_id'],str(date),float(fraction[di,ci]) if np.isfinite(fraction[di,ci]) else '',float(missing[di,ci]) if positive[ci] else '',float(utc[di,ci]) if np.isfinite(utc[di,ci]) else ''])
save('samples_index.json',sample_index);summary=dict(status='completed',country_days=nd*nc,positive_population_countries=int(positive.sum()),positive_cells=sum(t['populated_cells'] for t in timings),valid_population_fraction_rows=int(np.isfinite(fraction).sum()),utc_original_table_checks=checks,utc_max_error=maxerr,tile_timings=timings,elapsed_seconds=time.monotonic()-started,scope='Local pixel Q90 2018-2021 with unchanged fixed weights and strict missingness, all 2022-2025 UTC days. Spatial weather diagnostic only; no new network events or causal effect.');save('summary.json',summary);save('manifest.json',dict(inputs=sources.entries,outputs={n:Sources().verify(out/n) for n in ('country_daily.csv','summary.json','samples_index.json')}));save('status.json',dict(status='completed',elapsed_seconds=time.monotonic()-started));print(json.dumps(summary),flush=True)
