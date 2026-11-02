"""Acquire fixed external-validation cohort without modifying its protocol."""
import bz2,concurrent.futures,datetime as dt,gzip,hashlib,json
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]/'downloads/reconstruction_pilot/independent_validation'
protocol=json.loads((ROOT/'protocol.json').read_text())
s=requests.Session();s.trust_env=False
url='https://ftp.ripe.net/ripe/atlas/probes/archive/2023/10/20231001.json.bz2'
p=ROOT/'probes_20231001.json.bz2'
if not p.exists():
 r=s.get(url,timeout=90);r.raise_for_status();json.loads(bz2.decompress(r.content));p.write_bytes(r.content)
objects=json.loads(bz2.decompress(p.read_bytes()))['objects']
ids=sorted(x['id'] for x in objects if x.get('asn_v4')==4804 and x.get('is_public') and x.get('status')==1)
(ROOT/'selection.json').write_text(json.dumps({'snapshot_url':url,'snapshot_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'protocol_sha256':hashlib.sha256((ROOT/'protocol.json').read_bytes()).hexdigest(),'probe_ids':ids},indent=2)+'\n')
print(json.dumps({'selected_probes':len(ids),'ids':ids}),flush=True)
if len(ids)<5:raise SystemExit('Predeclared minimum cohort unavailable; validation cannot proceed.')
a=int(dt.datetime(2023,10,1,tzinfo=dt.timezone.utc).timestamp());b=int(dt.datetime(2023,12,1,tzinfo=dt.timezone.utc).timestamp())
p=ROOT/'ioda_AS4804_2023_oct_nov.json'
if not p.exists():
 r=s.get('https://api.ioda.inetintel.cc.gatech.edu/v2/signals/raw/asn/4804',params={'from':a,'until':b,'datasource':'ping-slash24','maxPoints':1000000},timeout=180);r.raise_for_status();data=r.json();assert data.get('data');p.write_bytes(r.content)
def fetch(job):
 month,msm=job;start=int(dt.datetime(2023,month,1,tzinfo=dt.timezone.utc).timestamp());stop=int(dt.datetime(2023,month+1,1,tzinfo=dt.timezone.utc).timestamp())
 params={'start':start,'stop':stop,'probe_ids':','.join(map(str,ids)),'format':'json'};url=f'https://atlas.ripe.net/api/v2/measurements/{msm}/results/'
 p=ROOT/f'msm{msm}_2023_{month:02d}.json.gz'
 if p.exists():data=json.loads(gzip.decompress(p.read_bytes()))
 else:
  session=requests.Session();session.trust_env=False;r=session.get(url,params=params,timeout=240);r.raise_for_status();data=r.json();assert isinstance(data,list);p.write_bytes(gzip.compress(r.content,mtime=0))
 assert all(x['prb_id'] in ids and x['msm_id']==msm and start<=x['timestamp']<stop for x in data)
 assert len({(x['prb_id'],x['timestamp']) for x in data})==len(data)
 meta={'url':url,'params':params,'records':len(data),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
 p.with_suffix('.metadata.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps({'month':month,'measurement':msm,'records':len(data)}),flush=True)
 return meta
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(fetch,[(m,k) for m in (10,11) for k in (1001,1010)]))
(ROOT/'download_summary.json').write_text(json.dumps({'files':results,'records':sum(x['records'] for x in results)},indent=2)+'\n')
