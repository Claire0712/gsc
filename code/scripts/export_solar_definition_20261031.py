"""Hash-checked descriptive overlap, without implying common network samples."""
from pathlib import Path
import csv,json,hashlib,statistics
root=Path(__file__).resolve().parents[1];p=root/'analysis/2026-10-31_solar_catalogue/v1/full_outputs';m=json.loads((p/'manifest.json').read_text());h=hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest()
for suffix in ('.verify.json','.events.verify.json'):
 v=json.loads(p.with_name(p.name+suffix).read_text());assert v['status']=='verified' and v['manifest_sha256']==h
for n,e in m['outputs'].items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==e['sha256']
def get(mode):
 rows=list(csv.DictReader((p/mode/'analysis_events.csv').open()));d={(r['country_id'],r['start_date']):r for r in rows};assert len(d)==len(rows);return d
a=get('solar');b=get('utc');common=sorted(a.keys()&b.keys());same=[k for k in common if a[k]['end_exclusive_utc']==b[k]['end_exclusive_utc']];ca={k for k,r in a.items() if r['weather_candidate']=='True'};cb={k for k,r in b.items() if r['weather_candidate']=='True'}
def season(mode):return {r['country_id']:r['warm_season_start_month'] for r in csv.DictReader((p/mode/'warm_seasons.csv').open())}
sa=season('solar');sb=season('utc');report=dict(solar_events=len(a),utc_events=len(b),same_country_start=len(common),same_full_bounds=len(same),same_start_changed_end=len(common)-len(same),solar_weather_candidates=len(ca),utc_weather_candidates=len(cb),same_candidate_country_start=len(ca&cb),changed_warm_season_countries=[c for c in sa if sa[c]!=sb[c]],median_hd_difference_same_bounds=statistics.median(float(a[k]['hd_c_days'])-float(b[k]['hd_c_days']) for k in same),manifest_sha256=h,scope='Weather definition sensitivity only; matched starts need not share end dates or network windows. No solar-day network-effect acceptance or causal claim.');q=root/'deliverables/2026-10-31_SOLAR_DEFINITION_COMPARISON.json';assert not q.exists();q.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
