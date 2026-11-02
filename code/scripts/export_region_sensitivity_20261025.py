"""All existing country-deletion specifications, preserving structural omissions."""
from collections import Counter
import json
from pathlib import Path
from .summarize_stop_target_curves_20261023 import ROOT,verified

directories=sorted(p for p in Path('analysis/2026-10-25_region_sensitivity/v1').glob('full_*') if p.is_dir())
assert len(directories)==12
specifications=[];ranges=[]
for directory in directories:
    summary=verified(str(directory),'summary.json');reports=verified(str(directory),'results.json')
    assert len(reports)==summary['omissions']
    specification={k:summary[k] for k in ('signal','setting','model')}
    counts={outcome:dict(estimable=sum(r['results'][outcome]['estimable'] for r in reports),
                        nonestimable_reasons=dict(Counter(r['results'][outcome]['reason'] for r in reports if not r['results'][outcome]['estimable'])))
            for outcome in reports[0]['results']}
    specifications.append(dict(**specification,omissions=len(reports),outcome_counts=counts))
    for outcome in reports[0]['results']:
        for term in sorted({term for report in reports for term in report['terms']}):
            values=[(report['results'][outcome]['beta'][report['terms'].index(term)],report['omitted_region'])
                    for report in reports if report['results'][outcome]['estimable'] and term in report['terms']]
            ranges.append(dict(**specification,outcome=outcome,term=term,estimable_omissions=len(values),
                structurally_omitted_regions=[r['omitted_region'] for r in reports if term not in r['terms']],
                minimum=min(values)[0] if values else None,minimum_region=min(values)[1] if values else None,
                maximum=max(values)[0] if values else None,maximum_region=max(values)[1] if values else None,
                positive=sum(v>0 for v,c in values),negative=sum(v<0 for v,c in values)))
target=ROOT/'deliverables/2026-10-25_REGION_DELETION_ALL_SPECIFICATIONS.json'
assert not target.exists()
target.write_text(json.dumps(dict(scope='All three signals, A/B, M1/M2, five outcomes; archived World Bank region grouping, not historical event-year classification. Deletion ranges are not confidence intervals or independent replications. Structural omissions/nonestimability retained; no available fits yield null, not zero coefficients. Numerical audits do not certify identification or small-cluster validity.',specifications=specifications,ranges=ranges),indent=2,allow_nan=False)+'\n')
print(json.dumps(dict(specifications=len(specifications),deletion_fits=sum(s['omissions']*5 for s in specifications),range_rows=len(ranges),estimable_fits=sum(v['estimable'] for s in specifications for v in s['outcome_counts'].values()))))
