"""Sensitivity only: weighted 0.5/1-degree aggregation; figures stay native."""
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from scripts.profile_regional_maps_20261102 import BOX,FIELDS

def coarsen(f,step):
 assert step in (.5,1.) and (f.country_population_weight>0).all();x=f[['country_id','latitude','longitude','country_population_weight']+FIELDS].copy();x['lat_bin']=np.floor((x.latitude+90)/step).astype(int);x['lon_bin']=np.floor((x.longitude+180)/step).astype(int)
 for k in FIELDS:x[k]*=x.country_population_weight
 g=x.groupby(['country_id','lat_bin','lon_bin'],as_index=False)[['country_population_weight']+FIELDS].sum()
 for k in FIELDS:g[k]/=g.country_population_weight
 g['latitude']=-90+(g.lat_bin+.5)*step;g['longitude']=-180+(g.lon_bin+.5)*step;return g

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--data',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();assert not a.output.exists();d=pd.read_csv(a.data);rows=[];conservation=[]
 for cid,b in BOX.items():
  native=d.loc[d.country_id==cid]
  for step in (.25,.5,1.):
   f=native if step==.25 else coarsen(native,step)
   for k in FIELDS:
    err=abs(np.average(native[k],weights=native.country_population_weight)-np.average(f[k],weights=f.country_population_weight));assert err<1e-10;conservation.append(float(err))
    for dx in (-5,0,5):
     for dy in (-2.5,0,2.5):
      lon=(b[0]+b[1])/2+dx;lat=(b[2]+b[3])/2+dy;sw=f.loc[(f.longitude<lon)&(f.latitude<lat)];ne=f.loc[(f.longitude>=lon)&(f.latitude>=lat)];south=f.loc[f.latitude<lat];north=f.loc[f.latitude>=lat]
      mean=lambda z:float(np.average(z[k],weights=z.country_population_weight));rows.append(dict(country_id=cid,step_deg=step,metric=k,longitude_split=lon,latitude_split=lat,SW_minus_NE=mean(sw)-mean(ne),south_minus_north=mean(south)-mean(north)))
 summary={cid:{k:{contrast:{'min':min(r[contrast] for r in rows if r['country_id']==cid and r['metric']==k),'max':max(r[contrast] for r in rows if r['country_id']==cid and r['metric']==k)} for contrast in ('SW_minus_NE','south_minus_north')} for k in FIELDS} for cid in BOX};summary['method']='Native 0.25-degree cell centres, plus fixed global-edge 0.5/1-degree weighted bins; all nine neighbouring cuts. No interpolation, new physical temperature or independent-cell inference. Plot resolution stays native.';summary['weighted_mean_conservation_max_abs_error']=max(conservation);a.output.write_text(json.dumps(summary,indent=2)+'\n');pd.DataFrame(rows).to_csv(a.output.with_suffix('.csv'),index=False);print(json.dumps(summary['USA']['absolute35_days_per_year']))
if __name__=='__main__':main()
