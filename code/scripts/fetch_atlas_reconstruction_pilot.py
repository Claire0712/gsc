"""Fetch fixed pre-event probe cohort; historical results only, no new measurements."""
import concurrent.futures,datetime as dt,gzip,hashlib,json,pathlib,requests
root=pathlib.Path(__file__).resolve().parents[1]/'downloads/reconstruction_pilot'
selection=json.loads((root/'atlas_pilot_request.json').read_text())
ids=selection['probe_ids']
def fetch(month):
 a=int(dt.datetime(2022,month,1,tzinfo=dt.timezone.utc).timestamp());b=int(dt.datetime(2022,month+1,1,tzinfo=dt.timezone.utc).timestamp())
 params={'start':a,'stop':b,'probe_ids':','.join(map(str,ids)),'format':'json'}
 url='https://atlas.ripe.net/api/v2/measurements/1010/results/'
 p=root/'raw'/f'atlas_1010_2022_{month:02d}.json.gz'
 if p.exists():data=json.loads(gzip.decompress(p.read_bytes()))
 else:
  s=requests.Session();s.trust_env=False;r=s.get(url,params=params,timeout=180);r.raise_for_status();data=r.json()
  assert isinstance(data,list)
  payload=gzip.compress(r.content,mtime=0);p.write_bytes(payload)
 assert all(x['prb_id'] in ids and x['msm_id']==1010 and a<=x['timestamp']<b for x in data)
 meta={'url':url,'params':params,'records':len(data),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'probes_returned':sorted(set(x['prb_id'] for x in data))}
 p.with_suffix('.metadata.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps({'month':month,**meta}),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(fetch,[5,6,7]))
