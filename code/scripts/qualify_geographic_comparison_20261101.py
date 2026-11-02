from pathlib import Path
import json,hashlib,datetime
from scripts.geographic_leverage_diagnostics import comparison_qualification
root=Path('deliverables/2026-11-01_geographic_comparison_v2');raw=json.loads((root/'results.json').read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();m=json.loads((root/'manifest.json').read_text())
for n,v in m['outputs'].items():assert sha(root/n)==v['sha256']
diag={(d['policy'],d['signal'],d['region']):d for d in raw['leverage_diagnostics']};rows=[]
for r in raw['flat_comparisons']:
 q=comparison_qualification(diag[r['policy'],r['signal'],r['region']]) if r['estimable'] else dict(qualified=False,reason=r['reason'])
 rows.append(dict(**r,qualified_regional_comparison=q['qualified'],qualification_reason=q['reason'],qualified_display_difference=r['difference_hd_slope'] if q['qualified'] else None))
assert len(rows)==126 and sum(r['estimable'] for r in rows)==3 and sum(r['qualified_regional_comparison'] for r in rows)==0
out=Path('deliverables/2026-11-01_GEOGRAPHIC_COMPARISON.json');assert not out.exists();out.write_text(json.dumps(dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),numerical_rows=rows,leverage_diagnostics=raw['leverage_diagnostics'],hd_bands={r['signal']:r['hd_band'] for r in raw['support_inputs']},summary=raw['summary'],qualified_regional_comparisons=0,raw_product_sha256=sha(root/'results.json'),source_manifest_sha256=raw['source_manifest_sha256'],independent_receipt_sha256=raw['independent_receipt_sha256'],interpretation_guard_sha256=sha('docs/superpowers/specs/2026-11-01-geographic-interpretation-guard.md'),guard_code_sha256=sha('scripts/geographic_leverage_diagnostics.py'),scope='Completed geographic support/conditional-slope diagnostic. Three numerical coefficients preserved, none qualify as an adequately supported regional contrast. No country/global ranking, zero-effect claim or causality.',whole_study_accepted=False),indent=2)+'\n')
print('126 rows retained, 3 numerical estimates, 0 qualified regional displays; raw p-values unchanged')
