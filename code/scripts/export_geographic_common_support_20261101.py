from pathlib import Path
import json,csv,hashlib,math
import numpy as np
from scripts.geographic_leverage_diagnostics import diagnostics as leverage_diagnostics
base=Path('analysis/2026-11-01_geographic_support/v1/full_outputs');sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();m=json.loads((base/'manifest.json').read_text());receipt=Path(str(base)+'.verify.json');v=json.loads(receipt.read_text());assert v['status']=='verified' and v['manifest_sha256']==sha(base/'manifest.json')
for n,x in m['outputs'].items():assert sha(base/n)==x['sha256']
results=json.loads((base/'results.json').read_text());summary=json.loads((base/'summary.json').read_text());inputs=json.loads((base/'support_inputs.json').read_text());flat=[];diagnostics=[]
for r in results:
 for outcome in ('mean_deficit_core','maintenance_core','peak_loss_core'):
  f=r['results'].get(outcome,{});ok=bool(f.get('estimable'));flat.append(dict(policy=r['policy'],signal=r['signal'],region=r['region'],region_label=r['region_label'],other_events=r['after_joint_support'][0]['events'],region_events=r['after_joint_support'][1]['events'],other_countries=r['after_joint_support'][0]['countries'],region_countries=r['after_joint_support'][1]['countries'],outcome=outcome,estimable=ok,reason='' if ok else f.get('reason',r.get('reason','unavailable')),difference_hd_slope=f.get('difference_hd_slope'),ci95_lower=f['interval95_normal'][-1][0] if ok else None,ci95_upper=f['interval95_normal'][-1][1] if ok else None,p_normal=f.get('difference_p_normal'),q_bh=f.get('q_bh'),q_by=f.get('q_by'),residual_df=f.get('residual_df'),predicted_outside_unit_interval=f.get('predicted_outside_unit_interval')))
 if not any(f.get('estimable') for f in r['results'].values()):continue
 z=np.load(base/r['matrix'],allow_pickle=False);gids={rr['country_id'] for rr in next(i for i in inputs if i['signal']==r['signal'])['predictor_complete'] if rr['region']==r['region']};diagnostics.append(dict(policy=r['policy'],signal=r['signal'],region=r['region'],**leverage_diagnostics(z['x'],z['z'],z['countries'],gids)))
assert len(flat)==126 and sum(r['estimable'] for r in flat)==3
out=Path('deliverables/2026-11-01_geographic_comparison_v2');assert not out.exists();out.mkdir(parents=True)
with (out/'all_comparisons.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
product=dict(summary=summary,results=results,support_inputs=inputs,flat_comparisons=flat,leverage_diagnostics=diagnostics,source_manifest_sha256=sha(base/'manifest.json'),independent_receipt_sha256=sha(receipt),auditor_sha256=sha('scripts/audit_geographic_common_support_20261101.py'),scope='Every frozen region/signal/policy/outcome retained, unsupported values missing. Conditional HD slope contrasts only, not country rankings or causal regional differences.',whole_study_accepted=False)
(out/'results.json').write_text(json.dumps(product,indent=2)+'\n');(out/'manifest.json').write_text(json.dumps(dict(source_manifest_sha256=sha(base/'manifest.json'),independent_receipt_sha256=sha(receipt),outputs={n:dict(bytes=(out/n).stat().st_size,sha256=sha(out/n)) for n in ['results.json','all_comparisons.csv']},whole_study_accepted=False),indent=2)+'\n');print(json.dumps(diagnostics));print('126 comparison rows, three estimable; source/audit hashes verified')
