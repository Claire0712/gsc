"""Hash-checked all-five-scenario curve export; no new inference or selection."""
import json
from .summarize_stop_target_curves_20261023 import ROOT, verified

rows=[];diagnostics=[]
for scenario in ('100_24','500_24','100_72','300_72','500_72'):
    for signal in ('ping-slash24','bgp','merit-nt'):
        key=scenario+'_'+signal
        fit=verified('analysis/2026-10-25_cyclone_hour/v1/'+key,'estimates.json')
        infer=verified('analysis/2026-10-25_cyclone_inference/v1/'+key,'inference.json')
        wild=verified('analysis/2026-10-25_cyclone_wild/v1/'+key,'bootstrap.json')
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
assert len(rows)==675 and len(diagnostics)==180
target=ROOT/'deliverables/2026-10-25_CYCLONE_ALL_CURVES.json'
assert not target.exists()
target.write_text(json.dumps(dict(scope='All five preselected alternative cyclone masks. Both source and target remasked, primary STOP and main heat/forward routing unchanged. All terms and outcomes exported, not selected by significance. Basic country-wild intervals are nonstudentized and unadjusted across specifications; not equivalence or paired same-sample tests. Country-CR0 leads are asymptotic diagnostics; non-PSD flags retained without repair. This completes this curve branch only, not dose/recovery-model sensitivity, outage/causal or final study certification.',coefficients=rows,diagnostics=diagnostics),indent=2,allow_nan=False)+'\n')
for row in rows:
    if row['outcome']=='signed' and row['term']=='heat_day_0':print(json.dumps(row))
for row in diagnostics:
    if row['outcome']=='signed' and row['covariance']=='country':print(json.dumps(row))
