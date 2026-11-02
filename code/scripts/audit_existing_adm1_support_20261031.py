"""Read-only existing ADM1 availability and indistinguishable-series audit."""
from pathlib import Path
from collections import defaultdict,Counter
import argparse,json,gzip,hashlib,time
import numpy as np
from .run_connection_baseline import Sources
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--pilot',action='store_true');a=p.parse_args();started=time.monotonic();out=Path(a.output);assert not out.exists();out.mkdir(parents=True);sources=Sources();records=[];groups=defaultdict(list);counters=Counter()
files=sorted(Path('data/ioda/adm1_six_countries/raw').glob('*.metadata.json'))
if a.pilot:files=[f for f in files if '_2024_Q1_batch00_' in f.name]
assert files
for path in files:
 metadata=json.loads(sources.read(path));task=metadata['task'];assert task['id']==metadata['id']
 if task['year'] not in (2022,2023,2024,2025):continue
 rawpath=Path('data')/metadata['file'];assert rawpath.is_relative_to(Path('data/ioda/adm1_six_countries/raw'))
 raw=json.loads(gzip.decompress(sources.read(rawpath,metadata)));assert not raw.get('error');seen=set();byhash=defaultdict(list)
 for batch in raw['data']:
  for s in batch:
   code=str(s['entityCode']);assert s['entityType']=='region' and code in task['regions'] and code not in seen;seen.add(code)
   assert s['datasource']==task['datasource'] and s['step']==s['nativeStep'] and s['step']>0
   assert task['from']<=s['from']<task['until'] and s['until']<=task['until']
   values=np.array(s['values'],dtype=np.float64);valid=np.isfinite(values)&(values>=0);expected=(task['until']-task['from'])/s['step'];assert expected==int(expected)
   digest=hashlib.sha256(np.asarray(values,dtype='<f8').tobytes()).hexdigest();byhash[(s['from'],s['step'],len(values),digest)].append(code)
   records.append(dict(country=task['country'],region=code,signal=task['datasource'],year=task['year'],quarter=task['quarter'],native_step=s['step'],requested_slots=int(expected),returned_slots=len(values),valid_nonnegative=int(valid.sum()),nonmissing=int(np.isfinite(values).sum()),values_sha256=digest,from_seconds=s['from']))
 assert set(metadata['regions_without_series'])==set(task['regions'])-seen
 counters['requests']+=1;counters['returned_series']+=len(seen);counters['absent_series']+=len(set(task['regions'])-seen)
 for key,codes in byhash.items():
  if len(codes)>1:groups[task['country'],task['year'],task['quarter'],task['datasource']].append(dict(regions=codes,values_sha256=key[-1],points=key[2]))
sources.verify(Path(__file__));sources.check();summary=dict(pilot=a.pilot,metadata_files_selected=len(files),**dict(counters),identical_series_groups=sum(len(v) for v in groups.values()),elapsed_seconds=time.monotonic()-started,scope='Existing raw native ADM1 response audit only. Identical numerical series do not demonstrate independent regional resolution and are not automatically confirmed faults. Native-slot availability is not country10minute eligibility or geometry crosswalk; no guessed region mapping, observation filling or new download.')
def save(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
save('series_records.json',records);save('identical_groups.json',[dict(country=k[0],year=k[1],quarter=k[2],signal=k[3],groups=v) for k,v in sorted(groups.items())]);save('summary.json',summary);save('manifest.json',dict(inputs=sources.entries,outputs={n:Sources().verify(out/n) for n in ('series_records.json','identical_groups.json','summary.json')}));save('status.json',dict(status='completed'));print(json.dumps(summary))
