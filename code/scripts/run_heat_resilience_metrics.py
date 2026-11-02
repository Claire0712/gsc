"""Audited descriptive metrics from completed baseline artifacts only.

Technical metrics use analysis_available, preserving observed known-confounded
slots as observations. The separate full_observed_unconfounded flag requires
upstream target_analysis_unconfounded throughout the fixed window. Neither flag
certifies final sample eligibility or a causal heat effect. Held routes remain
held. Unknown STOP records, uncertain cyclone edges and missing mask coverage
are preserved as separate reasons. No held event is released by this driver.

All baseline products are verified against the completed manifest. Its upstream
input chain is retained as provenance, not re-certified by rereading raw data.
"""
import argparse
import io
import json
import os
from pathlib import Path
import time
import numpy as np
if __package__:
    from . import run_connection_baseline as upstream
    from . import heat_resilience_metrics as core
else:
    import run_connection_baseline as upstream
    import heat_resilience_metrics as core


def run(baseline_directory,output):
    baseline_directory=Path(baseline_directory).absolute();output=Path(output).absolute()
    if output.exists():raise FileExistsError(output)
    if baseline_directory.resolve() in output.resolve().parents or output.resolve() in baseline_directory.resolve().parents or output.resolve()==baseline_directory.resolve():
        raise ValueError('Input/output overlap')
    started=time.monotonic()
    sources=upstream.Sources()
    stage=upstream.Stage(baseline_directory,sources,status_key='status',manifest_key=('status','completed'))
    summary=stage.json('summary.json')
    if summary.get('status')!='completed' or summary.get('mask_bits')!=upstream.MASK_BITS or summary.get('final_sample_eligible') is not False:
        raise ValueError('Unsupported baseline summary schema or scope')
    # All products are small tables or per-event archives, not global raw arrays.
    for name in stage.outputs:sources.verify(baseline_directory/name,stage.outputs[name])
    fields='event_id country_id ioda_iso2 signal point_file expected_full_slots target_valid_slots baseline_available_slots analysis_available_slots full_target_and_baseline target_stop_or_cyclone_slots target_cyclone_uncertain_slots target_mask_coverage_unknown_slots unresolved_stop_country_records unknown_end_stop_country_records full_observed_unconfounded final_sample_eligible'.split()
    audits=stage.rows('event_baseline_audit.csv',fields)
    routes=stage.rows('event_routing.csv',['event_id','country_id','route','start_date','end_exclusive_utc'])
    held=stage.rows('held_stop_review.csv',['event_id','country_id','route'])
    route_map={r['event_id']:r for r in routes}
    if len(route_map)!=len(routes):raise ValueError('Duplicate routing events')
    if {r['event_id'] for r in held}!={r['event_id'] for r in routes if r['route']=='held_stop_review'}:
        raise ValueError('Held routes disagree')
    seen=set();points=set();results=[]
    selected_countries=summary['selected_countries'];selected_signals=summary['selected_signals']
    expected={(r['event_id'],s) for r in routes if r['route']=='forward' and r['country_id'] in selected_countries for s in selected_signals}
    for row in audits:
        key=row['event_id'],row['signal']
        if key in seen or row['point_file'] in points:raise ValueError('Duplicate audit key or archive')
        seen.add(key);points.add(row['point_file'])
        route=route_map.get(row['event_id'])
        if route is None or route['route']!='forward' or route['country_id']!=row['country_id']:
            raise ValueError('Non-forward or mismatched audit route')
        if upstream.archive.boolean(row['final_sample_eligible']):raise ValueError('Unexpected upstream final eligibility')
        start,end,full=upstream._event_bounds(route)
        targets=np.arange(start,full,600,dtype=np.int64)
        with np.load(io.BytesIO(stage.read(row['point_file'])),allow_pickle=False) as z:
            arrays={k:z[k] for k in z.files}
        for name in ['event_id','country_id','signal']:
            if name not in arrays or arrays[name].ndim!=0 or str(arrays[name].item())!=row[name]:raise ValueError('NPZ identity mismatch')
        for name in ['target_timestamps','target_values','baseline','analysis_available','target_valid','baseline_available',
                     'core_mask','target_exclusion_bits','target_mask_coverage_complete','target_analysis_unconfounded']:
            if name not in arrays or arrays[name].shape!=targets.shape:raise ValueError('Missing or invalid NPZ array: '+name)
        if arrays['target_timestamps'].dtype.kind not in 'iu' or not np.array_equal(targets,arrays['target_timestamps']):
            raise ValueError('Fixed event window mismatch')
        for name in ['analysis_available','target_valid','baseline_available','core_mask','target_mask_coverage_complete','target_analysis_unconfounded']:
            if arrays[name].dtype.kind!='b':raise ValueError('NPZ mask must be Boolean')
        bits=arrays['target_exclusion_bits']
        if bits.dtype.kind not in 'iu' or np.any(bits>31):raise ValueError('Unknown target mask bit')
        if not np.array_equal(arrays['core_mask'],targets<end):raise ValueError('Core mask mismatch')
        available=arrays['analysis_available'];unconfounded=arrays['target_analysis_unconfounded']
        if not np.array_equal(unconfounded,available & ((bits&22)==0)) or not np.array_equal(arrays['target_mask_coverage_complete'],(bits&16)==0):
            raise ValueError('Confound mask algebra mismatch')
        counts=dict(expected_full_slots=len(targets),target_valid_slots=int(arrays['target_valid'].sum()),
                    baseline_available_slots=int(arrays['baseline_available'].sum()),analysis_available_slots=int(available.sum()),
                    target_stop_or_cyclone_slots=int(np.count_nonzero(bits&6)),target_cyclone_uncertain_slots=int(np.count_nonzero(bits&8)),
                    target_mask_coverage_unknown_slots=int(np.count_nonzero(bits&16)))
        if any(int(row[k])!=v for k,v in counts.items()):raise ValueError('Audit counts disagree with NPZ')
        if upstream.archive.boolean(row['full_target_and_baseline'])!=bool(available.all()) or upstream.archive.boolean(row['full_observed_unconfounded'])!=bool(unconfounded.all()):
            raise ValueError('Audit completeness mismatch')
        unknown=((bits&8)!=0)|((bits&16)!=0)
        metrics=core.metrics_from_baseline(arrays,start,end,unknown_review=unknown)
        if metrics['valid_slots']!=int(available.sum()):raise ValueError('Availability permits invalid observation/reference')
        reasons=['final_sample_review_not_completed']
        if not metrics['full_window_complete']:reasons.append('incomplete_observation_or_reference')
        if counts['target_stop_or_cyclone_slots']:reasons.append('target_stop_or_conservative_cyclone_flag')
        if counts['target_cyclone_uncertain_slots']:reasons.append('uncertain_cyclone_edge')
        if counts['target_mask_coverage_unknown_slots']:reasons.append('unknown_mask_calendar_coverage')
        for key in ['unresolved_stop_country_records','unknown_end_stop_country_records']:
            if int(row[key])<0:raise ValueError('Negative STOP uncertainty count')
            if int(row[key]):reasons.append(key)
        results.append(dict(event_id=row['event_id'],country_id=row['country_id'],ioda_iso2=row['ioda_iso2'],signal=row['signal'],
                            source_point_file=row['point_file'],route='forward',final_sample_eligible=False,
                            full_observed_unconfounded=bool(unconfounded.all()),qualification_reasons=reasons,
                            upstream_audit=row,metrics=metrics))
    if seen!=expected or len(audits)!=summary['signal_windows']:raise ValueError('Selected event/signal set incomplete')
    if points!={n for n in stage.outputs if n.endswith('.npz')}:raise ValueError('Unaccounted point archives')
    sources.check()
    output.mkdir(parents=True,exist_ok=False)
    archive=upstream.archive
    def publish(name,value):archive.atomic(output/name,archive.json_data(value))
    publish('status.json',dict(status='running',pid=os.getpid()))
    try:
        publish('event_metrics.json',results)
        csvrows=[]
        for r in results:
            row={k:r[k] for k in ['event_id','country_id','signal','final_sample_eligible','full_observed_unconfounded']}
            row.update({k:r['metrics'][k] for k in ['dhrd_hours','signed_deviation_hours','coverage_fraction','state','core_end_state','recurrence_during_core']})
            row.update(recovery_status=r['metrics']['recovery']['status'],recovery_confirmation_hours=r['metrics']['recovery']['confirmation_hours'],
                       qualification_reasons=';'.join(r['qualification_reasons']))
            csvrows.append(row)
        archive.write_csv(output/'event_metrics.csv',list(csvrows[0]) if csvrows else ['event_id'],csvrows)
        for name in ['event_routing.csv','held_stop_review.csv']:archive.atomic(output/name,stage.read(name))
        report=dict(status='completed',signal_windows=len(results),technical_complete_windows=sum(r['metrics']['full_window_complete'] for r in results),
                    full_observed_unconfounded_windows=sum(r['full_observed_unconfounded'] for r in results),held_stop_review_rows=len(held),
                    final_sample_eligible=False,causal_effect_estimated=False,scope='descriptive_technical_metrics_only',
                    confound_policy=__doc__,elapsed_seconds=time.monotonic()-started,finished_utc=archive.now(),
                    baseline_directory=str(baseline_directory))
        publish('summary.json',report)
        sources.check()
        products={p.name:archive.fingerprint(p) for p in output.iterdir() if p.name!='status.json'}
        scripts={str(Path(m.__file__).resolve()):archive.fingerprint(Path(m.__file__)) for m in [core,upstream,archive]}
        scripts[str(Path(__file__).resolve())]=archive.fingerprint(Path(__file__))
        publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products,scripts=scripts,numpy_version=np.__version__))
        publish('status.json',dict(status='completed',pid=os.getpid()))
        return report
    except BaseException as exc:
        publish('status.json',dict(status='failed',error=str(exc)));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();print(json.dumps(run(args.baseline,args.output)))
