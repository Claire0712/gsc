from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1];base=root/'analysis/2026-10-31_country_solar/v1';h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();months={};seconds=0.;rows=sample_checks=clock_checks=utc_finite=utc_missing=0;maximum=0.;clocks=set()
for year in range(2018,2026):
 for month in range(1,13):
  label=f'{year}{month:02d}';p=base/('full_'+label);m=json.loads((p/'manifest.json').read_text());mh=h(p/'manifest.json');assert json.loads((p/'status.json').read_text())['status']=='completed'
  for name in ('summary.json','country_clocks.json'):assert h(p/name)==m['outputs'][name]['sha256']
  a=json.loads(p.with_name(p.name+'.verify.json').read_text());b=json.loads(p.with_name(p.name+'.utc.verify.json').read_text());assert a['status']==b['status']=='verified' and a['manifest_sha256']==b['manifest_sha256']==mh;s=json.loads((p/'summary.json').read_text());assert s['defined_country_clocks']==214;months[label]=mh;seconds+=s['elapsed_seconds'];rows+=s['rows'];sample_checks+=a['sample_cell_day_metric_checks'];clock_checks+=a['all_country_clock_checks'];utc_finite+=b['finite_utc_metric_checks'];utc_missing+=b['matched_missing_metrics'];maximum=max(maximum,b['max_error']);clocks.add(h(p/'country_clocks.json'))
assert len(months)==96 and len(clocks)==1 and rows==636996 and utc_finite+utc_missing==3*rows
result=dict(status='verified_monthly_aggregation',months=96,country_days=rows,production_seconds_sum=seconds,scalar_cell_day_metric_checks=sample_checks,country_clock_checks=clock_checks,utc_finite_metric_checks=utc_finite,utc_missing_metric_checks=utc_missing,utc_max_error=maximum,constant_country_clocks_sha256=next(iter(clocks)),monthly_manifest_sha256=months,scope='Exact fixed-population circular-mean country clocks, monthly aggregation and both independent receipts; catalogue checks are separate. Not solar-day network effect or whole-study acceptance.')
p=root/'deliverables/2026-11-01_COUNTRY_SOLAR_AGGREGATION_RECEIPT.json';assert not p.exists();p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='monthly_manifest_sha256'}))
