"""All existing country-deletion specifications, preserving structural omissions."""
from collections import Counter
import json
from pathlib import Path
from .summarize_stop_target_curves_20261023 import ROOT,verified

directories=[Path('analysis/2026-10-24_leave_country/v1/full_ap_A_M1')]
directories+=sorted(p for p in Path('analysis/2026-10-24_country_sensitivity/v1').glob('full_*') if p.is_dir())
assert len(directories)==12
specifications=[];ranges=[]
for directory in directories:
    summary=verified(str(directory),'summary.json');reports=verified(str(directory),'results.json')
    assert len(reports)==summary['omissions']==summary['source_countries']
    specification={k:summary[k] for k in ('signal','setting','model')}
    counts={outcome:dict(estimable=sum(r['results'][outcome]['estimable'] for r in reports),
                        nonestimable_reasons=dict(Counter(r['results'][outcome]['reason'] for r in reports if not r['results'][outcome]['estimable'])))
            for outcome in reports[0]['results']}
    specifications.append(dict(**specification,omissions=len(reports),outcome_counts=counts))
    for outcome in reports[0]['results']:
        for term in sorted({term for report in reports for term in report['terms']}):
            values=[(report['results'][outcome]['beta'][report['terms'].index(term)],report['omitted_country'])
                    for report in reports if report['results'][outcome]['estimable'] and term in report['terms']]
            ranges.append(dict(**specification,outcome=outcome,term=term,estimable_omissions=len(values),
                structurally_omitted_countries=[r['omitted_country'] for r in reports if term not in r['terms']],
                minimum=min(values)[0] if values else None,minimum_country=min(values)[1] if values else None,
                maximum=max(values)[0] if values else None,maximum_country=max(values)[1] if values else None,
                positive=sum(v>0 for v,c in values),negative=sum(v<0 for v,c in values)))
target=ROOT/'deliverables/2026-10-24/COUNTRY_DELETION_ALL_SPECIFICATIONS_2026-10-24.json'
assert not target.exists()
target.write_text(json.dumps(dict(scope='All three signals, A/B, M1/M2, five outcomes. Country deletion ranges are not confidence intervals, independent replications or region-deletion evidence. Structural omissions and nonestimability retained; zero available fits yield null ranges, not zero coefficients. Numerical audits do not certify identification or small-cluster validity.',specifications=specifications,ranges=ranges),indent=2,allow_nan=False)+'\n')
print(json.dumps(dict(specifications=len(specifications),deletion_fits=sum(s['omissions']*5 for s in specifications),range_rows=len(ranges),estimable_fits=sum(v['estimable'] for s in specifications for v in s['outcome_counts'].values()))))
