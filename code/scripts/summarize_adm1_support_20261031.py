"""Coverage denominators include requested quarters with absent series."""
from pathlib import Path
from collections import defaultdict,Counter
import json,hashlib,time
p=Path('analysis/2026-10-31_adm1_support/v1/full_outputs');out=p.parent/'support_summary';assert not out.exists();m=json.loads((p/'manifest.json').read_text());v=json.loads(p.with_name('full_outputs.verify.json').read_text());assert v['status']=='verified' and v['manifest_sha256']==hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest()
for n,e in m['outputs'].items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==e['sha256']
rows=json.loads((p/'series_records.json').read_text());requested=defaultdict(dict);observed=defaultdict(list);duplicates=defaultdict(list)
for name,e in m['inputs'].items():
 if not name.endswith('.metadata.json'):continue
 raw=Path(name).read_bytes();assert hashlib.sha256(raw).hexdigest()==e['sha256'];t=json.loads(raw)['task']
 if t['year'] not in (2022,2023,2024,2025):continue
 for region in t['regions']:
  key=t['country'],region,t['datasource'],t['year'];assert t['quarter'] not in requested[key];requested[key][t['quarter']]=t['until']-t['from']
for r in rows:
 observed[r['country'],r['region'],r['signal'],r['year']].append(r)
 duplicates[r['country'],r['year'],r['quarter'],r['signal'],r['from_seconds'],r['native_step'],r['returned_slots'],r['values_sha256']].append(r['region'])
annual=[]
for k,quarters in sorted(requested.items()):
 assert set(quarters)=={1,2,3,4};rr=observed[k];steps={r['native_step'] for r in rr};step=next(iter(steps)) if len(steps)==1 else None
 expected=sum(quarters.values())/step if step else None;valid=sum(r['valid_nonnegative'] for r in rr);fraction=valid/expected if expected else None
 assert fraction is None or 0<=fraction<=1
 annual.append(dict(country=k[0],region=k[1],signal=k[2],year=k[3],requested_quarters=4,returned_quarters=len(rr),native_step=step,expected_native_slots=expected,valid_native_slots=valid,valid_native_fraction=fraction,coverage_at_least80_native=None if fraction is None else fraction>=.8,reason=None if step else 'No single observed native sampling step in this region/source/year; denominator not guessed'))
identity=[dict(country=k[0],year=k[1],quarter=k[2],signal=k[3],from_seconds=k[4],native_step=k[5],points=k[6],values_sha256=k[7],regions=sorted(regions)) for k,regions in sorted(duplicates.items()) if len(regions)>1]
summary=dict(region_source_years=len(annual),native_coverage80=sum(r['coverage_at_least80_native'] is True for r in annual),native_coverage_below80=sum(r['coverage_at_least80_native'] is False for r in annual),denominator_unknown=sum(r['valid_native_fraction'] is None for r in annual),unique_regions=len({(r['country'],r['region']) for r in annual}),countries=sorted({r['country'] for r in annual}),cross_batch_identical_groups=len(identity),scope='Native requested-slot support only; absent quarters remain missing observations and count in denominators when native step is known. This is not10minute annual qualification or reliable geometry crosswalk. Exact identical region vectors do not prove independent spatial signal or confirmed faults. No new data.')
out.mkdir(parents=True)
for name,data in [('annual_native_support.json',annual),('identical_regions.json',identity),('summary.json',summary)]: (out/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
(out/'manifest.json').write_text(json.dumps(dict(original_manifest_sha256=v['manifest_sha256'],metadata_hashes_verified=True,outputs={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir()}),indent=2)+'\n');print(json.dumps(summary))
