"""Bounded existing-ERA5 regional pixel maps; no new observations or network fit."""
import argparse,calendar,csv,datetime as dt,hashlib,json,time
from pathlib import Path
import numpy as np
from netCDF4 import Dataset
from .aggregate_era5_country_daily import load_weight_bundle,validate_temperature_units
from .pixel_exceedance_v2 import pixel_thresholds
from .regional_pixel_maps import summarize_days,json_scalar
from .run_connection_baseline import Sources
REGIONS={'USA':(-125,-66,24,50),'CHN':(74,135,18,54),'AUS':(112,154,-44,-10)}
ROOT_ERA=Path('/volume1/homes/Judy/GSC2027/era5')
def run(a):
 start=time.monotonic();out=Path(a.output)
 if out.exists():raise FileExistsError(out)
 out.mkdir(parents=True);save=lambda n,v:(out/n).write_text(json.dumps(v,indent=2,allow_nan=False,default=json_scalar)+'\n');save('status.json',dict(status='running',phase='metadata'))
 src=Sources();wd=Path('analysis/2026-10-06_era5_existing_data/weights');oldroot=Path('analysis/2026-10-31_pixel_exceedance/v1');oldm=json.loads(src.read(oldroot/'full_outputs/manifest.json'));cm=json.loads(src.read(oldroot/'comparison/manifest.json'));cf=oldroot/'comparison/country_day_spatial_comparison.csv';src.verify(cf,cm['outputs'][cf.name]);src.verify(Path(__file__));src.verify(Path(__file__).with_name('regional_pixel_maps.py'));src.verify(Path(__file__).with_name('pixel_exceedance_v2.py'));src.verify(Path('docs/superpowers/specs/2026-11-02-regional-map-expansion.md'))
 for n in ('weights.npz','country_metadata.csv','weights_metadata.json'):src.verify(wd/n,oldm['inputs'][str(wd/n)])
 b=load_weight_bundle(wd/'weights.npz',wd/'country_metadata.csv',wd/'weights_metadata.json');meta=list(csv.DictReader((wd/'country_metadata.csv').open()));lat=np.asarray(b['grid']['latitude']);lon=np.asarray(b['grid']['longitude']);assert len(lat)==721 and len(lon)==1440
 targetdates=np.arange(np.datetime64('2022-01-01'),np.datetime64('2026-01-01'));refdates=np.arange(np.datetime64('2018-01-01'),np.datetime64('2022-01-01'));refdates=refdates[np.array([str(d)[5:]!='02-29' for d in refdates])]
 cd=lambda d:-1 if str(d)[5:]=='02-29' else (dt.date(2001,int(str(d)[5:7]),int(str(d)[8:10]))-dt.date(2001,1,1)).days
 cal=np.array([cd(d) for d in refdates]);years=np.array([int(str(d)[:4]) for d in refdates]);targetcal=np.array([cd(d) for d in targetdates]);months=[f'{y}{m:02d}' for y in range(2018,2026) for m in range(1,13)];snapshots={};old_hashes={}
 for month in months:
  p=ROOT_ERA/f'era5_2m_{month}.nc';stamp=Sources.stamp(p);entry=oldm['inputs'][str(p)];assert stamp[2]==entry['bytes'] and stamp[3]<= (oldroot/'full_outputs/manifest.json').stat().st_mtime_ns,'Raw input changed since prior audit'
  snapshots[str(p)]=stamp;old_hashes[str(p)]=entry
 cids=['USA'] if a.pilot else list(REGIONS);contexts={c:[] for c in cids}
 with cf.open() as f:
  for r in csv.DictReader(f):
   if r['country_id'] in contexts:contexts[r['country_id']].append(r)
 outputs={};timings=[];sample_names=[];daily_hashes=[];records=[];country_summaries=[];daily_records=[]
 def read(month,lat0,lon0,grid_ids):
  p=ROOT_ERA/f'era5_2m_{month}.nc';begin=np.datetime64(month[:4]+'-'+month[4:]+'-01');end=(begin.astype('datetime64[M]')+1).astype('datetime64[D]');dates=np.arange(begin,end);la1=min(721,lat0+121);lo1=min(1440,lon0+240);pos=(grid_ids//1440-lat0)*(lo1-lon0)+(grid_ids%1440-lon0)
  with Dataset(p) as f:
   validate_temperature_units(f['t2m'].units);assert f['valid_time'].units=='seconds since 1970-01-01';np.testing.assert_array_equal(f['valid_time'][:],np.arange(int(begin.astype(int))*86400,int(end.astype(int))*86400,3600));np.testing.assert_array_equal(f['latitude'][:],lat);np.testing.assert_array_equal(f['longitude'][:],lon)
   raw=np.asarray(np.ma.filled(f['t2m'][:,lat0:la1,lon0:lo1],np.nan),dtype=np.float32).reshape(len(dates),24,-1);hourly=raw[:,:,pos];v=hourly.max(axis=1).astype(float)-273.15;v[~np.isfinite(hourly).all(axis=1)]=np.nan
  daily_hashes.append(dict(month=month,latitude_start=lat0,longitude_start=lon0,country=cid,decoded_selected_daily_sha256=hashlib.sha256(np.ascontiguousarray(v).tobytes()).hexdigest()));return dates,v
 for cid in cids:
  cc=sorted(contexts[cid],key=lambda r:r['date']);assert [r['date'] for r in cc]==[str(d) for d in targetdates];assert all(r['country_daily_exceedance'] in ('True','False') for r in cc);national_hot=np.array([r['country_daily_exceedance']=='True' for r in cc]);original=np.array([float(r['pixel_exceedance_population_fraction']) for r in cc]);assert np.isfinite(original).all()
  ci=next(i for i,r in enumerate(meta) if r['country_id']==cid);w=b['weights'].getrow(ci);lo=(lon[w.indices%1440]+180)%360-180;la=lat[w.indices//1440];west,east,south,north=REGIONS[cid];take=(lo>=west)&(lo<=east)&(la>=south)&(la<=north);ids=w.indices[take];mass=w.data[take];order=np.argsort(ids);ids=ids[order];mass=mass[order];tiles=sorted(set(zip((ids//1440)//121,(ids%1440)//240)));sum_hot=np.zeros(1461);selected_weight=0.;n_cells=0
  if a.pilot:tiles=tiles[:1]
  for tr,tc in tiles:
   tick=time.monotonic();keep=((ids//1440)//121==tr)&((ids%1440)//240==tc);ii=ids[keep];ww=mass[keep]
   if a.pilot:
    selection=np.linspace(0,len(ii)-1,min(64,len(ii))).astype(int);ii=ii[selection];ww=ww[selection]
   refs=[];seen=[]
   for month in months[:48]:
    dd,v=read(month,tr*121,tc*240,ii);k=np.array([str(d)[5:]!='02-29' for d in dd]);refs.append(v[k]);seen.extend(dd[k])
   reference=np.concatenate(refs);del refs;np.testing.assert_array_equal(np.array(seen),refdates);q,n,ny=pixel_thresholds(reference,cal,years,np.arange(365));target=[];seen=[]
   for month in months[48:]:dd,v=read(month,tr*121,tc*240,ii);target.append(v);seen.extend(dd)
   target=np.concatenate(target);np.testing.assert_array_equal(np.array(seen),targetdates);threshold=q[np.maximum(targetcal,0)].copy();threshold[targetcal<0]=(q[58]+q[59])/2;stats=summarize_days(target,threshold,targetdates,national_hot);assert np.isfinite(target).all() and np.isfinite(threshold).all(),'Retain missing; do not publish apparently complete regional map'
   sum_hot+=((target>threshold)*ww).sum(axis=1);selected_weight+=float(ww.sum());n_cells+=len(ii)
   pick=np.linspace(0,len(ii)-1,min(8,len(ii))).astype(int);name=f'sample_{cid}_{tr}_{tc}.npz';np.savez_compressed(out/name,reference=reference[:,pick],reference_dates=refdates.astype(int),reference_calendar=cal,reference_years=years,threshold=q[:,pick],reference_n=n[:,pick],reference_year_count=ny[:,pick],target=target[:,pick],target_dates=targetdates.astype(int),target_threshold=threshold[:,pick],national_hot=national_hot,grid_indices=ii[pick],weights=ww[pick]);sample_names.append(name)
   for j,index in enumerate(ii):
    row=dict(country_id=cid,grid_index=int(index),latitude=float(lat[index//1440]),longitude=float((lon[index%1440]+180)%360-180),country_population_weight=float(ww[j]),absolute35_days_per_year=float(stats['absolute_days_per_year'][j]),local_q90_days_per_year=float(stats['relative_days_per_year'][j]),local_hot_on_national_nonhot_percent=float(stats['local_hot_on_national_nonhot_fraction'][j]*100),valid_target_days=int(stats['relative_valid_days'][j]),national_nonhot_days=stats['national_nonhot_days'])
    for yi,year in enumerate(range(2022,2026)):row[f'local_q90_percent_{year}']=float(stats['annual_relative_percent'][yi,j])
    for si,season in enumerate(('DJF','MAM','JJA','SON')):row[f'local_q90_percent_{season}']=float(stats['season_relative_percent'][si,j])
    records.append(row)
   timings.append(dict(country=cid,tile=[int(tr),int(tc)],cells=len(ii),seconds=time.monotonic()-tick));save('status.json',dict(status='running',completed_tiles=len(timings),cells=n_cells,elapsed_seconds=time.monotonic()-start));print(json.dumps(timings[-1]),flush=True)
   del reference,q,target,threshold,n,ny
  daily_records.extend(dict(country_id=cid,date=str(date),national_hot=bool(national_hot[i]),original_pixel_fraction=float(original[i]),roi_hot_country_weight=float(sum_hot[i]),roi_country_weight=selected_weight) for i,date in enumerate(targetdates))
  diff=original-sum_hot;assert (diff>=-1e-9).all() and (diff<=1-selected_weight+1e-9).all();country_summaries.append(dict(country_id=cid,bbox=REGIONS[cid],positive_cells=n_cells,represented_country_population_weight=selected_weight,national_nonhot_days=int((~national_hot).sum()),original_country_fraction_bound_checks=1461,minimum_difference=float(diff.min()),maximum_difference=float(diff.max())))
 for p,stamp in snapshots.items():assert Sources.stamp(Path(p))==stamp,'Raw source changed during run'
 src.check()
 with (out/'pixels.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
 with (out/'country_daily_subset.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(daily_records[0]));w.writeheader();w.writerows(daily_records)
 save('country_summaries.json',country_summaries);save('decoded_source_hashes.json',daily_hashes);save('raw_source_provenance.json',dict(archived_full_hashes=old_hashes,before_after_fingerprints=snapshots,check='Original full SHA ledger reused; byte sizes/mtime predating prior audit and full fingerprints checked stable. Fresh decoded subset hashes recorded. Full raw files not freshly rehashed.'))
 summary=dict(status='completed',pilot=a.pilot,cells=len(records),tiles=len(timings),samples=sample_names,countries=country_summaries,tile_timings=timings,elapsed_seconds=time.monotonic()-start,scope='Discrete existing-source weather grid diagnostics, fixed population support. Not network-fault/state-effect evidence or a new climatological normal.');save('summary.json',summary)
 for file in out.iterdir():
  if file.name!='status.json':outputs[file.name]=Sources().verify(file)
 save('manifest.json',dict(inputs=src.entries,outputs=outputs,raw_full_rehash=False));save('status.json',dict(status='completed'));print(json.dumps(summary),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--pilot',action='store_true');run(p.parse_args())
