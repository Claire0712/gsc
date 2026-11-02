"""Exact country-clock correction on preselected unchanged MYS hourly cache."""
from pathlib import Path
import json,csv,time,math
import numpy as np
from .run_connection_baseline import Sources
from .aggregate_era5_country_daily import load_weight_bundle
from .country_solar import circular_longitudes,fixed_offset_extrema
started=time.monotonic();src=Sources();out=Path('analysis/2026-10-31_country_solar/v1/pilot_mys');assert not out.exists();wd=Path('analysis/2026-10-06_era5_existing_data/weights')
for name in ('weights.npz','country_metadata.csv','weights_metadata.json'):src.verify(wd/name)
b=load_weight_bundle(wd/'weights.npz',wd/'country_metadata.csv',wd/'weights_metadata.json');lon=(np.tile(b['grid']['longitude'],721)+180)%360-180;clon,res=circular_longitudes(b['weights'],lon);meta=list(csv.DictReader((wd/'country_metadata.csv').open()));ci=next(i for i,r in enumerate(meta) if r['country_id']=='MYS');clock=float(clon[ci]);offset=int(np.ceil(-clock/15))
# Independent scalar weighted sine/cosine circular means for all countries.
for j in range(len(meta)):
 w=b['weights'].getrow(j);x=math.fsum(float(m)*math.cos(math.radians(float(lon[i]))) for i,m in zip(w.indices,w.data));y=math.fsum(float(m)*math.sin(math.radians(float(lon[i]))) for i,m in zip(w.indices,w.data))
 if not len(w.data):assert np.isnan(clon[j]);continue
 expected=(math.degrees(math.atan2(y,x))+180)%360-180;assert abs(((expected-clon[j])+180)%360-180)<1e-10
old=Path('analysis/2026-10-30_solar_day/v1/pilot_mys');manifest=json.loads(src.read(old/'manifest.json'));src.verify(old/'raw_subset.npz',manifest['outputs']['raw_subset.npz']);z=np.load(old/'raw_subset.npz');results={};checks=0
for var in ('t2m','d2m'):
 v=z[var];values=fixed_offset_extrema(z['times'],v,offset,z['days']);utc=fixed_offset_extrema(z['times'],v,0,z['days']);fields=('tmin_c','tmax_c') if var=='t2m' else ('mean_c',)
 for field in fields:
  for d,day in enumerate(z['days']):
   ix=[i for i,t in enumerate(z['times']) if math.floor((float(t)+clock*240)/86400)==int(day)];assert len(ix)==24
   for j in range(v.shape[1]):
    hourly=[float(v[i,j]) for i in ix];expected=(min(hourly) if field=='tmin_c' else max(hourly) if field=='tmax_c' else math.fsum(hourly)/24)-273.15;assert abs(expected-values[field][d,j])<1e-10;checks+=1
  results[var+'_'+field]=dict(country_solar=(values[field]@z['weights']).tolist(),utc=(utc[field]@z['weights']).tolist())
for p in (Path(__file__),Path(__file__).with_name('country_solar.py'),Path('docs/superpowers/specs/2026-10-31-country-solar-correction.md')):src.verify(p)
src.check();out.mkdir(parents=True);summary=dict(country='MYS',country_circular_mean_longitude=clock,circular_resultant=float(res[ci]),first_utc_hour_offset=offset,countries_with_scalar_clock_check=len(meta),scalar_hour_value_checks=checks,results=results,elapsed_seconds=time.monotonic()-started,scope='Exact proposal country-offset clock pilot, not full weather catalogue or network effect; original pixel-clock diagnostic is preserved separately.');(out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n');(out/'manifest.json').write_text(json.dumps(dict(inputs=src.entries,outputs={'summary.json':Sources().verify(out/'summary.json')}),indent=2)+'\n');print(json.dumps(summary))
