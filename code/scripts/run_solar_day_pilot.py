"""Real MYS four-day timing pilot; preserve raw subset for scalar verification."""
from pathlib import Path
import csv,json,time,hashlib
import numpy as np
from scipy.sparse import load_npz
from netCDF4 import Dataset
from .solar_day import extrema
from .run_connection_baseline import Sources
start=time.monotonic();root=Path.cwd();out=root/'analysis/2026-10-30_solar_day/v1/pilot_mys';assert not out.exists()
weights=root/'analysis/2026-10-06_era5_existing_data/weights';metadata=list(csv.DictReader((weights/'country_metadata.csv').open()));ci=next(i for i,r in enumerate(metadata) if r['country_id']=='MYS')
matrix=load_npz(weights/'weights.npz').tocsr();w=matrix.getrow(ci);rr=w.indices//1440;cc=w.indices%1440;mass=w.data
assert (mass>0).all() and np.isclose(mass.sum(),1.)
source=Path('/volume1/homes/Judy/GSC2027/era5/era5_2m_202401.nc');inputs=Sources()
for p in (source,weights/'weights.npz',weights/'country_metadata.csv',Path(__file__),Path(__file__).with_name('solar_day.py')):inputs.verify(p)
with Dataset(source) as nc:
 assert nc.variables['valid_time'].units=='seconds since 1970-01-01'
 tt=np.asarray(nc.variables['valid_time'][:],dtype=np.int64);days=np.array([19732,19733,19734,19735])
 # Derive day numbers from explicit ISO dates rather than relying on literals.
 days=np.array([np.datetime64('2024-01-'+str(d)).astype('datetime64[D]').astype(int) for d in range(10,14)])
 take=(tt>=(days[0]-1)*86400)&(tt<(days[-1]+2)*86400);idx=np.flatnonzero(take);lon=np.asarray(nc.variables['longitude'][:])[cc];lon=(lon+180)%360-180
 bounds=(slice(idx[0],idx[-1]+1),slice(rr.min(),rr.max()+1),slice(cc.min(),cc.max()+1))
 data={}
 for name in ('t2m','d2m'):
  assert str(nc.variables[name].units)=='K';tile=np.asarray(np.ma.filled(nc.variables[name][bounds],np.nan));data[name]=tile[:,rr-rr.min(),cc-cc.min()]
selected=tt[take];results={}
for name,v in data.items():
 solar=extrema(selected,v,lon,days);utc=extrema(selected,v,np.zeros(len(lon)),days)
 for field in (('tmin_c','tmax_c') if name=='t2m' else ('mean_c',)):
  results[name+'_'+field]=dict(solar=(solar[field]@mass).tolist(),utc=(utc[field]@mass).tolist(),difference=((solar[field]-utc[field])@mass).tolist())
inputs.check();out.mkdir(parents=True);np.savez_compressed(out/'raw_subset.npz',times=selected,longitude=lon,weights=mass,days=days,**data)
report=dict(country='MYS',days=['2024-01-'+str(d) for d in range(10,14)],positive_cells=len(mass),results=results,elapsed_seconds=time.monotonic()-start,scope='Four-day pilot only; mean solar-day hourly bins, strict fixed population weights. No full study sensitivity or effect claim.')
(out/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');(out/'manifest.json').write_text(json.dumps(dict(inputs=inputs.entries,outputs={n:Sources().verify(out/n) for n in ('raw_subset.npz','summary.json')}),indent=2)+'\n');print(json.dumps(report,indent=2))
