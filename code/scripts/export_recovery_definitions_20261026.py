"""Hash-checked complete four-definition recovery model handoff."""
import json
from .summarize_stop_target_curves_20261023 import ROOT,verified

records=[]
for definition in ('90_4h','98_4h','95_2h','95_6h'):
    directory='analysis/2026-10-26_recovery_cox/v1/full_'+definition
    rows=verified(directory,'results.json')
    summary=verified(directory,'summary.json')
    assert len(rows)==summary['models']==12
    records.extend(dict(definition=definition,**r) for r in rows)
assert len(records)==48 and sum(r['estimable'] for r in records)==30
target=ROOT/'deliverables/2026-10-26_RECOVERY_DEFINITION_MODELS.json'
assert not target.exists()
target.write_text(json.dumps(dict(scope='All four preselected one-factor definitions, three signals, primary/complete72 and M1/M2. Unavailable models and reasons retained. Conditional observational recovery only; changed definitions change endpoint/risk set. Country sandwich intervals and asymptotic PH diagnostics unadjusted for multiplicity. Existing post-hoc numerical health rules applied uniformly, not newly preregistered. Not causal/global-resilience or final study certification.',models=records),indent=2,allow_nan=False)+'\n')
print(json.dumps(dict(models=len(records),estimable=sum(r['estimable'] for r in records))))
