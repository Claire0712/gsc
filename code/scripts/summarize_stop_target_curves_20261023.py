"""Read-only, hash-checked target-window sensitivity comparison (not remasking)."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verified(directory, filename):
    path = ROOT / directory / filename
    manifest = json.loads((path.parent / 'manifest.json').read_text())
    expected = manifest['outputs'][filename]
    data = path.read_bytes()
    assert len(data) == expected['bytes'], path
    assert hashlib.sha256(data).hexdigest() == expected['sha256'], path
    return json.loads(data)


def collect():
    rows = []
    for variant in ('q95', 'min3'):
        for scenario in ('unknown_end_plusminus7', 'unknown_end_plusminus30'):
            for signal, label in (('ping-slash24', 'ap'), ('bgp', 'bgp'), ('merit-nt', 'merit-nt')):
                key = f'{variant}_{scenario}_{signal}'
                base = verified(f'analysis/2026-10-23_variant_hour_curve/v1/{variant}_{label}', 'estimates.json')
                changed = verified(f'analysis/2026-10-23_stop_scenario_hour/v1/{key}', 'estimates.json')
                wild = verified(f'analysis/2026-10-23_stop_scenario_wild/v1/{key}', 'bootstrap.json')
                original_wild = verified(f'analysis/2026-10-23_variant_wild/v1/{variant}_{label}', 'bootstrap.json')
                assert base['terms'] == changed['terms']
                assert base['signal'] == changed['signal'] == wild['signal'] == signal
                assert changed['countries'] == wild['countries']
                for outcome in changed['results']:
                    for index, term in enumerate(changed['terms']):
                        before = base['results'][outcome]['beta'][index]
                        after = changed['results'][outcome]['beta'][index]
                        rows.append(dict(variant=variant, scenario=scenario, signal=signal,
                            outcome=outcome, term=term, primary_beta=before, scenario_beta=after,
                            change=after-before, primary_interval95=original_wild['results'][outcome]['basic_interval95'][index],
                            scenario_interval95=wild['results'][outcome]['basic_interval95'][index],
                            primary_countries=base['countries'], scenario_countries=changed['countries'],
                            primary_groups=base['groups'], scenario_groups=changed['groups']))
    return rows


if __name__ == '__main__':
    result = collect()
    assert len(result) == 12 * 3 * 15
    destination = ROOT / 'deliverables/2026-10-16/STOP_TARGET_CURVE_COMPARISON_2026-10-23.json'
    assert not destination.exists()
    destination.write_text(json.dumps(dict(scope='Target-window exclusion and rematching only; reference_remasking=false. Hypothetical unknown-end scenarios, not inferred shutdown dates. Country wild basic intervals are nonstudentized; comparisons are not paired tests, equivalence tests, causal evidence, or multiplicity-adjusted claims.', rows=result), indent=2)+'\n')
    for row in result:
        if row['outcome'] == 'signed' and row['term'] == 'heat_day_0':
            print(row)
