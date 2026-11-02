"""Exact proposal country-clock monthly statistics, positive-population groups."""
from pathlib import Path
from contextlib import ExitStack
import argparse,csv,json,time
import numpy as np
from netCDF4 import Dataset
from .run_connection_baseline import Sources
from .aggregate_era5_country_daily import load_weight_bundle,validate_temperature_units
from .country_solar import circular_longitudes,fixed_offset_extrema
p=argparse.ArgumentParser();p.add_argument('--month',required=True);p.add_argument('--output',required=True);a=p.parse_args();started=time.monotonic();out=Path(a.output);assert not out.exists();out.mkdir(parents=True);src=Sources();save=lambda name,obj:(out/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n');save('status.json',dict(status='running'))
wd=Path('analysis/2026-10-06_era5_existing_data/weights');b=load_weight_bundle(wd/'weights.npz',wd/'country_metadata.csv',wd/'weights_metadata.json');w=b['weights'].tocsr();ncountry=w.shape[0]
for n in ('weights.npz','country_metadata.csv','weights_metadata.json'):src.verify(wd/n)
checked=Path('analysis/2026-10-31_country_solar/v1/pilot_mys');pilot=json.loads(src.read(checked/'summary.json'));assert pilot['scalar_hour_value_checks']>0 and pilot['countries_with_scalar_clock_check']==218;pm=json.loads(src.read(checked/'manifest.json'));src.verify(checked/'summary.json',pm['outputs']['summary.json'])
longitudes=(np.tile(b['grid']['longitude'],721)+180)%360-180;clon,resultant=circular_longitudes(w,longitudes);defined=np.isfinite(clon);offset=np.zeros(ncountry,dtype=int);offset[defined]=np.ceil(-clon[defined]/15).astype(int);groups=[(k,np.flatnonzero(defined&(offset==k))) for k in sorted(set(offset[defined].tolist()))]
clocks=[dict(country_id=str(country),mean_longitude=float(clon[i]) if defined[i] else None,circular_resultant=float(resultant[i]) if np.isfinite(resultant[i]) else None,first_utc_hour_offset=int(offset[i]) if defined[i] else None) for i,country in enumerate(b['country_ids'])];save('country_clocks.json',clocks)
start=np.datetime64(a.month[:4]+'-'+a.month[4:]+'-01');stop=(start.astype('datetime64[M]')+1).astype('datetime64[D]');days=np.arange(start,stop).astype(int);nd=len(days);times=np.arange((days[0]-1)*86400,(days[-1]+2)*86400,3600,dtype=np.int64);months=sorted({str(np.datetime64(int(d),'D'))[:7].replace('-','') for d in (days[0]-1,days[0],days[-1]+1)})
master=json.loads(src.read(Path('analysis/2026-10-31_pixel_exceedance/v1/full_outputs/manifest.json')));total={k:np.zeros((nd,ncountry)) for k in ('tmin_c','tmax_c','dewpoint_c')};bad={k:np.zeros((nd,ncountry)) for k in total};utc={k:np.zeros((nd,ncountry)) for k in total};utc_bad={k:np.zeros((nd,ncountry)) for k in total};count=0;read_seconds=reduce_seconds=0.;sampled=set()
with ExitStack() as stack:
 opened=[]
 for month in months:
  if not '201801'<=month<='202512':continue
  path=Path('/volume1/homes/Judy/GSC2027/era5')/('era5_2m_'+month+'.nc');src.verify(path,master['inputs'][str(path)]);f=stack.enter_context(Dataset(path));tt=np.asarray(f.variables['valid_time'][:],dtype=np.int64)
  assert f.variables['valid_time'].units=='seconds since 1970-01-01' and np.all(np.diff(tt)==3600) and np.all(tt%3600==0)
  for coordinate in ('latitude','longitude'):np.testing.assert_array_equal(f.variables[coordinate][:],b['grid'][coordinate])
  ix=np.flatnonzero((tt>=times[0])&(tt<=times[-1]));opened.append((f,tt,ix))
 for lat0 in range(0,721,121):
  for lon0 in range(0,1440,240):
   lat1=min(721,lat0+121);lon1=min(1440,lon0+240);indices=(np.arange(lat0,lat1)[:,None]*1440+np.arange(lon0,lon1)[None,:]).ravel();tileweights=w[:,indices]
   if not tileweights.nnz:continue
   for var,fields in (('t2m',('tmin_c','tmax_c')),('d2m',('dewpoint_c',))):
    tick=time.monotonic();raw=np.full((len(times),len(indices)),np.nan,dtype=np.float32)
    for f,tt,ix in opened:
     if len(ix)==0:continue
     validate_temperature_units(f.variables[var].units);v=np.asarray(np.ma.filled(f.variables[var][ix[0]:ix[-1]+1,lat0:lat1,lon0:lon1],np.nan),dtype=np.float32).reshape(len(ix),-1);raw[(tt[ix]-times[0])//3600]=v
    read_seconds+=time.monotonic()-tick;tick=time.monotonic()
    for off,countries in groups:
     wg=tileweights[countries];occupied=np.flatnonzero(np.asarray(wg.sum(axis=0)).ravel()>0)
     if len(occupied)==0:continue
     wg=wg[:,occupied];v=raw[:,occupied];solar=fixed_offset_extrema(times,v,off,days);zero=solar if off==0 else fixed_offset_extrema(times,v,0,days)
     for field in fields:
      key='mean_c' if field=='dewpoint_c' else field
      for totals,missing,values in ((total,bad,solar[key]),(utc,utc_bad,zero[key])):
       finite=np.isfinite(values);totals[field][:,countries]+=np.asarray(wg.dot(np.where(finite,values,0.).T)).T;missing[field][:,countries]+=np.asarray(wg.dot((~finite).astype(float).T)).T
     if var not in sampled:
      representative=int(countries[np.flatnonzero(np.asarray(wg.sum(axis=1)).ravel()>0)[0]]);pick=np.arange(min(8,len(occupied)));np.savez_compressed(out/('first_tile_'+var+'.npz'),times=times,values=v[:,pick],longitude=np.full(len(pick),clon[representative]),days=days,representative_country=np.array(str(b['country_ids'][representative])),**{k:solar[k][:,pick] for k in solar});sampled.add(var)
    reduce_seconds+=time.monotonic()-tick
   count+=1;save('status.json',dict(status='running',tiles=count,elapsed_seconds=time.monotonic()-started))
rows=[]
for di,day in enumerate(days):
 for ci,country in enumerate(b['country_ids']):
  r=dict(country_id=str(country),date=str(np.datetime64(int(day),'D')),complete_month_grid=True)
  for field in total:
   r[field]=float(total[field][di,ci]) if defined[ci] and bad[field][di,ci]==0 else None;r['utc_'+field]=float(utc[field][di,ci]) if defined[ci] and utc_bad[field][di,ci]==0 else None;r[field+'_missing_population_fraction']=float(bad[field][di,ci]) if defined[ci] else None
  rows.append(r)
with (out/'country_daily.csv').open('w',newline='') as f:writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
for path in (Path(__file__),Path(__file__).with_name('country_solar.py'),Path(__file__).with_name('aggregate_era5_country_daily.py'),Path('docs/superpowers/specs/2026-10-31-country-solar-correction.md')):src.verify(path)
src.check();save('summary.json',dict(month=a.month,complete_month_grid=True,tiles=count,rows=len(rows),defined_country_clocks=int(defined.sum()),read_seconds=read_seconds,reduce_seconds=reduce_seconds,elapsed_seconds=time.monotonic()-started,scope='Exact proposal country fixed-population circular-mean longitude day. All pixels in a country share that clock. Missing external archive edge hours stay missing. Full weather catalogue/network effects not established by aggregation.'));save('manifest.json',dict(inputs=src.entries,outputs={name:Sources().verify(out/name) for name in ('country_daily.csv','country_clocks.json','first_tile_t2m.npz','first_tile_d2m.npz','summary.json')}));save('status.json',dict(status='completed'));print((out/'summary.json').read_text())
