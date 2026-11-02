"""Hash-checked all-specification remaining sensitivity model integration."""
import json
from .summarize_stop_target_curves_20261023 import ROOT, verified

keys = ('cyclone_100_24','cyclone_500_24','cyclone_100_72','cyclone_300_72','cyclone_500_72','stop_7','stop_30','sync_joint','sync_all','past_only')
families = {}
counts = {}
not_emitted = []
for family, version, count_key in (('associations','v1','estimable_models'),('cox','v2','estimable')):
    records = []
    reports = {}
    for key in keys:
        directory = f'analysis/2026-10-28_sensitivity_{family}/{version}/{key}'
        rows = verified(directory, 'results.json')
        summary = verified(directory, 'summary.json')
        assert len(rows) == summary['models']
        expected = 8 if family=='associations' and key in ('sync_joint','sync_all') else 12
        assert len(rows) == expected
        if expected == 8:
            assert not any(r['signal']=='merit-nt' for r in rows)
            not_emitted.append(dict(sensitivity=key, family=family, signal='merit-nt', specifications=4, reason='No main-caliper matched Telescope integral groups; driver emitted no signal models, not a zero estimate.'))
        count = sum(all(o['estimable'] for o in r['results'].values()) if family=='associations' else bool(r['estimable']) for r in rows)
        assert count == summary[count_key]
        reports[key] = dict(models=len(rows), estimable=count)
        records.extend(dict(sensitivity=key, **r) for r in rows)
    assert len(records) == (112 if family=='associations' else 120)
    families[family] = records
    counts[family] = reports
target = ROOT / 'deliverables/2026-10-28_ALTERNATIVE_BASELINE_MODELS.json'
assert not target.exists()
target.write_text(json.dumps(dict(scope='All ten existing preselected source/target baseline or exclusion sensitivities. All emitted models and unavailable reasons retained; non-emitted signal specifications explicitly separate. Observational changed samples, not paired causal contrasts. Conditional Cox health rules are existing post-hoc rules, complete72 conditions on future completeness; no multiplicity or causal certification. Not final study acceptance.', families=families, counts=counts, not_emitted=not_emitted),indent=2,allow_nan=False)+'\n')
print(json.dumps(counts))
