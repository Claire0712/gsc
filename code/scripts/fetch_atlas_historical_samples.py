"""Read historical outcomes in missing IODA years, retain separate provenance."""
import bz2,concurrent.futures,datetime as dt,gzip,hashlib,json
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]/'downloads/reconstruction_pilot/historical_coverage'
OUT=ROOT/'result_samples';OUT.mkdir(exist_ok=True)
selected={}
for year in range(2018,2022):
 objects=json.loads(bz2.decompress((ROOT/f'probes_{year}0701.json.bz2').read_bytes()))['objects']
 cohort=[]
 for country in ['US','RU','CA','AU','BR','CN']:
  used=set()
  for x in sorted(objects,key=lambda x:x['id']):
   if x.get('country_code')==country and x.get('is_public') and x.get('status')==1 and x.get('asn_v4') and x['asn_v4'] not in used:
    cohort.append({'id':x['id'],'asn_v4':x['asn_v4'],'country':country});used.add(x['asn_v4'])
    if len(used)==3:break
 selected[year]=cohort
(OUT/'selection.json').write_text(json.dumps({'rule':'Per July 1 historical snapshot: first public connected IPv4 probe by ID in each of first three distinct ASNs by probe ID, for six ADM1-focus countries. Availability sample only, not country representation.','cohorts':selected},indent=2)+'\n')
def fetch(job):
 year,msm=job;ids=[x['id'] for x in selected[year]]
 start=int(dt.datetime(year,7,1,tzinfo=dt.timezone.utc).timestamp());stop=start+86400
 params={'start':start,'stop':stop,'probe_ids':','.join(map(str,ids)),'format':'json'}
 url=f'https://atlas.ripe.net/api/v2/measurements/{msm}/results/'
 p=OUT/f'{year}_0701_msm{msm}.json.gz'
 if p.exists():data=json.loads(gzip.decompress(p.read_bytes()))
 else:
  s=requests.Session();s.trust_env=False;r=s.get(url,params=params,timeout=180);r.raise_for_status();data=r.json()
  assert isinstance(data,list)
  p.write_bytes(gzip.compress(r.content,mtime=0))
 assert all(x['prb_id'] in ids and x['msm_id']==msm and start<=x['timestamp']<stop for x in data)
 assert len({(x['prb_id'],x['timestamp']) for x in data})==len(data)
 meta={'year':year,'measurement':msm,'url':url,'params':params,'records':len(data),'selected_probes':len(ids),'returned_probes':sorted({x['prb_id'] for x in data}),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size,'not_ioda':True}
 p.with_suffix('.metadata.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta),flush=True)
 return meta
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(fetch,[(y,m) for y in range(2018,2022) for m in (1001,1010)]))
(OUT/'summary.json').write_text(json.dumps({'files':results,'records':sum(x['records'] for x in results),'complete_ioda_2018_2021':False},indent=2)+'\n')
