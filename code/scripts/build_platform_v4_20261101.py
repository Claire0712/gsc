"""Build a new self-contained platform from the preserved replay, no network/data downloads."""
from pathlib import Path
import re,json,hashlib,time,argparse
parser=argparse.ArgumentParser();parser.add_argument('--output',default='deliverables/2026-11-01_platform_v4');args=parser.parse_args()
root=Path(__file__).resolve().parents[1];out=root/args.output
assert not out.exists()
source=root/'deliverables/2026-10-16/replay_full/index.html'
raw=source.read_text();payload=re.search(r'<script id="dataset" type="application/json">(.*?)</script>',raw,re.S).group(1)
rows=json.loads(payload);assert len(rows)==2730 and len({r['event_id'] for r in rows})==910
countries=json.loads((root/'data/worldbank/countries.json').read_text())[1]
locations={r['id']:dict(name=r['name'],lon=float(r['longitude']),lat=float(r['latitude']),capital=r['capitalCity']) for r in countries if r.get('longitude') and r.get('latitude') and r['region']['id']!='NA'}
template=root/'web/platform_v4/index.template.html';html=template.read_text()

social_path=root/'analysis/2026-10-20_dlep/v1/full_outputs/rows.json'
social_manifest=root/'analysis/2026-10-20_dlep/v1/full_outputs/manifest.json'
social_receipt=root/'analysis/2026-10-20_dlep/v1/full.verify.json'
sm=json.loads(social_manifest.read_text());sv=json.loads(social_receipt.read_text())
assert sv['status']=='verified' and sv['manifest_sha256']==hashlib.sha256(social_manifest.read_bytes()).hexdigest()
assert hashlib.sha256(social_path.read_bytes()).hexdigest()==sm['outputs']['rows.json']['sha256']
social_rows=json.loads(social_path.read_text());social={r['event_id']:r for r in social_rows};assert len(social)==len(social_rows)==910
ap={r['event_id']:r for r in rows if r['signal']=='ping-slash24'};assert set(ap)==set(social)
for key,r in social.items():
 assert r['country_id']==ap[key]['country_id'] and r['signal']=='ping-slash24'
 assert r['dhrd_hours']==ap[key]['metrics']['dhrd_hours']
 if r['dlep_proxy'] is not None:
  assert r['full_observed_unconfounded'] and abs(r['dlep_proxy']-r['dhrd_hours']*r['population_2025']*r['internet']['value'])<=max(1e-7,abs(r['dlep_proxy'])*1e-12)
assert sum(r['dlep_proxy'] is not None for r in social.values())==454
html=html.replace('<script id="dataset"','<script id="social" type="application/json">'+json.dumps(social,ensure_ascii=False,allow_nan=False).replace('</','<\\/')+'</script><script id="dataset"',1)

boundary=root/'outputs/2026-10-29_map_boundaries/adm0_display.geojson'
boundary_manifest=root/'outputs/2026-10-29_map_boundaries/manifest.json'
assert hashlib.sha256(boundary.read_bytes()).hexdigest()==json.loads(boundary_manifest.read_text())['output_sha256']
html=html.replace('<script id="dataset"', '<script id="boundaries" type="application/json">'+boundary.read_text().replace('</','<\\/')+'</script><script id="dataset"',1)
html=html.replace('无国家边界源可用，暂不绘制行政区填色。','叠加已有 geoBoundaries ADM0 概化轮廓，仅作定位背景；不是故障范围。')
for marker,value in {'__DATASET__':payload,'__LOCATIONS__':json.dumps(locations,ensure_ascii=False).replace('</','<\\/'),'__CORE__':(root/'web/platform_v4/core.js').read_text(),'__APP__':(root/'web/platform_v4/app.js').read_text()}.items():
    assert html.count(marker)==1;html=html.replace(marker,value)
assert '__DATASET__' not in html and 'https://' not in html
extra=[]
primary=root/'deliverables/2026-11-01_primary_figures_v2'
pm=primary/'manifest.json';pr=primary/'visual_review.json';pmb=json.loads(pm.read_text());prb=json.loads(pr.read_text())
assert prb['status']=='verified' and prb['figure_manifest_sha256']==hashlib.sha256(pm.read_bytes()).hexdigest()
primary_data=primary/'source_data.json';assert hashlib.sha256(primary_data.read_bytes()).hexdigest()==pmb['outputs']['source_data.json']['sha256']
spatial_path=root/'outputs/2026-10-31_pixel_country_summary.csv';spatial_manifest=root/'outputs/2026-11-01_pixel_metadata/comparison_manifest.json';spatial_verify=root/'outputs/2026-11-01_pixel_metadata/comparison_verify.json';smb=json.loads(spatial_manifest.read_text());svb=json.loads(spatial_verify.read_text());assert svb['status']=='verified' and svb['manifest_sha256']==hashlib.sha256(spatial_manifest.read_bytes()).hexdigest();assert hashlib.sha256(spatial_path.read_bytes()).hexdigest()==smb['outputs']['country_summary.csv']['sha256']
import csv
spatial_rows=[]
for row in csv.DictReader(spatial_path.open()):
 r={'country_id':row['country_id']}
 for key,value in row.items():
  if key=='country_id':continue
  r[key]=int(value) if key.endswith('_days') else float(value) if value else None
 spatial_rows.append(r)
assert len(spatial_rows)==214 and len({r['country_id'] for r in spatial_rows})==214
solar=root/'deliverables/2026-11-01_COUNTRY_SOLAR_DEFINITION_COMPARISON.json';solar_data=json.loads(solar.read_text());assert solar_data['manifest_sha256']=='c94b4bd3930041bcf535dd2eb2a72cd3a965057b67f058346611475291393aea'
spatial_summary=root/'outputs/2026-11-01_pixel_metadata/comparison_summary.json'
results=dict(primary=json.loads(primary_data.read_text()),spatial=dict(countries=spatial_rows,summary=json.loads(spatial_summary.read_text())),weather_definition=solar_data,scope='Fixed 2022-2025 study samples; event filters do not refit these estimates. Spatial means are not event damage or causality.')
extra=[primary_data,pm,pr,spatial_path,spatial_manifest,spatial_verify,spatial_summary,solar,root/'web/platform_v4/results.js',root/'web/platform_v4/results_app.js']
results['source_sha256']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in extra[:8]}
html=html.replace('<script id="dataset"','<script id="analysis-results" type="application/json">'+json.dumps(results,ensure_ascii=False,allow_nan=False).replace('</','<\\/')+'</script><script id="dataset"',1)
html=html.replace('</body>', '<script>'+extra[-2].read_text()+'</script><script>'+extra[-1].read_text()+'</script></body>',1)

out.mkdir();(out/'index.html').write_text(html)
sources=extra+[source,root/'data/worldbank/countries.json',template,root/'web/platform_v4/core.js',root/'web/platform_v4/app.js',Path(__file__),boundary,boundary_manifest,social_path,social_manifest,social_receipt]
manifest=dict(records=len(rows),events=910,countries=len({r['country_id'] for r in rows}),
 mapped_countries=len({r['country_id'] for r in rows}&locations.keys()),
 point_semantics='World Bank country metadata, mostly capitals; not outage/device locations or boundary polygons',
 sources={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
 output_sha256=hashlib.sha256((out/'index.html').read_bytes()).hexdigest(),
 browser_interaction_verified=False,whole_study_accepted=False,created_unix=time.time())
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
