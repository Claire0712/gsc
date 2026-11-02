"""Fixed six-country coverage-selected ASN validation, no selection on outcomes."""
import bz2,concurrent.futures,datetime as dt,gzip,hashlib,json,collections,time
from pathlib import Path
import requests
BASE=Path(__file__).resolve().parents[1]/'downloads/reconstruction_pilot'
ROOT=BASE/'multinetwork_validation';ROOT.mkdir(exist_ok=True)
source=BASE/'independent_validation/probes_20231001.json.bz2'
objects=json.loads(bz2.decompress(source.read_bytes()))['objects']
eligible=[x for x in objects if x.get('is_public') and x.get('status')==1 and x.get('asn_v4')]
cohorts=[]
for country in ['US','RU','CA','AU','BR','CN']:
 counts=collections.Counter(x['asn_v4'] for x in eligible if x.get('country_code')==country and x['asn_v4']!=812)
 asn=sorted(counts,key=lambda k:(-counts[k],k))[0]
 candidates=[x['id'] for x in eligible if x['asn_v4']==asn]
 ids=sorted(sorted(candidates,key=lambda i:hashlib.sha256(f'HeatSignal-validation-v1:{i}'.encode()).hexdigest())[:30])
 assert len(ids)>=5
 cohorts.append({'country_for_selection':country,'asn':asn,'eligible_global_probes':len(candidates),'probe_ids':ids})
protocol={'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'cohort_rule':'For each of six proposal ADM1-focus countries choose the IPv4 ASN with most public connected probes in Oct 1 2023 snapshot, excluding development ASN812. For that ASN select up to 30 global probes by fixed SHA256 order. ASN series, not country estimates.','cohorts':cohorts,'baseline':['2023-10-01','2023-11-01'],'validation':['2023-11-01','2023-12-01'],'measurements':[1001,1010],'min_reports_per_8h':108,'minimum_cohort_fraction':.8,'min_ioda_reports_per_8h':44,'proxy':'Within-probe mean of both target packet-success proportions, then median across eligible probes, normalized by October median. Missing is not failure.','descriptive_gates':{'coverage_min':.8,'mae_max':.05,'drop_threshold':.8,'recall_min':.8,'false_positive_fraction_max':.05,'deficit_relative_error_max':.25},'interpretation':'No global backfill approval from this test. No event-response validation where no genuine drop bins are observed. Network selection favors well-observed ASNs and may include hosting networks.'}
p=ROOT/'protocol.json'
if not p.exists():p.write_text(json.dumps(protocol,indent=2)+'\n')
else:
 old=json.loads(p.read_text());assert old['cohorts']==cohorts
print(json.dumps({'cohorts':[{k:v for k,v in x.items() if k!='probe_ids'}|{'selected':len(x['probe_ids'])} for x in cohorts]}),flush=True)
def get(url,params):
 s=requests.Session();s.trust_env=False
 for attempt in range(3):
  try:
   r=s.get(url,params=params,timeout=240);r.raise_for_status();return r
  except requests.RequestException:
   if attempt==2:raise
   time.sleep(2*(attempt+1))
def fetch(job):
 cohort,kind,month,msm=job;asn=cohort['asn'];ids=cohort['probe_ids']
 folder=ROOT/f'AS{asn}';folder.mkdir(exist_ok=True)
 if kind=='ioda':
  a=int(dt.datetime(2023,10,1,tzinfo=dt.timezone.utc).timestamp());b=int(dt.datetime(2023,12,1,tzinfo=dt.timezone.utc).timestamp())
  url=f'https://api.ioda.inetintel.cc.gatech.edu/v2/signals/raw/asn/{asn}';params={'from':a,'until':b,'datasource':'ping-slash24','maxPoints':1000000};p=folder/'ioda_oct_nov.json.gz'
 else:
  a=int(dt.datetime(2023,month,1,tzinfo=dt.timezone.utc).timestamp());b=int(dt.datetime(2023,month+1,1,tzinfo=dt.timezone.utc).timestamp())
  url=f'https://atlas.ripe.net/api/v2/measurements/{msm}/results/';params={'start':a,'stop':b,'probe_ids':','.join(map(str,ids)),'format':'json'};p=folder/f'msm{msm}_2023_{month:02d}.json.gz'
 if p.exists():data=json.loads(gzip.decompress(p.read_bytes()))
 else:
  r=get(url,params);data=r.json();p.write_bytes(gzip.compress(r.content,mtime=0))
 if kind=='atlas':
  assert isinstance(data,list) and all(x['prb_id'] in ids and x['msm_id']==msm and a<=x['timestamp']<b for x in data)
  assert len({(x['prb_id'],x['timestamp']) for x in data})==len(data)
  count=len(data)
 else:
  assert isinstance(data,dict) and data.get('data') is not None
  count=sum(len(x.get('values',[])) for group in data['data'] for x in group)
 meta={'url':url,'params':params,'kind':kind,'records_or_values':count,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
 p.with_suffix('.metadata.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps({'asn':asn,'file':p.name,'records_or_values':count}),flush=True)
 return meta
jobs=[(c,'ioda',None,None) for c in cohorts]+[(c,'atlas',m,k) for c in cohorts for m in (10,11) for k in (1001,1010)]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(fetch,jobs))
(ROOT/'download_summary.json').write_text(json.dumps({'files':results,'atlas_records':sum(x['records_or_values'] for x in results if x['kind']=='atlas'),'protocol_sha256':hashlib.sha256(p.read_bytes()).hexdigest()},indent=2)+'\n')
