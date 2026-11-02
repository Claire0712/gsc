"""Build a new self-contained platform from the preserved replay, no network/data downloads."""
from pathlib import Path
import re,json,hashlib,time,argparse
parser=argparse.ArgumentParser();parser.add_argument('--output',default='deliverables/2026-10-29_platform');args=parser.parse_args()
root=Path(__file__).resolve().parents[1];out=root/args.output
assert not out.exists()
source=root/'deliverables/2026-10-16/replay_full/index.html'
raw=source.read_text();payload=re.search(r'<script id="dataset" type="application/json">(.*?)</script>',raw,re.S).group(1)
rows=json.loads(payload);assert len(rows)==2730 and len({r['event_id'] for r in rows})==910
countries=json.loads((root/'data/worldbank/countries.json').read_text())[1]
locations={r['id']:dict(name=r['name'],lon=float(r['longitude']),lat=float(r['latitude']),capital=r['capitalCity']) for r in countries if r.get('longitude') and r.get('latitude') and r['region']['id']!='NA'}
template=root/'web/platform/index.template.html';html=template.read_text()
boundary=root/'outputs/2026-10-29_map_boundaries/adm0_display.geojson'
boundary_manifest=root/'outputs/2026-10-29_map_boundaries/manifest.json'
assert hashlib.sha256(boundary.read_bytes()).hexdigest()==json.loads(boundary_manifest.read_text())['output_sha256']
html=html.replace('<script id="dataset"', '<script id="boundaries" type="application/json">'+boundary.read_text().replace('</','<\\/')+'</script><script id="dataset"',1)
html=html.replace('无国家边界源可用，暂不绘制行政区填色。','叠加已有 geoBoundaries ADM0 概化轮廓，仅作定位背景；不是故障范围。')
for marker,value in {'__DATASET__':payload,'__LOCATIONS__':json.dumps(locations,ensure_ascii=False).replace('</','<\\/'),'__CORE__':(root/'web/platform/core.js').read_text(),'__APP__':(root/'web/platform/app.js').read_text()}.items():
    assert html.count(marker)==1;html=html.replace(marker,value)
assert '__DATASET__' not in html and 'https://' not in html
out.mkdir();(out/'index.html').write_text(html)
sources=[source,root/'data/worldbank/countries.json',template,root/'web/platform/core.js',root/'web/platform/app.js',Path(__file__),boundary,boundary_manifest]
manifest=dict(records=len(rows),events=910,countries=len({r['country_id'] for r in rows}),
 mapped_countries=len({r['country_id'] for r in rows}&locations.keys()),
 point_semantics='World Bank country metadata, mostly capitals; not outage/device locations or boundary polygons',
 sources={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
 output_sha256=hashlib.sha256((out/'index.html').read_bytes()).hexdigest(),
 browser_interaction_verified=False,whole_study_accepted=False,created_unix=time.time())
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
