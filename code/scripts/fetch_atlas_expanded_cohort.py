"""Pre-training snapshot cohort; two destinations, all eligible AS812 probes."""
import bz2,concurrent.futures,datetime as dt,gzip,hashlib,json
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]/'downloads/reconstruction_pilot/expanded_cohort'
ROOT.mkdir(exist_ok=True)
s=requests.Session();s.trust_env=False
url='https://ftp.ripe.net/ripe/atlas/probes/archive/2022/05/20220501.json.bz2'
p=ROOT/'probes_20220501.json.bz2'
if not p.exists():
 r=s.get(url,timeout=90);r.raise_for_status();json.loads(bz2.decompress(r.content));p.write_bytes(r.content)
objects=json.loads(bz2.decompress(p.read_bytes()))['objects']
ids=sorted(x['id'] for x in objects if x.get('asn_v4')==812 and x.get('is_public') and x.get('status')==1)
assert ids and len(ids)<100
(ROOT/'selection.json').write_text(json.dumps({'source':url,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'probe_ids':ids,'rule':'All public connected AS812 probes on May 1 2022, before fitting period; no selection using July outcomes.','measurements':[1001,1010],'months':[5,6,7],'july_is_development':True},indent=2)+'\n')
print(json.dumps({'selected_probes':len(ids),'ids':ids}),flush=True)
def fetch(job):
 month,msm=job;start=int(dt.datetime(2022,month,1,tzinfo=dt.timezone.utc).timestamp());stop=int(dt.datetime(2022,month+1,1,tzinfo=dt.timezone.utc).timestamp())
 params={'start':start,'stop':stop,'probe_ids':','.join(map(str,ids)),'format':'json'}
 url=f'https://atlas.ripe.net/api/v2/measurements/{msm}/results/'
 p=ROOT/f'msm{msm}_2022_{month:02d}.json.gz'
 if p.exists():data=json.loads(gzip.decompress(p.read_bytes()))
 else:
  session=requests.Session();session.trust_env=False;r=session.get(url,params=params,timeout=240);r.raise_for_status();data=r.json()
  assert isinstance(data,list)
  p.write_bytes(gzip.compress(r.content,mtime=0))
 assert all(x['prb_id'] in ids and x['msm_id']==msm and start<=x['timestamp']<stop for x in data)
 assert len({(x['prb_id'],x['timestamp']) for x in data})==len(data)
 meta={'url':url,'params':params,'records':len(data),'probes_returned':sorted({x['prb_id'] for x in data}),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
 p.with_suffix('.metadata.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps({'month':month,'measurement':msm,'records':len(data),'returned':len(meta['probes_returned'])}),flush=True)
 return meta
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(fetch,[(month,msm) for month in (5,6,7) for msm in (1001,1010)]))
(ROOT/'download_summary.json').write_text(json.dumps({'files':results,'records':sum(x['records'] for x in results),'not_ioda':True},indent=2)+'\n')
