"""Download historical probe inventories; snapshots are not connectivity outcomes."""
import bz2,collections,concurrent.futures,csv,hashlib,json
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]/'downloads/reconstruction_pilot/historical_coverage'
ROOT.mkdir(parents=True,exist_ok=True)
def fetch(day):
 url=f'https://ftp.ripe.net/ripe/atlas/probes/archive/{day[:4]}/{day[4:6]}/{day}.json.bz2'
 p=ROOT/f'probes_{day}.json.bz2'
 if not p.exists():
  s=requests.Session();s.trust_env=False;r=s.get(url,timeout=90);r.raise_for_status()
  data=json.loads(bz2.decompress(r.content));assert isinstance(data['objects'],list)
  p.write_bytes(r.content)
 else:data=json.loads(bz2.decompress(p.read_bytes()))
 eligible=[x for x in data['objects'] if x.get('is_public') and x.get('status')==1 and x.get('asn_v4') and x.get('country_code')]
 countries=collections.Counter(x['country_code'] for x in eligible)
 asns=collections.defaultdict(set)
 for x in eligible:asns[x['country_code']].add(x['asn_v4'])
 meta={'date':day,'url':url,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'objects':len(data['objects']),'eligible_probes':len(eligible),'countries_any':len(countries),'countries_10probes_3asns':sum(n>=10 and len(asns[c])>=3 for c,n in countries.items()),'definition':'public, connected at snapshot, IPv4 ASN and country known; does not establish actual result availability or representativeness'}
 (ROOT/f'probes_{day}.metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
 print(json.dumps(meta),flush=True)
 return meta,[{'date':day,'country':c,'probes':n,'asns':len(asns[c])} for c,n in sorted(countries.items())]
days=[f'{y}{m:02d}01' for y in range(2018,2022) for m in (1,4,7,10)]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(fetch,days))
with (ROOT/'country_snapshot_coverage.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=['date','country','probes','asns']);w.writeheader()
 for _,rows in results:w.writerows(rows)
(ROOT/'coverage_summary.json').write_text(json.dumps({'snapshots':[x[0] for x in results],'threshold_note':'10 probes and 3 ASNs is a descriptive screen, not a validated IODA replacement criterion.','historical_ioda_completed':False},indent=2)+'\n')
