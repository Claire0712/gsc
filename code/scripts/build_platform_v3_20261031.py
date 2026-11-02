"""Build a new self-contained platform from the preserved replay, no network/data downloads."""
from pathlib import Path
import re,json,hashlib,time,argparse
parser=argparse.ArgumentParser();parser.add_argument('--output',default='deliverables/2026-10-31_platform_v3');args=parser.parse_args()
root=Path(__file__).resolve().parents[1];out=root/args.output
assert not out.exists()
source=root/'deliverables/2026-10-16/replay_full/index.html'
raw=source.read_text();payload=re.search(r'<script id="dataset" type="application/json">(.*?)</script>',raw,re.S).group(1)
rows=json.loads(payload);assert len(rows)==2730 and len({r['event_id'] for r in rows})==910
countries=json.loads((root/'data/worldbank/countries.json').read_text())[1]
locations={r['id']:dict(name=r['name'],lon=float(r['longitude']),lat=float(r['latitude']),capital=r['capitalCity']) for r in countries if r.get('longitude') and r.get('latitude') and r['region']['id']!='NA'}
template=root/'web/platform_v3/index.template.html';html=template.read_text()

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
for marker,value in {'__DATASET__':payload,'__LOCATIONS__':json.dumps(locations,ensure_ascii=False).replace('</','<\\/'),'__CORE__':(root/'web/platform_v3/core.js').read_text(),'__APP__':(root/'web/platform_v3/app.js').read_text()}.items():
    assert html.count(marker)==1;html=html.replace(marker,value)
assert '__DATASET__' not in html and 'https://' not in html
out.mkdir();(out/'index.html').write_text(html)
sources=[source,root/'data/worldbank/countries.json',template,root/'web/platform_v3/core.js',root/'web/platform_v3/app.js',Path(__file__),boundary,boundary_manifest,social_path,social_manifest,social_receipt]
manifest=dict(records=len(rows),events=910,countries=len({r['country_id'] for r in rows}),
 mapped_countries=len({r['country_id'] for r in rows}&locations.keys()),
 point_semantics='World Bank country metadata, mostly capitals; not outage/device locations or boundary polygons',
 sources={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
 output_sha256=hashlib.sha256((out/'index.html').read_bytes()).hexdigest(),
 browser_interaction_verified=False,whole_study_accepted=False,created_unix=time.time())
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
