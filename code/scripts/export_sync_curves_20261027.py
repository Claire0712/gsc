"""Export every supported synchronous-sensitivity curve term, hash checked."""
import json
from .summarize_stop_target_curves_20261023 import ROOT, verified

rows = []
diagnostics = []
for universe in ('joint', 'all'):
    for signal in ('ping-slash24', 'bgp'):
        key = universe + '_' + signal
        base = 'analysis/2026-10-26_sync_'
        fit = verified(base + 'hour/v1/' + key, 'estimates.json')
        infer = verified(base + 'inference/v1/' + key, 'inference.json')
        wild = verified(base + 'wild/v1/' + key, 'bootstrap.json')
        assert fit['signal'] == infer['signal'] == wild['signal'] == signal
        assert fit['countries'] == infer['country_clusters'] == wild['countries']
        assert len(fit['terms']) == 15 and fit['terms'][6] == 'heat_day_0'
        for outcome in ('signed', 'deficit', 'below95'):
            for i, term in enumerate(fit['terms']):
                rows.append(dict(universe=universe, signal=signal, outcome=outcome,
                    term=term, beta=fit['results'][outcome]['beta'][i],
                    country_wild_basic95=wild['results'][outcome]['basic_interval95'][i],
                    countries=fit['countries'], groups=fit['groups'], draws=wild['draws']))
            for covariance, report in infer['results'][outcome].items():
                diagnostics.append(dict(universe=universe, signal=signal, outcome=outcome,
                    covariance=covariance,
                    **{k: v for k, v in report.items() if k not in ('covariance', 'interval95')}))
assert len(rows) == 180 and len(diagnostics) == 48
target = ROOT / 'deliverables/2026-10-27_SYNC_CURVES.json'
assert not target.exists()
target.write_text(json.dumps(dict(
    scope='Signal-specific exact candidate timestamps excluded from source references and target computational views. Raw observations retained; unconfirmed candidates are not established faults. Joint and all source universes remain separate. All outcomes/terms exported. Nonstudentized country-wild intervals are not multiplicity adjusted, equivalence tests, paired same-sample contrasts or causal effects. Non-PSD diagnostics retained.',
    unavailable=[dict(universe=u, signal='merit-nt', reason='Zero matched curve groups at frozen main caliper 1; no estimate, not zero effect') for u in ('joint', 'all')],
    coefficients=rows, diagnostics=diagnostics), indent=2, allow_nan=False) + '\n')
