"""Export all existing variant coefficients and diagnostics, without refitting."""
import json
import time
from .summarize_stop_target_curves_20261023 import ROOT, verified


def collect():
    coefficients, diagnostics = [], []
    for variant in ('absolute35', 'q95', 'min3', 'min6', 'season6', 'all_year', 'absolute30'):
        for label in ('ap', 'bgp', 'merit-nt'):
            key = variant + '_' + label
            fit = verified('analysis/2026-10-23_variant_hour_curve/v1/' + key, 'estimates.json')
            infer = verified('analysis/2026-10-23_variant_curve_inference/v1/' + key, 'inference.json')
            wild = verified('analysis/2026-10-23_variant_wild/v1/' + key, 'bootstrap.json')
            assert fit['signal'] == infer['signal'] == wild['signal']
            assert fit['countries'] == infer['country_clusters'] == wild['countries']
            assert len(fit['terms']) == 15 and fit['terms'][6] == 'heat_day_0'
            for outcome in ('signed', 'deficit', 'below95'):
                for index, term in enumerate(fit['terms']):
                    coefficients.append(dict(variant=variant, signal=fit['signal'], outcome=outcome,
                        term=term, beta=fit['results'][outcome]['beta'][index],
                        country_wild_basic95=wild['results'][outcome]['basic_interval95'][index],
                        countries=fit['countries'], groups=fit['groups'], draws=wild['draws'],
                        enumerated=wild['enumerated']))
                for covariance, report in infer['results'][outcome].items():
                    diagnostics.append(dict(variant=variant, signal=fit['signal'], outcome=outcome,
                        covariance=covariance, countries=fit['countries'],
                        few_country_clusters=infer['few_country_clusters'],
                        **{k:v for k,v in report.items() if k not in ('covariance', 'interval95')}))
    assert len(coefficients) == 21 * 3 * 15
    assert len(diagnostics) == 21 * 3 * 4
    assert len({(r['variant'],r['signal'],r['outcome'],r['term']) for r in coefficients}) == len(coefficients)
    return coefficients, diagnostics


if __name__ == '__main__':
    started = time.monotonic()
    coefficients, diagnostics = collect()
    target = ROOT / 'deliverables/2026-10-16/ALL_VARIANT_CURVE_TABLES_2026-10-23.json'
    assert not target.exists()
    target.write_text(json.dumps(dict(
        scope='All seven definitions and three signals, without significance selection. Separate samples, not common-support comparisons. Country wild intervals are nonstudentized basic intervals, not equivalence tests. Lead tests are asymptotic CR0 diagnostics, not proof of identification. Non-PSD multiway estimates are retained and flagged, not repaired. No multiplicity correction is applied in this export.',
        coefficients=coefficients, diagnostics=diagnostics), indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(coefficients=len(coefficients), diagnostics=len(diagnostics),
        non_psd=sum(not r['psd'] for r in diagnostics),
        elapsed_seconds=time.monotonic()-started)))
    for r in diagnostics:
        if r['outcome']=='signed' and r['covariance']=='country':
            print(json.dumps(r))
