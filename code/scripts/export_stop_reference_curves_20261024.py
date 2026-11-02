"""Hash-checked complete six-model export, not additional inference."""
import json
from .summarize_stop_target_curves_20261023 import ROOT, verified

rows=[];diagnostics=[]
for scenario in ('unknown_end_plusminus7','unknown_end_plusminus30'):
    for signal in ('ping-slash24','bgp','merit-nt'):
        key=scenario+'_'+signal
        fit=verified('analysis/2026-10-24_stop_reference_hour/v1/'+key,'estimates.json')
        infer=verified('analysis/2026-10-24_stop_reference_inference/v1/'+key,'inference.json')
        wild=verified('analysis/2026-10-24_stop_reference_wild/v1/'+key,'bootstrap.json')
        assert fit['signal']==infer['signal']==wild['signal']==signal
        assert fit['countries']==infer['country_clusters']==wild['countries']
        assert len(fit['terms'])==15 and fit['terms'][6]=='heat_day_0'
        for outcome in ('signed','deficit','below95'):
            for i,term in enumerate(fit['terms']):
                rows.append(dict(scenario=scenario,signal=signal,outcome=outcome,term=term,
                    beta=fit['results'][outcome]['beta'][i],
                    country_wild_basic95=wild['results'][outcome]['basic_interval95'][i],
                    countries=fit['countries'],groups=fit['groups'],draws=wild['draws']))
            for covariance,report in infer['results'][outcome].items():
                diagnostics.append(dict(scenario=scenario,signal=signal,outcome=outcome,covariance=covariance,
                    **{k:v for k,v in report.items() if k not in ('covariance','interval95')}))
assert len(rows)==270 and len(diagnostics)==72
target=ROOT/'deliverables/2026-10-16/STOP_FULL_REFERENCE_CURVES_2026-10-24.json'
assert not target.exists()
target.write_text(json.dumps(dict(scope='Both source and target hypothetical STOP masks; original main heat definition and forward routing. All terms/outcomes exported. Basic country wild intervals are nonstudentized, not equivalence tests or adjusted paired tests. CR0 lead diagnostics are asymptotic; non-PSD covariance flags retained without repair. Not causal outage confirmation or final study certification.',coefficients=rows,diagnostics=diagnostics),indent=2,allow_nan=False)+'\n')
for row in rows:
    if row['outcome']=='signed' and row['term']=='heat_day_0':print(json.dumps(row))
for row in diagnostics:
    if row['outcome']=='signed' and row['covariance']=='country':print(json.dumps(row))
