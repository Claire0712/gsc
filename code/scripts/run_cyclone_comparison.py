#!/usr/bin/env python3
"""Extended heat/control observations and raw preperiod features, not matching."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import io
import json
import os
from pathlib import Path
import resource
import time

import numpy as np

if __package__:
    from . import run_cyclone_sensitivity_baseline as old
    from . import cyclone_baseline_sensitivity as scenario
    from . import build_control_calendar as calendar
else:
    import run_cyclone_sensitivity_baseline as old
    import cyclone_baseline_sensitivity as scenario
    import build_control_calendar as calendar

archive,core=old.archive,old.core
DAY=86400


def validate_scenario(summary, radius, hours):
    bounds=scenario.coverage_bounds(hours)
    if (radius not in (100,300,500) or summary.get('cyclone_radius_km')!=radius
            or summary.get('cyclone_half_width_hours')!=hours
            or summary.get('cyclone_complete_bounds')!=list(bounds)):
        raise ValueError('Explicit baseline cyclone parameters must match comparison')


def window_definitions(events,controls):
    by_id={e['event_id']:e for e in events}
    if len(by_id)!=len(events):raise ValueError('Duplicate heat event ID')
    windows=[]
    for event in events:
        start,end,_=old._event_bounds(event)
        windows.append(dict(window_id='heat:'+event['event_id'],parent_event_id=event['event_id'],role='heat',country_id=event['country_id'],ioda_iso2=event['ioda_iso2'],start=start,end=end))
    for row in controls:
        if row['matching_calendar_candidate']!='True':continue
        event=by_id[row['event_id']]
        start,end=archive.utc(row['control_start_utc']),archive.utc(row['control_end_exclusive_utc'])
        hs,he,_=old._event_bounds(event)
        if row['country_id']!=event['country_id'] or end-start!=he-hs:raise ValueError('Control parent/country/duration mismatch')
        windows.append(dict(window_id='control:'+row['control_id'],parent_event_id=event['event_id'],role='control',country_id=event['country_id'],ioda_iso2=event['ioda_iso2'],start=start,end=end))
    if len({w['window_id'] for w in windows})!=len(windows):raise ValueError('Duplicate window identity')
    return windows


def window_stats(result,bits,other_heat,start,end,role):
    times=result['target_timestamps']
    expected=np.arange(start-7*DAY,max(end+3*DAY,start+8*DAY),600,dtype=np.int64)
    if role not in ('heat','control') or end<=start or not np.array_equal(times,expected):
        raise ValueError('Full exact extended target grid/role required')
    periods=dict(preperiod=times<start,integral=(times>=start)&(times<end+3*DAY),curve=times<start+8*DAY)
    if np.count_nonzero(periods['preperiod'])!=1008:raise ValueError('Exactly 1008 preperiod slots required')
    forbidden=(bits&1)!=0 if role=='control' else np.asarray(other_heat,dtype=bool).copy()
    forbidden[periods['preperiod']] |= (bits[periods['preperiod']]&1)!=0
    confound=(bits&22)!=0
    valid=result['target_valid'] & np.isfinite(result['target_values']) & (result['target_values']>=0)
    raw=valid & result['target_annual_eligible'] & ~forbidden & ~confound
    technical=raw & result['baseline_available']
    arrays=dict(core_mask=(times>=start)&(times<end),other_heat_mask=other_heat,
                target_heat_forbidden=forbidden,target_raw_available=raw,target_technical_available=technical,
                target_analysis_unconfounded=result['analysis_available']&~confound,
                **{k+'_mask':v for k,v in periods.items()})
    stats={}
    for use,select in periods.items():
        stats.update({use+'_expected_slots':int(select.sum()),
                      use+'_observed_complete':bool(valid[select].all()),
                      use+'_annual_complete':bool(result['target_annual_eligible'][select].all()),
                      use+'_reference_complete':bool(result['baseline_available'][select].all()),
                      use+'_heat_forbidden_slots':int(np.count_nonzero(forbidden&select)),
                      use+'_stop_slots':int(np.count_nonzero(((bits&2)!=0)&select)),
                      use+'_cyclone_slots':int(np.count_nonzero(((bits&4)!=0)&select)),
                      use+'_coverage_unknown_slots':int(np.count_nonzero(((bits&16)!=0)&select)),
                      use+'_raw_available':bool(raw[select].all()),
                      use+'_technical_available':bool(technical[select].all())})
    stats['matching_technical_available']=stats['preperiod_technical_available'] and stats['integral_technical_available']
    # A separate curve gate never silently substitutes for the matching gate.
    stats['matching_curve_technical_available']=stats['matching_technical_available'] and stats['curve_technical_available']
    stats.update(raw_pre_level=None,raw_pre_mad_over_median=None,raw_pre_slope_per_day_over_median=None,
                 raw_pre_normalized_features_available=False,raw_pre_feature_reason='raw_preperiod_not_qualified',matched=False,final_sample_eligible=False)
    if stats['preperiod_raw_available']:
        values=result['target_values'][periods['preperiod']]
        # Long double intermediates avoid avoidable overflow in raw summaries.
        values=values.astype(np.longdouble)
        median=np.median(values)
        stats['raw_pre_level']=float(median)
        if median>0:
            x=np.arange(1008,dtype=np.longdouble)/144
            x-=x.mean();normalized=values/median
            mad=np.median(np.abs(values-median))/median
            slope=np.dot(x,normalized-normalized.mean())/np.dot(x,x)
            if np.isfinite(float(mad)) and np.isfinite(float(slope)):
                stats.update(raw_pre_mad_over_median=float(mad),raw_pre_slope_per_day_over_median=float(slope),raw_pre_normalized_features_available=True,raw_pre_feature_reason='available')
            else:stats['raw_pre_feature_reason']='normalized_feature_nonfinite'
        else:stats['raw_pre_feature_reason']='nonpositive_median'
    return arrays,stats


def run(*,preflight,candidate,connection,quality,heat,stop,cyclone,calendar_dir,baseline,
        output,cyclone_radius,cyclone_hours,countries=None,signals=None):
    started=time.monotonic()
    directories={k:Path(v).absolute() for k,v in dict(preflight=preflight,candidate=candidate,connection=connection,
        quality=quality,heat=heat,stop=stop,cyclone=cyclone,calendar=calendar_dir,baseline=baseline).items()}
    output=Path(output).absolute()
    if any(output.resolve()==p.resolve() or output.resolve() in p.resolve().parents or p.resolve() in output.resolve().parents for p in directories.values()):raise ValueError('Input/output overlap')
    output.mkdir(parents=True,exist_ok=False)
    def publish(name,data):archive.atomic(output/name,archive.json_data(data))
    def progress(**state):publish('status.json',dict(status='running',pid=os.getpid(),elapsed_seconds=time.monotonic()-started,**state))
    progress(stage='verify_source_chain')
    try:
        sources=old.Sources()
        bs=old.Stage(directories['baseline'],sources,status_key='status')
        cal=old.Stage(directories['calendar'],sources,status_key='status')
        baseline_summary=bs.json('summary.json');cal.json('summary.json')
        validate_scenario(baseline_summary, cyclone_radius, cyclone_hours)
        ancestry=bs.manifest['inputs'];cal_ancestry=cal.manifest['inputs']
        def check_chain():
            for path,entry in sources.entries.items():
                p=Path(path)
                roots=[directories[k] for k in ('preflight','candidate','connection','quality','heat','stop','cyclone')]
                if any(root==p.parent for root in roots) and ancestry.get(path)!=entry:
                    raise ValueError('Baseline source chain ancestry mismatch: '+path)
                if p.parent in (directories['candidate'],directories['heat']) and cal_ancestry.get(path)!=entry:
                    raise ValueError('Calendar source chain ancestry mismatch: '+path)
        for module in (old,core,archive,calendar,scenario,scenario.primary):
            p=Path(module.__file__).absolute();entry=sources.verify(p)
            chain=cal_ancestry if module is calendar else ancestry
            prior=[v for k,v in chain.items() if Path(k).name==p.name]
            # The original baseline script hashes itself, core and archive.
            if len(prior)!=1 or prior[0]!=entry:raise ValueError('Code ancestry mismatch: '+p.name)
        sources.verify(Path(__file__).absolute())
        stages={k:old.Stage(directories[k],sources,status_key='state' if k=='cyclone' else 'status') for k in ('preflight','candidate','stop','cyclone')}
        for k,state in [('connection','complete'),('quality','completed'),('heat','complete')]:stages[k]=old.Stage(directories[k],sources,manifest_key=('state',state))
        check_chain()
        if stages['quality'].json('summary.json').get('quality_pass') is not True:raise ValueError('Quality stage failed')
        cs=stages['connection']
        if cs.manifest.get('quarters')!=archive.QUARTERS or {n for n in cs.outputs if n.endswith('.npz')}!={f'ioda_{q}_{s}.npz' for q in archive.QUARTERS for s in archive.SIGNALS}:raise ValueError('48 exact connection archives required')
        cross=stages['preflight'].rows('joint_crosswalk.csv',['ioda_iso2','joint_country_id','joint_status'])
        archive.unique(cross,['ioda_iso2']);exact=[r for r in cross if r['joint_status']=='exact_joint_match'];archive.unique(exact,['joint_country_id'])
        mapping={r['joint_country_id']:r['ioda_iso2'] for r in exact}
        selected=sorted(mapping) if countries is None else list(countries)
        signals=list(archive.SIGNALS) if signals is None else list(signals)
        if not selected or len(set(selected))!=len(selected) or not set(selected)<=set(mapping):raise ValueError('Invalid country selection')
        if not signals or len(set(signals))!=len(signals) or not set(signals)<=set(archive.SIGNALS):raise ValueError('Invalid signal selection')
        routes=stages['candidate'].rows('event_routing.csv',archive.EVENT_FIELDS+['route','ioda_iso2']);archive.unique(routes,['event_id'])
        for name,route in [('forward_candidates.csv','forward'),('held_stop_review.csv','held_stop_review')]:
            if stages['candidate'].rows(name,['event_id','route'])!=[r for r in routes if r['route']==route]:raise ValueError('Routing subset mismatch')
        events=[r for r in routes if r['route']=='forward']
        if any(mapping.get(r['country_id'])!=r['ioda_iso2'] or not archive.boolean(r['weather_candidate']) for r in events):raise ValueError('Forward mapping/weather mismatch')
        if dict(Counter(r['route'] for r in routes))!=baseline_summary['route_counts']:raise ValueError('Baseline routing ancestry mismatch')
        catalogue=stages['heat'].rows('analysis_events.csv',['event_id','country_id','start_date','end_exclusive_utc']);archive.unique(catalogue,['event_id'])
        index={r['event_id']:r for r in catalogue}
        if set(index)!={r['event_id'] for r in routes}:raise ValueError('Catalogue route mismatch')
        for row in routes:
            if any(row[k]!=index[row['event_id']][k] for k in ('country_id','start_date','end_exclusive_utc')):raise ValueError('Catalogue bounds mismatch')
        daily=stages['heat'].read('daily_heat_flags.csv.gz')
        with io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(daily)),encoding='utf-8-sig') as stream:
            heat_by_id=calendar.heat_windows(csv.DictReader(stream,strict=True),catalogue)
        controls=cal.rows('control_calendar.csv',['control_id','matching_calendar_candidate'])
        expected=[{k:str(v) for k,v in row.items()} for event in events for row in calendar.calendar_rows(event,heat_by_id[event['country_id']])]
        if controls!=expected:raise ValueError('Calendar rows differ from independent source reconstruction')
        windows=[w for w in window_definitions(events,controls) if w['country_id'] in selected]
        annual=old.annual_table(stages['quality'].rows('coverage_annual.csv',['country_id','signal','year','expected_points','valid_points','candidate_80pct']))
        sw=defaultdict(list);unresolved=Counter();unknown_end=Counter();seen=set()
        for row in stages['stop'].json('stop_windows.json')['records']:
            if row['source_row'] in seen:raise ValueError('Duplicate STOP record')
            seen.add(row['source_row'])
            if row['windows']:
                if row['country_id'] not in mapping or row['reasons'] or row['national_outage_inferred'] is not False:raise ValueError('Invalid STOP window')
                pair=row['windows']['main'];old.interval_mask(np.array([],dtype=np.int64),[pair]);sw[row['country_id']].append(pair)
                unknown_end[row['country_id']]+=int(row['end_unknown'])
            else:unresolved[row['country_id']]+=1
        cy=stages['cyclone'];prov=cy.json('provenance.json')
        if prov['rules'].get('closed_utc_windows') is not True or not set(selected)<=set(cy.status['completed_countries']) or not set(selected)<=set(prov['selected_ids']):raise ValueError('Cyclone completion gate failed')
        cw=defaultdict(list);kw=defaultdict(list)
        for country in selected:
            data=cy.json(country+'.json')
            if data['country']!=country:raise ValueError('Cyclone country mismatch')
            cw[country],kw[country]=scenario.select_windows(data['windows'],country,cyclone_radius,cyclone_hours)
        check_chain();sources.check()
        grouped=defaultdict(list)
        for i,w in enumerate(windows):grouped[w['country_id']].append((i,w))
        products={};audits=[];phases={}
        for signal in signals:
            times,matrix,history=old.load_signal(cs,signal,[mapping[c] for c in selected],progress);phases[signal]=history;check_chain()
            for ci,country in enumerate(selected):
                heat_pairs=[(w['start'],w['end']) for w in heat_by_id[country]]
                mask_windows=(heat_pairs,sw[country],cw[country],kw[country])
                source_bits=scenario.masks(times,*mask_windows,cyclone_hours);source_annual=old.annual_mask(times,mapping[country],signal,annual)
                for i,w in grouped[country]:
                    start,end=w['start'],w['end'];targets=np.arange(start-7*DAY,max(end+3*DAY,start+8*DAY),600,dtype=np.int64)
                    result=core.retrospective_baseline(times,matrix[ci],reference_excluded=source_bits!=0,annual_eligible=source_annual,target_timestamps=targets)
                    bits=scenario.masks(targets,*mask_windows,cyclone_hours)
                    other=old.interval_mask(targets,[(h['start'],h['end']) for h in heat_by_id[country] if w['role']=='control' or h['event_id']!=w['parent_event_id']])
                    extra,stats=window_stats(result,bits,other,start,end,w['role'])
                    queries=targets[:,None]+np.array(core.RETROSPECTIVE_OFFSETS_DAYS)[None,:]*DAY
                    arrays={k:v for k,v in result.items() if isinstance(v,np.ndarray)}
                    arrays.update(extra,window_id=np.array(w['window_id']),parent_event_id=np.array(w['parent_event_id']),role=np.array(w['role']),
                        event_id=np.array(w['parent_event_id']),country_id=np.array(country),signal=np.array(signal),
                        start_utc_seconds=np.array(start),end_utc_seconds=np.array(end),target_exclusion_bits=bits,
                        reference_exclusion_bits=scenario.masks(queries,*mask_windows,cyclone_hours),reference_annual_eligible=old.annual_mask(queries,mapping[country],signal,annual),
                        reference_present=(queries>=times[0])&(queries<=times[-1]),target_mask_coverage_complete=(bits&16)==0)
                    name=f'window_{i:06d}_{signal}.npz';temporary=output/('.'+name)
                    with temporary.open('wb') as stream:np.savez_compressed(stream,**arrays)
                    os.replace(temporary,output/name);products[name]=archive.fingerprint(output/name)
                    audits.append(dict(**w,signal=signal,point_file=name,extended_slots=len(targets),unresolved_stop_country_records=unresolved[country],unknown_end_stop_country_records=unknown_end[country],**stats))
                    progress(stage='compute_windows',signal=signal,country=country,processed_signal_windows=len(audits))
            del matrix
        for name,stage in [('event_routing.csv',stages['candidate']),('held_stop_review.csv',stages['candidate']),('control_calendar.csv',cal)]:
            archive.atomic(output/name,stage.read(name));products[name]=archive.fingerprint(output/name)
        archive.write_csv(output/'window_audit.csv',list(audits[0]) if audits else ['window_id','matched','final_sample_eligible'],audits)
        products['window_audit.csv']=archive.fingerprint(output/'window_audit.csv')
        counts={}
        for signal in signals:
            counts[signal]={role:{key:sum(bool(r[key]) for r in audits if r['signal']==signal and r['role']==role) for key in
                ('preperiod_raw_available','preperiod_reference_complete','integral_technical_available','curve_technical_available','matching_technical_available','matching_curve_technical_available','raw_pre_normalized_features_available')} for role in ('heat','control')}
        summary=dict(status='completed',cyclone_radius_km=cyclone_radius,cyclone_half_width_hours=cyclone_hours,cyclone_complete_bounds=list(scenario.coverage_bounds(cyclone_hours)),reference_remasking=True,heat_windows=sum(w['role']=='heat' for w in windows),control_windows=sum(w['role']=='control' for w in windows),
            signal_windows=len(audits),selected_countries=selected,selected_signals=signals,exact_country_count=len(mapping),route_counts=dict(Counter(r['route'] for r in routes)),
            calendar_rows_preserved=len(controls),availability_by_signal_role=counts,native_phase_history=phases,mask_bits=old.MASK_BITS,
            source_ancestry_verified=True,raw_features='1008 raw preperiod values only; median, MAD/median, OLS raw slope per day/median; independent of retrospective reference availability',
            heat_policy='Own heat core and recovery allowed; other heat forbidden; any preperiod heat forbidden; all control heat forbidden',
            baseline_policy=baseline_summary['reference_rule'],calendar_coverage_policy=baseline_summary['cyclone_calendar_coverage_policy'],
            confirmed_measurement_anomaly_exclusions=0,matched=False,final_sample_eligible=False,elapsed_seconds=time.monotonic()-started,
            peak_rss_native_units=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        publish('summary.json',summary);products['summary.json']=archive.fingerprint(output/'summary.json')
        check_chain();sources.check()
        publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products,numpy_version=np.__version__))
        publish('status.json',dict(status='completed',pid=os.getpid(),elapsed_seconds=time.monotonic()-started))
        return summary
    except BaseException as exc:
        publish('status.json',dict(status='failed',pid=os.getpid(),error=str(exc),elapsed_seconds=time.monotonic()-started));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('preflight','candidate','connection','quality','heat','stop','cyclone','calendar-dir','baseline','output'):parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--countries',nargs='+');parser.add_argument('--signals',nargs='+',choices=list(archive.SIGNALS))
    parser.add_argument('--cyclone-radius',required=True,type=int,choices=[100,300,500])
    parser.add_argument('--cyclone-hours',required=True,type=int,choices=[24,72])
    print(json.dumps(run(**vars(parser.parse_args())),sort_keys=True))
