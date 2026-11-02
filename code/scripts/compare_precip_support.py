"""Descriptive single-slice precipitation support comparison; never recomputes rainfall."""
import argparse
import csv
import hashlib
import json
import math
import pathlib
import sys
import time
from datetime import datetime, timezone


def unique(rows, key):
    values = [r[key] for r in rows]
    if any(not v for v in values) or len(values) != len(set(values)):
        raise ValueError('Missing or duplicate ' + key)
    return set(values)


def compare(rows, crosswalk, events):
    boundaries = unique(rows, 'boundary_code')
    unique(crosswalk, 'ioda_iso2')
    exact = [r for r in crosswalk if r['joint_status'] == 'exact_joint_match']
    matched = unique(exact, 'joint_country_id')
    if not matched <= boundaries: raise ValueError('Exact crosswalk boundary absent')
    unique(events, 'event_id')
    if any(r['country_id'] not in boundaries for r in events): raise ValueError('Unknown event boundary')
    candidates = [r for r in events if str(r['weather_candidate']).lower() == 'true']
    groups = {k: [] for k in ['zero_population', 'no_support', 'partial_support', 'full_support']}
    residuals = []
    for r in rows:
        a, f, m = (r[k] for k in ['assigned_population','finite_support_population','missing_support_population'])
        if not all(math.isfinite(v) and v >= 0 for v in [a,f,m]): raise ValueError('Invalid population')
        if not math.isclose(a,f+m,rel_tol=1e-10,abs_tol=1e-7): raise ValueError('Population nonconservation')
        if a and not math.isclose(r['finite_support_fraction'],f/a,rel_tol=1e-10,abs_tol=1e-12):
            raise ValueError('Invalid coverage fraction')
        if not a and r['finite_support_fraction'] is not None: raise ValueError('Zero denominator must be missing')
        residuals.append(abs(a-f-m))
        group = 'zero_population' if a == 0 else 'no_support' if f == 0 else 'full_support' if m == 0 else 'partial_support'
        groups[group].append(r['boundary_code'])
    def counts(codes):
        codes=set(codes)
        return dict(boundaries=len(codes),exact_joint_entities=len(codes & matched),
                    candidate_events_all_boundaries=sum(e['country_id'] in codes for e in candidates),
                    candidate_events_exact_joint=sum(e['country_id'] in codes & matched for e in candidates),
                    candidate_event_countries_exact_joint=len({e['country_id'] for e in candidates if e['country_id'] in codes & matched}),
                    boundary_codes=sorted(codes),exact_joint_codes=sorted(codes & matched))
    usable = [r for r in rows if r['assigned_population'] > 0 and r['finite_support_population'] > 0]
    thresholds={'unrestricted_descriptive': counts(r['boundary_code'] for r in usable)}
    for percent in [80,90,95,99]:
        thresholds['ge_'+str(percent)]=counts(r['boundary_code'] for r in usable if r['finite_support_fraction'] >= percent/100)
    thresholds['strict_complete']=counts(groups['full_support'])
    return dict(denominators=counts(boundaries),thresholds=thresholds,
                categories={k:counts(v) for k,v in groups.items()},
                candidate_event_definition='weather_candidate == True in existing analysis_events.csv; before network eligibility screening',
                all_catalogue_events=len(events),max_population_partition_residual=max(residuals,default=0),
                diagnostic_only=True, full_period_eligibility_certified=False,
                limitations=['2018-01-01 source slice and old 0.1-degree weights only.',
                             'Old spatial assignments have not been independently globally rebuilt/certified.',
                             'No full-period precipitation finite-mask verification.',
                             'Partial-support averages cannot be labelled whole-population means.',
                             'Unrestricted descriptive reference still excludes zero population and no finite support.',
                             'These event retention counts do not apply annual signal eligibility or baseline/window completeness.'])


def create_output(path):
    path.mkdir(parents=True, exist_ok=False)


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser()
    for key in ['support','crosswalk','events','weights','metadata','output-dir']: p.add_argument('--'+key,required=True,type=pathlib.Path)
    args=p.parse_args()
    if args.output_dir.exists(): raise FileExistsError(args.output_dir)
    started=time.time()
    support=json.loads(args.support.read_text())
    hashes={k:dict(path=str(getattr(args,k)),sha256=sha(getattr(args,k))) for k in ['support','crosswalk','events','weights','metadata']}
    for k in ['weights','metadata']:
        if hashes[k]['sha256'] != support[k+'_sha256']: raise ValueError(k+' hash mismatch')
    with args.crosswalk.open() as f: crosswalk=list(csv.DictReader(f))
    with args.events.open() as f: events=list(csv.DictReader(f))
    result=compare(support['rows'],crosswalk,events)
    if result['denominators']['exact_joint_entities'] != 195: raise ValueError('Expected 195 exact joint entities')
    from scipy.sparse import load_npz
    import numpy as np
    matrix=load_npz(args.weights)
    metadata=json.loads(args.metadata.read_text())
    countries=metadata['countries']
    unique(countries,'boundary_code')
    diagnostic={r['boundary_code']:r for r in support['rows']}
    if len(countries) != matrix.shape[0] or set(diagnostic) != {r['boundary_code'] for r in countries}: raise ValueError('Weight boundary mismatch')
    if not np.isfinite(matrix.data).all() or (matrix.data < 0).any(): raise ValueError('Invalid matrix weights')
    totals=np.asarray(matrix.sum(axis=1)).ravel()
    for i,c in enumerate(countries):
        if c['index'] != i: raise ValueError('Metadata row ordering mismatch')
        for target in [c['population_assigned'],diagnostic[c['boundary_code']]['assigned_population']]:
            if not math.isclose(totals[i],target,rel_tol=1e-10,abs_tol=1e-7): raise ValueError('Weight population mismatch')
    if not math.isclose(metadata['positive_population'],metadata['assigned_population']+metadata['unassigned_population'],rel_tol=1e-10): raise ValueError('Global population nonconservation')
    if not math.isclose(float(totals.sum()),metadata['assigned_population'],rel_tol=1e-10): raise ValueError('Matrix total mismatch')
    result.update(source_time=support['source_time'],input_hashes=hashes,script_sha256=sha(__file__),
                  command=sys.argv,finished_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.time()-started,
                  verification=dict(input_weight_hashes_match=True,weight_row_totals_match=True,
                                    matrix_population=float(totals.sum()),global_population_conservation=True,
                                    exact_mapping_unique=True,spatial_weight_certification=False))
    create_output(args.output_dir)
    (args.output_dir/'comparison.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    with (args.output_dir/'threshold_counts.csv').open('w') as f:
        fields=['threshold','boundaries','exact_joint_entities','candidate_events_all_boundaries','candidate_events_exact_joint','candidate_event_countries_exact_joint']
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader()
        for name,row in result['thresholds'].items(): writer.writerow(dict(threshold=name,**{k:row[k] for k in fields[1:]}))
    manifest={p.name:sha(p) for p in args.output_dir.iterdir()}
    (args.output_dir/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(status='completed',output_dir=str(args.output_dir),elapsed_seconds=result['elapsed_seconds'])))


if __name__ == '__main__': main()
