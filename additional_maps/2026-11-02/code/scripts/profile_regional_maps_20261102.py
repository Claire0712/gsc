"""Descriptive profiles; all preselected geographic cuts retained, no p-values."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
BOX={'USA':(-125,-66,24,50),'CHN':(74,135,18,54),'AUS':(112,154,-44,-10)}
FIELDS=['absolute35_days_per_year','local_q90_days_per_year','local_hot_on_national_nonhot_percent']
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--data',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();assert not a.output.exists();d=pd.read_csv(a.data);result={};cuts=[]
 def weighted(f,key):
  assert len(f)>0 and f[key].notna().all();return float(np.average(f[key],weights=f.country_population_weight))
 for cid,b in BOX.items():
  f=d.loc[d.country_id==cid];west,east,south,north=b;cx=(west+east)/2;cy=(south+north)/2
  result[cid]={'cells':len(f),'represented_country_weight':float(f.country_population_weight.sum()),'national_nonhot_days':int(f.national_nonhot_days.iloc[0]),'metrics':{key:{'weighted_mean':weighted(f,key),'equal_cell_mean':float(f[key].mean()),'cell_min':float(f[key].min()),'cell_median':float(f[key].median()),'cell_max':float(f[key].max())} for key in FIELDS},'annual_relative_percentage':{str(y):weighted(f,f'local_q90_percent_{y}') for y in range(2022,2026)}}
  for dx in (-5,0,5):
   for dy in (-2.5,0,2.5):
    lon,lat=cx+dx,cy+dy;groups={'SW':f.loc[(f.longitude<lon)&(f.latitude<lat)],'NE':f.loc[(f.longitude>=lon)&(f.latitude>=lat)],'south':f.loc[f.latitude<lat],'north':f.loc[f.latitude>=lat]}
    for key in FIELDS:
     means={name:weighted(z,key) for name,z in groups.items()};cuts.append(dict(country_id=cid,longitude_split=lon,latitude_split=lat,metric=key,**{k+'_mean':v for k,v in means.items()},SW_minus_NE=means['SW']-means['NE'],south_minus_north=means['south']-means['north'],**{k+'_cells':len(v) for k,v in groups.items()}))
  result[cid]['cut_sensitivity']={key:{contrast:{'min':float(min(x[contrast] for x in cuts if x['country_id']==cid and x['metric']==key)),'max':float(max(x[contrast] for x in cuts if x['country_id']==cid and x['metric']==key))} for contrast in ('SW_minus_NE','south_minus_north')} for key in FIELDS}
 result['interpretation']='Cell weather metrics on original fixed-country population support. Weighted means normalize only within the represented region. Conditional local Q90 includes every national non-exceedance day, all seasons; not an absolute hazardous-heat rate. Spatial cuts and neighbouring alternatives are descriptive, correlated cells are not independent samples, no causal or state-network inference.'
 a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');pd.DataFrame(cuts).to_csv(a.output.with_suffix('.cuts.csv'),index=False);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
