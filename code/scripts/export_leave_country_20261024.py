"""Export all focal-term country-deletion ranges, not confidence intervals."""
import json
from .summarize_stop_target_curves_20261023 import ROOT, verified

directory='analysis/2026-10-24_leave_country/v1/full_ap_A_M1'
reports=verified(directory,'results.json');summary=verified(directory,'summary.json')
assert len(reports)==summary['omissions']==summary['source_countries']==109
rows=[]
for outcome in reports[0]['results']:
    for i,term in enumerate(reports[0]['terms']):
        values=[(r['results'][outcome]['beta'][i],r['omitted_country']) for r in reports if r['results'][outcome]['estimable']]
        lo,hi=min(values),max(values)
        rows.append(dict(outcome=outcome,term=term,estimable_omissions=len(values),
            unavailable_omissions=[r['omitted_country'] for r in reports if not r['results'][outcome]['estimable']],
            minimum=lo[0],minimum_omitted_country=lo[1],maximum=hi[0],maximum_omitted_country=hi[1],
            positive_coefficients=sum(v>0 for v,c in values),negative_coefficients=sum(v<0 for v,c in values)))
assert len(rows)==15
target=ROOT/'deliverables/2026-10-24/LEAVE_COUNTRY_AP_A_M1_2026-10-24.json'
assert not target.exists()
target.write_text(json.dumps(dict(scope='Primary AP A/M1 country deletion only, not region deletion or all specifications. Ranges of dependent deletion coefficients are not confidence intervals or independent replications. All outcomes/terms retained, CR0 covariance not independently recertified by deletion audit. No causal or global-robustness claim.',source_summary=summary,ranges=rows),indent=2,allow_nan=False)+'\n')
print(json.dumps(dict(omissions=len(reports),outcome_term_rows=len(rows))))
