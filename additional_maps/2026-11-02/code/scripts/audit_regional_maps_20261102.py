"""Independent scalar quantiles/counts, archived-bound and retained raw probes."""
import argparse,csv,datetime as dt,json,math,time,hashlib
from pathlib import Path
import numpy as np
from netCDF4 import Dataset

def run(a):
 start=time.monotonic();out=Path(a.output);m=json.loads((out/'manifest.json').read_text())
 for f,e in m['outputs'].items():assert hashlib.sha256((out/f).read_bytes()).hexdigest()==e['sha256']
 rows={(r['country_id'],int(r['grid_index'])):r for r in csv.DictReader((out/'pixels.csv').open())};summary=json.loads((out/'summary.json').read_text());quantiles=counts=raw_probes=bound_checks=0
 for name in summary['samples']:
  x=np.load(out/name,allow_pickle=False);cid=name.split('_')[1];ref=x['reference'];calendar=x['reference_calendar'];years=x['reference_years'];dates=x['target_dates'].astype('datetime64[D]');nnh=int((~x['national_hot']).sum())
  for j,grid in enumerate(x['grid_indices']):
   for day in range(365):
    dist=np.minimum((calendar-day)%365,(day-calendar)%365);z=ref[dist<=15,j];yy=years[dist<=15];valid=np.isfinite(z);z=np.sort(z[valid]);ny=len(set(yy[valid].tolist()));assert len(z)==x['reference_n'][day,j] and ny==x['reference_year_count'][day,j]
    if len(z)>=112 and ny==4:
     k=.9*(len(z)-1);lo=math.floor(k);hi=math.ceil(k);expected=float(z[lo]+(z[hi]-z[lo])*(k-lo));assert abs(expected-x['threshold'][day,j])<1e-10
    else:assert np.isnan(x['threshold'][day,j])
    quantiles+=1
   vv=x['target'][:,j].tolist();qq=[]
   for d in dates:
    s=str(d)
    if s[5:]=='02-29':qq.append(float((x['threshold'][58,j]+x['threshold'][59,j])/2))
    else:qq.append(float(x['threshold'][(dt.date(2001,int(s[5:7]),int(s[8:10]))-dt.date(2001,1,1)).days,j]))
   np.testing.assert_allclose(qq,x['target_threshold'][:,j],rtol=0,atol=1e-12);r=rows[cid,int(grid)];assert all(math.isfinite(v) for v in vv+qq)
   expected={'absolute35_days_per_year':sum(v>35 for v in vv)/4,'local_q90_days_per_year':sum(v>q for v,q in zip(vv,qq))/4,'local_hot_on_national_nonhot_percent':100*sum(v>q for v,q,h in zip(vv,qq,x['national_hot']) if not h)/nnh}
   for year in range(2022,2026):
    ix=[i for i,d in enumerate(dates) if str(d).startswith(str(year))];expected[f'local_q90_percent_{year}']=100*sum(vv[i]>qq[i] for i in ix)/len(ix)
   for label,months in [('DJF',(12,1,2)),('MAM',(3,4,5)),('JJA',(6,7,8)),('SON',(9,10,11))]:
    ix=[i for i,d in enumerate(dates) if int(str(d)[5:7]) in months];expected['local_q90_percent_'+label]=100*sum(vv[i]>qq[i] for i in ix)/len(ix)
   for k,value in expected.items():assert abs(float(r[k])-value)<1e-10;counts+=1
  # One fixed sampled cell, three predeclared source dates per tile.
  row,col=divmod(int(x['grid_indices'][0]),1440)
  for date in ('2022-01-01','2023-07-15','2024-02-29'):
   month=date[:4]+date[5:7];idx=(int(date[8:10])-1)*24
   with Dataset('/volume1/homes/Judy/GSC2027/era5/era5_2m_'+month+'.nc') as f:
    values=np.asarray(np.ma.filled(f['t2m'][idx:idx+24,row,col],np.nan),np.float32);assert len(values)==24;value=float(max(values))-273.15 if np.isfinite(values).all() else np.nan
   k=list(map(str,dates)).index(date);assert abs(value-x['target'][k,0])<1e-10;raw_probes+=1
 original=Path('analysis/2026-10-31_pixel_exceedance/v1/comparison/country_day_spatial_comparison.csv');lookup={(r['country_id'],r['date']):r for r in csv.DictReader(original.open()) if r['country_id'] in {s['country_id'] for s in summary['countries']}}
 for r in csv.DictReader((out/'country_daily_subset.csv').open()):
  source=lookup[r['country_id'],r['date']];assert source['country_daily_exceedance']==r['national_hot'];assert abs(float(source['pixel_exceedance_population_fraction'])-float(r['original_pixel_fraction']))<1e-12;diff=float(r['original_pixel_fraction'])-float(r['roi_hot_country_weight']);assert -1e-9<=diff<=1-float(r['roi_country_weight'])+1e-9;bound_checks+=1
 rec=dict(status='verified',scalar_quantile_checks=quantiles,independent_summary_counts=counts,original_hourly_source_probes=raw_probes,original_country_day_membership_and_bounds=bound_checks,elapsed_seconds=time.monotonic()-start,manifest_sha256=hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest(),scope='Sampled scalar/raw-source audit and every national-day bound. Descriptive weather maps only, not independent-cell inference or subnational network effects. Full raw files not newly rehashed.')
 p=out.parent/(out.name+'.verify.json');assert not p.exists();p.write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps(rec))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args())
