"""Chunk-aligned solar-day aggregation, neighboring source hours retained."""
import argparse,calendar,csv,json,time
from pathlib import Path
from contextlib import ExitStack
import numpy as np
from netCDF4 import Dataset
from .solar_tile import reduce_tile
from .aggregate_era5_country_daily import load_weight_bundle,validate_temperature_units
from .run_connection_baseline import Sources
def run(a):
 started=time.monotonic();out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
 save=lambda n,v:(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
 save('status.json',dict(status='running'));sources=Sources();wd=Path('analysis/2026-10-06_era5_existing_data/weights')
 bundle=load_weight_bundle(wd/'weights.npz',wd/'country_metadata.csv',wd/'weights_metadata.json');w=bundle['weights'];grid=bundle['grid'];ncountry=w.shape[0]
 for name in ('weights.npz','country_metadata.csv','weights_metadata.json'):sources.verify(wd/name)
 begin=int(np.datetime64(a.month[:4]+'-'+a.month[4:]+'-01').astype(int));nd=calendar.monthrange(int(a.month[:4]),int(a.month[4:]))[1];days=np.arange(begin,begin+nd);times=np.arange((begin-1)*86400,(begin+nd+1)*86400,3600,dtype=np.int64)
 monthset=sorted({str(np.datetime64(int(d),'D'))[:7].replace('-','') for d in (begin-1,begin,begin+nd)})
 total={k:np.zeros((nd,ncountry)) for k in ('tmin_c','tmax_c','dewpoint_c')};missing={k:np.zeros((nd,ncountry)) for k in total};utc={k:np.zeros((nd,ncountry)) for k in total};utc_missing={k:np.zeros((nd,ncountry)) for k in total};count=0;read_seconds=0.;reduce_seconds=0.
 with ExitStack() as stack:
  opened=[]
  for month in monthset:
   path=Path('/volume1/homes/Judy/GSC2027/era5')/('era5_2m_'+month+'.nc')
   if not path.exists():continue
   sources.verify(path);nc=stack.enter_context(Dataset(path));tt=np.asarray(nc.variables['valid_time'][:],dtype=np.int64);assert nc.variables['valid_time'].units=='seconds since 1970-01-01' and np.all(np.diff(tt)==3600)
   for coordinate in ('latitude','longitude'):np.testing.assert_array_equal(nc.variables[coordinate][:],grid[coordinate])
   ix=np.flatnonzero((tt>=times[0])&(tt<=times[-1]));opened.append((nc,tt,ix))
  for lat0 in range(0,721,121):
   for lon0 in range(0,1440,240):
    lat1=min(721,lat0+121);lon1=min(1440,lon0+240);indices=(np.arange(lat0,lat1)[:,None]*1440+np.arange(lon0,lon1)[None,:]).ravel();weights=w[:,indices]
    if not weights.nnz:continue
    if a.limit_tiles and count>=a.limit_tiles:continue
    longitude=np.tile(np.asarray(grid['longitude'])[lon0:lon1],lat1-lat0);longitude=(longitude+180)%360-180
    for variable,fields in [('t2m',('tmin_c','tmax_c')),('d2m',('dewpoint_c',))]:
     v=np.full((len(times),len(indices)),np.nan,dtype=np.float32);read_start=time.monotonic()
     for nc,tt,ix in opened:
      if not len(ix):continue
      validate_temperature_units(nc.variables[variable].units);tile=np.asarray(np.ma.filled(nc.variables[variable][ix[0]:ix[-1]+1,lat0:lat1,lon0:lon1],np.nan),dtype=np.float32).reshape(len(ix),-1);positions=(tt[ix]-times[0])//3600;v[positions]=tile
     read_seconds+=time.monotonic()-read_start;tick=time.monotonic();solar=reduce_tile(times,v,longitude,days);zero=reduce_tile(times,v,np.zeros(len(indices)),days);reduce_seconds+=time.monotonic()-tick
     for field in fields:
      key='mean_c' if field=='dewpoint_c' else field
      for accumulator,bad,values in ((total,missing,solar[key]),(utc,utc_missing,zero[key])):
       valid=np.isfinite(values);accumulator[field]+=np.asarray(weights.dot(np.where(valid,values,0.).T)).T;bad[field]+=np.asarray(weights.dot((~valid).astype(float).T)).T
     if count==0:
      pick=np.flatnonzero(np.asarray(weights.sum(axis=0)).ravel()>0)[:8]
      np.savez_compressed(out/('first_tile_'+variable+'.npz'),times=times,values=v[:,pick],longitude=longitude[pick],days=days,**{k:solar[k][:,pick] for k in solar})
    count+=1;save('status.json',dict(status='running',tiles=count,elapsed_seconds=time.monotonic()-started))
 full=not a.limit_tiles;rows=[];pop=np.asarray(bundle['population'])
 for di,day in enumerate(days):
  for ci,country in enumerate(bundle['country_ids']):
   r=dict(country_id=country,date=str(np.datetime64(int(day),'D')),complete_month_grid=full)
   for field in total:
    r[field]=None if missing[field][di,ci]>0 or pop[ci]==0 else float(total[field][di,ci]);r['utc_'+field]=None if utc_missing[field][di,ci]>0 or pop[ci]==0 else float(utc[field][di,ci]);r[field+'_missing_population_fraction']=float(missing[field][di,ci])
   rows.append(r)
 with (out/'country_daily.csv').open('w',newline='') as f:writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
 for n in ('solar_tile.py','run_solar_month.py','aggregate_era5_country_daily.py'):sources.verify(Path(__file__).with_name(n))
 sources.check();save('summary.json',dict(month=a.month,complete_month_grid=full,tiles=count,rows=len(rows),read_seconds=read_seconds,reduce_seconds=reduce_seconds,elapsed_seconds=time.monotonic()-started,scope='Partial tile run is timing/verification only, not country mean or complete month. Full run requires independent UTC/source-cell audit; no solar events/effects inferred here. Missing edge hours remain NaN, never wrapped or imputed.'))
 save('manifest.json',dict(inputs=sources.entries,outputs={p.name:Sources().verify(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'}));save('status.json',dict(status='completed'));print((out/'summary.json').read_text())
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--month',required=True);p.add_argument('--output',required=True);p.add_argument('--limit-tiles',type=int,default=0);run(p.parse_args())
