"""Complete hash-checked LOYO dose and conditional recovery model export."""
import json
from .summarize_stop_target_curves_20261023 import ROOT, verified

families = {}
counts = {}
for family, version, count_key in (('associations', 'v1', 'estimable_models'), ('recovery_cox', 'v2', 'estimable')):
    records = []
    for year in range(2018, 2022):
        directory = f'analysis/2026-10-28_loyo_{family}/{version}/full_omit_{year}'
        rows = verified(directory, 'results.json')
        summary = verified(directory, 'summary.json')
        assert len(rows) == summary['models'] == 12
        actual = sum(all(outcome['estimable'] for outcome in row['results'].values()) if family == 'associations' else bool(row['estimable']) for row in rows)
        assert actual == summary[count_key]
        records.extend(dict(omitted_reference_year=year, **row) for row in rows)
    assert len(records) == 48
    families[family] = records
    counts[family] = dict(models=len(records), estimable=sum(all(outcome['estimable'] for outcome in row['results'].values()) if family == 'associations' else bool(row['estimable']) for row in records))
target = ROOT / 'deliverables/2026-10-28_LOYO_MODELS.json'
assert not target.exists()
target.write_text(json.dumps(dict(
    scope='All four omitted reference years and all preselected model specifications; unavailable models/reasons retained. Dose models use country/start-year-month fixed effects and country CR0, not causal identification; conditional Cox uses country sandwich and the existing uniformly applied post-hoc health rules. Complete72 conditions on future completeness. No multiplicity, long-climate-reference or same-sample certification. Not final study acceptance.',
    families=families), indent=2, allow_nan=False) + '\n')
print(json.dumps(counts))
