"""All four weather-only LOYO catalogues using unchanged event construction."""
import argparse
import io
import json
import time
from pathlib import Path
import pandas as pd
from . import heat_catalogue_variants_core as core
from .loyo_catalogue_inputs import loyo_inputs
from .run_connection_baseline import Sources, Stage


def run(a):
    started = time.monotonic()
    out = Path(a.output)
    if out.exists():
        raise FileExistsError(out)
    src = Sources()
    thresholds_stage = Stage(a.thresholds, src, status_key='status', manifest_key=('status', 'completed'))
    thresholds = pd.read_csv(io.BytesIO(thresholds_stage.read('thresholds.csv')), dtype={'country_id': str})
    data, sources, exclusions = core.load_inputs(a.daily, a.countries.split(',') if a.countries else None)
    for item in sources:
        src.verify(item['path'], {'sha256': item['sha256']})
        src.verify(Path(item['path']).with_suffix('.audit.json'), {'sha256': item['audit_sha256']})
    for name in ('run_loyo_catalogues.py', 'loyo_catalogue_inputs.py', 'heat_catalogue_variants_core.py'):
        src.verify(Path(__file__).with_name(name))
    out.mkdir(parents=True)
    products = {}
    results = {}
    for omit in range(2018, 2022):
        variant = f'omit_{omit}'
        target = out / variant
        target.mkdir()
        tables = {name: [] for name in ('raw_events.csv', 'process_events.csv', 'analysis_events.csv', 'daily_heat_flags.csv.gz', 'warm_seasons.csv')}
        for country, frame in data.groupby('country_id', sort=True):
            q, season = loyo_inputs(thresholds.loc[thresholds.country_id == country], frame, omit)
            flagged = core.attach_thresholds(frame.loc[frame.date >= '2021-01-01'], q)
            r, p, e, d = core.catalogue_country(flagged, season['warm_season_start_month'])
            for name, table in zip(list(tables)[:4], (r, p, e, d)):
                tables[name].append(table)
            tables['warm_seasons.csv'].append(pd.DataFrame([dict(country_id=country, omitted_reference_year=omit, **season)]))
        combined = {name: pd.concat(parts, ignore_index=True) for name, parts in tables.items()}
        for name, table in combined.items():
            table.to_csv(target / name, index=False, compression='gzip' if name.endswith('.gz') else None)
            products[variant + '/' + name] = Sources().verify(target / name)
        rules = dict(omitted_reference_year=omit, threshold='Q90,84/93 and all three remaining years', warm_season='Three months, same omitted year', network_screened=False)
        (target / 'rules.json').write_text(json.dumps(rules, indent=2) + '\n')
        products[variant + '/rules.json'] = Sources().verify(target / 'rules.json')
        events = combined['analysis_events.csv']
        results[variant] = dict(analysis_events=len(events), weather_candidates=int(events.weather_candidate.sum()), countries=int(events.country_id.nunique()))
        print(variant, json.dumps(results[variant]), flush=True)
    src.check()
    summary = dict(variants=results, elapsed_seconds=time.monotonic() - started, scope='Weather-only LOYO; both thresholds and season omit the same reference year. Original event construction and 2021 context. Not connectivity eligibility or effect sensitivity completion.')
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    products['summary.json'] = Sources().verify(out / 'summary.json')
    (out / 'manifest.json').write_text(json.dumps(dict(status='completed', inputs=src.entries, outputs=products), indent=2) + '\n')
    (out / 'status.json').write_text('{"status":"completed"}\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('daily', 'thresholds', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--countries')
    run(parser.parse_args())
