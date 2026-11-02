"""Hash-checked complete LOYO curve integration; no new inference."""
import json
from .summarize_stop_target_curves_20261023 import ROOT, verified

rows = []
diagnostics = []
for year in range(2018, 2022):
    for signal in ('ping-slash24', 'bgp', 'merit-nt'):
        key = f'omit_{year}_{signal}'
        base = 'analysis/2026-10-27_loyo_'
        fit = verified(base + 'hour/v1/' + key, 'estimates.json')
        infer = verified(base + 'inference/v1/' + key, 'inference.json')
        wild = verified(base + 'wild/v1/' + key, 'bootstrap.json')
        assert fit['signal'] == infer['signal'] == wild['signal'] == signal
        assert fit['countries'] == infer['country_clusters'] == wild['countries']
        assert len(fit['terms']) == 15 and fit['terms'][6] == 'heat_day_0'
        for outcome in ('signed', 'deficit', 'below95'):
            for i, term in enumerate(fit['terms']):
                rows.append(dict(omitted_reference_year=year, signal=signal, outcome=outcome,
                    term=term, beta=fit['results'][outcome]['beta'][i],
                    country_wild_basic95=wild['results'][outcome]['basic_interval95'][i],
                    groups=fit['groups'], countries=fit['countries'], draws=wild['draws']))
            for covariance, report in infer['results'][outcome].items():
                diagnostics.append(dict(omitted_reference_year=year, signal=signal, outcome=outcome,
                    covariance=covariance,
                    **{k: v for k, v in report.items() if k not in ('covariance', 'interval95')}))
assert len(rows) == 540 and len(diagnostics) == 144
target = ROOT / 'deliverables/2026-10-28_LOYO_CURVES.json'
assert not target.exists()
target.write_text(json.dumps(dict(
    scope='All four omitted reference years, jointly recomputed Q90 Tmax/Tmin thresholds and warm-season selection; source/target baselines and matching rebuilt. Every curve term/outcome retained. Country-wild basic intervals are nonstudentized, unadjusted across specifications, not equivalence or paired common-sample contrasts. Non-PSD covariance diagnostics retained. This completes the curve table only, not LOYO dose/recovery models or final study acceptance.',
    coefficients=rows, diagnostics=diagnostics), indent=2, allow_nan=False) + '\n')
for row in rows:
    if row['outcome'] == 'signed' and row['term'] == 'heat_day_0':
        print(json.dumps(row))
