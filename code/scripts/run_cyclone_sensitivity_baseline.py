#!/usr/bin/env python3
"""Verified, bounded-memory retrospective baseline runner; no DHRD or inference.

One selected signal matrix is retained at a time. Only existing forward routes
are computed; held routes remain unchanged. Full source manifests must exist,
but a pilot hashes/loads only the selected signals and cyclone countries.
"""
import argparse
import calendar
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat

import numpy as np

try:
    from . import audit_candidate_connectivity as archive
    from . import connection_baseline as core
except ImportError:
    import audit_candidate_connectivity as archive
    import connection_baseline as core


MASK_BITS = {'heat_core_and_72h': 1, 'stop_finite_candidate': 2,
             'cyclone_conservative_300km_24h': 4, 'cyclone_uncertain_edge': 8,
             'cyclone_calendar_coverage_unknown':16}
CYCLONE_COMPLETE_START = archive.utc('2018-01-02T00:00:00Z')
CYCLONE_COMPLETE_END = archive.utc('2025-12-31T00:00:00Z')


def _json(data):
    def unique_pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def invalid(value): raise ValueError('Nonfinite JSON constant: '+value)
    return json.loads(data, object_pairs_hook=unique_pairs, parse_constant=invalid)


class Sources:
    """Hash consumed files and fail on observable mutation before publication."""
    def __init__(self):
        self.entries, self.stamps = {}, {}

    @staticmethod
    def stamp(path):
        s = path.lstat()
        if not stat.S_ISREG(s.st_mode): raise ValueError('Source must be regular, not symlink: '+str(path))
        return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns

    def verify(self, path, expected=None):
        path = Path(path)
        initial = self.stamp(path)
        if path in self.stamps and initial != self.stamps[path]: raise ValueError('Source changed: '+str(path))
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
        entry = dict(bytes=initial[2], sha256=h.hexdigest())
        if self.stamp(path) != initial: raise ValueError('Source changed while hashing')
        if expected is not None:
            size = expected.get('bytes', expected.get('size_bytes'))
            if entry['sha256'] != expected.get('sha256') or (size is not None and entry['bytes'] != size):
                raise ValueError('Input hash/provenance mismatch: '+str(path))
        self.stamps[path], self.entries[str(path)] = initial, entry
        return entry

    def read(self, path, expected=None):
        self.verify(path, expected)
        data = Path(path).read_bytes()
        if hashlib.sha256(data).hexdigest() != self.entries[str(path)]['sha256']:
            raise ValueError('Source changed during read')
        return data

    def check(self):
        for path, initial in self.stamps.items():
            if self.stamp(path) != initial: raise ValueError('Source changed before publication: '+str(path))


class Stage:
    def __init__(self, directory, sources, *, status_key=None, manifest_key=None):
        self.directory, self.sources = Path(directory), sources
        if status_key:
            status = _json(sources.read(self.directory/'status.json'))
            if status.get(status_key) != 'completed': raise ValueError(str(directory)+' must be completed')
            self.status = status
        self.manifest = _json(sources.read(self.directory/'manifest.json'))
        if manifest_key:
            key, expected = manifest_key
            if self.manifest.get(key) != expected: raise ValueError(str(directory)+' manifest must be '+expected)
        entries = self.manifest['outputs']
        if isinstance(entries, dict): items = list(entries.items())
        elif isinstance(entries, list):
            items = [(e.get('file', Path(e.get('path','')).name), e) for e in entries]
        else: raise ValueError('Unsupported manifest outputs')
        self.outputs = {}
        for name, entry in items:
            if (not isinstance(name,str) or not name or Path(name).name != name or name in ('.','..')
                    or name in self.outputs or not isinstance(entry,dict)):
                raise ValueError('Invalid or duplicate manifest output')
            if not re.fullmatch('[a-f0-9]{64}', str(entry.get('sha256',''))): raise ValueError('Invalid manifest sha256')
            self.outputs[name] = entry

    def read(self, name):
        if name not in self.outputs: raise ValueError('Required manifest output missing: '+name)
        return self.sources.read(self.directory/name, self.outputs[name])

    def json(self, name): return _json(self.read(name))

    def rows(self, name, required):
        reader = csv.DictReader(io.StringIO(self.read(name).decode('utf-8-sig')), strict=True)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)) or not set(required).issubset(fields): raise ValueError('Missing/duplicate CSV fields: '+name)
        rows = list(reader)
        if any(None in r or None in r.values() for r in rows): raise ValueError('Invalid CSV width: '+name)
        return rows


def interval_mask(timestamps, windows, *, closed=False):
    """Mask exact point labels; cyclone endpoints closed, heat/STOP right-open."""
    stamps = np.asarray(timestamps)
    result = np.zeros(stamps.shape, dtype=bool)
    for start, end in windows:
        if type(start) is not int or type(end) is not int or end < start or (not closed and end == start):
            raise ValueError('Invalid interval')
        result |= (stamps >= start) & ((stamps <= end) if closed else (stamps < end))
    return result


def masks(stamps, heat, stop, cyclone, known):
    bits = np.zeros(np.asarray(stamps).shape, dtype=np.uint8)
    bits[interval_mask(stamps, heat)] |= 1
    bits[interval_mask(stamps, stop)] |= 2
    conservative = interval_mask(stamps, cyclone, closed=True)
    known_mask = interval_mask(stamps, known, closed=True)
    if np.any(known_mask & ~conservative): raise ValueError('Known cyclone windows exceed conservative windows')
    bits[conservative] |= 4
    bits[conservative & ~known_mask] |= 8
    bits[(stamps < CYCLONE_COMPLETE_START) | (stamps >= CYCLONE_COMPLETE_END)] |= 16
    return bits


def all_year_heat_windows(stage, catalogue):
    """Use daily labels to retain 2021 heat processes whose recovery enters 2022.

    The exported analysis-event table omits processes ending before 2022, while
    the daily labels retain the 2021 context. Streaming avoids materializing all
    daily weather columns as hundreds of thousands of Python dictionaries.
    """
    data=stage.read('daily_heat_flags.csv.gz')
    grouped={}
    with io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(data)),encoding='utf-8-sig') as stream:
        reader=csv.DictReader(stream,strict=True)
        fields=reader.fieldnames or []
        if len(fields)!=len(set(fields)) or not {'country_id','date','analysis_event_id'}<=set(fields):
            raise ValueError('Daily heat labels missing required columns')
        for row in reader:
            if None in row or None in row.values():raise ValueError('Malformed daily heat row')
            label=row['analysis_event_id']
            if not label:continue
            stamp=archive.utc(row['date']+'T00:00:00Z')
            key=row['country_id'],label
            if key not in grouped:grouped[key]=set()
            if stamp in grouped[key]:raise ValueError('Duplicate daily heat date/label')
            grouped[key].add(stamp)
    windows=defaultdict(list);bounds={}
    for key,days in grouped.items():
        start,stop=min(days),max(days)+86400
        if len(days)*86400 != stop-start:raise ValueError('Noncontiguous daily heat event label')
        bounds[key]=(start,stop)
        windows[key[0]].append((start,stop+72*3600))
    expected={(r['country_id'],r['event_id']) for r in catalogue}
    for row in catalogue:
        start,end,_=_event_bounds(row)
        if bounds.get((row['country_id'],row['event_id']))!=(start,end):
            raise ValueError('Daily heat labels disagree with event catalogue')
    for key,(start,end) in bounds.items():
        if key not in expected and end>archive.ANALYSIS_START:
            raise ValueError('Daily heat event missing from all-year catalogue')
    return windows,len(grouped)


def annual_table(rows):
    result = {}
    for row in rows:
        key = row['country_id'], row['signal'], int(row['year'])
        if key in result or not re.fullmatch('[A-Z]{2}',key[0]) or key[1] not in archive.SIGNALS or key[2] not in range(2022,2026):
            raise ValueError('Invalid/duplicate annual coverage key')
        expected, valid = int(row['expected_points']), int(row['valid_points'])
        full = (366 if calendar.isleap(key[2]) else 365)*86400//archive.SIGNALS[key[1]]
        passed = 5*valid >= 4*expected
        if expected != full or not 0 <= valid <= expected or archive.boolean(row['candidate_80pct']) != passed:
            raise ValueError('Annual gate disagrees with native full-calendar coverage')
        result[key] = passed
    return result


def annual_mask(stamps, iso2, signal, annual):
    result = np.zeros(np.asarray(stamps).shape,dtype=bool)
    for year in range(2022,2026):
        if annual.get((iso2,signal,year),False):
            result |= (stamps >= archive.BOUNDS[f'{year}Q1'][0]) & (stamps < archive.BOUNDS[f'{year}Q4'][1])
    return result


def _event_bounds(row):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',row['start_date']): raise ValueError('Invalid event date')
    start,end=archive.utc(row['start_date']+'T00:00:00Z'),archive.utc(row['end_exclusive_utc'])
    if end <= start: raise ValueError('Invalid event bounds')
    return start,end,end+72*3600


def load_signal(stage, signal, countries, progress):
    times=np.arange(archive.ANALYSIS_START,archive.ANALYSIS_END,600,dtype=np.int64)
    matrix=np.full((len(countries),len(times)),np.nan,dtype=np.float64)
    phase_history={}
    for quarter in archive.QUARTERS:
        name=f'ioda_{quarter}_{signal}.npz'
        stage.sources.verify(stage.directory/name,stage.outputs[name])
        values,index,phases=archive.load_archive(stage.directory,quarter,signal)
        # Validate observed phases for every country in consumed archives, not
        # merely selected countries; fail instead of aligning/jitter-correcting.
        for country, idx in index.items():
            phase=int(phases[idx])
            if phase >= 0 and np.isfinite(values[idx]).any():
                if country in phase_history and phase_history[country] != phase:
                    raise ValueError('Inconsistent observed native phase: '+country+'/'+signal)
                phase_history[country]=phase
        begin=(archive.BOUNDS[quarter][0]-archive.ANALYSIS_START)//600
        for i,country in enumerate(countries):
            if country in index:matrix[i,begin:begin+values.shape[1]]=values[index[country]]
        del values
        stage.sources.check()
        progress(stage='load_signal',signal=signal,quarter=quarter)
    return times,matrix,phase_history


def run(*, preflight, candidate, connection, quality, heat, stop, cyclone,
        output, cyclone_radius, cyclone_hours, countries=None, signals=None):
    from . import cyclone_baseline_sensitivity as scenario
    scenario.select_windows([], '', cyclone_radius, cyclone_hours)
    output=Path(output).absolute()
    directories={k:Path(v).absolute() for k,v in dict(preflight=preflight,candidate=candidate,connection=connection,
                 quality=quality,heat=heat,stop=stop,cyclone=cyclone).items()}
    if any(output.resolve()==p.resolve() or output.resolve() in p.resolve().parents or p.resolve() in output.resolve().parents for p in directories.values()):
        raise ValueError('Input/output overlap')
    output.mkdir(parents=True,exist_ok=False)
    def publish(name,value):archive.atomic(output/name,archive.json_data(value))
    def progress(**state):publish('status.json',dict(status='running',pid=os.getpid(),**state))
    progress(stage='verify_metadata')
    try:
        sources=Sources()
        for path in [Path(__file__),Path(core.__file__),Path(archive.__file__),Path(scenario.__file__),Path(scenario.primary.__file__)]:sources.verify(path)
        stages={}
        for key in ['preflight','candidate','stop','cyclone']:
            stages[key]=Stage(directories[key],sources,status_key='state' if key=='cyclone' else 'status')
        for key,state in [('connection','complete'),('heat','complete'),('quality','completed')]:
            stages[key]=Stage(directories[key],sources,manifest_key=('state',state))
        if stages['quality'].json('summary.json').get('quality_pass') is not True:raise ValueError('Quality stage must pass')
        cs=stages['connection']
        expected={f'ioda_{q}_{s}.npz' for q in archive.QUARTERS for s in archive.SIGNALS}
        if cs.manifest.get('quarters')!=archive.QUARTERS or {n for n in cs.outputs if n.endswith('.npz')}!=expected:
            raise ValueError('Connection manifest must contain exactly 48 quarterly signal archives')
        cross=stages['preflight'].rows('joint_crosswalk.csv',['ioda_iso2','joint_country_id','joint_status'])
        archive.unique(cross,['ioda_iso2'])
        exact=[r for r in cross if r['joint_status']=='exact_joint_match']
        archive.unique(exact,['joint_country_id'])
        mapping={r['joint_country_id']:r['ioda_iso2'] for r in exact}
        if not mapping or any(not re.fullmatch('[A-Z]{3}',c) or not re.fullmatch('[A-Z]{2}',s) for c,s in mapping.items()):
            raise ValueError('Invalid exact country mapping')
        selected=sorted(mapping) if countries is None else list(countries)
        signals=list(archive.SIGNALS) if signals is None else list(signals)
        if not selected or len(set(selected))!=len(selected) or not set(selected)<=set(mapping):raise ValueError('Invalid country selection')
        if not signals or len(set(signals))!=len(signals) or not set(signals)<=set(archive.SIGNALS):raise ValueError('Invalid signal selection')
        routes=stages['candidate'].rows('event_routing.csv',archive.EVENT_FIELDS+['route','ioda_iso2'])
        archive.unique(routes,['event_id'])
        for row in routes:
            if row['route'] not in ('forward','held_stop_review','unmatched_country','not_weather_candidate'):raise ValueError('Unknown routing status')
            archive.event_bounds(row)
            if row['route'] in ('forward','held_stop_review'):
                if mapping.get(row['country_id']) != row['ioda_iso2'] or not archive.boolean(row['weather_candidate']):
                    raise ValueError('Routing disagrees with exact crosswalk/weather candidate')
        for name,route in [('forward_candidates.csv','forward'),('held_stop_review.csv','held_stop_review')]:
            rows=stages['candidate'].rows(name,['event_id','route'])
            expected_rows=[r for r in routes if r['route']==route]
            if rows!=expected_rows:raise ValueError('Candidate routing subset mismatch: '+name)
        catalogue=stages['heat'].rows('analysis_events.csv',['event_id','country_id','start_date','end_exclusive_utc'])
        archive.unique(catalogue,['event_id'])
        catalog_index={r['event_id']:r for r in catalogue}
        if set(catalog_index)!={r['event_id'] for r in routes}:raise ValueError('Full all-year catalogue differs from candidate routing')
        for row in routes:
            original=catalog_index[row['event_id']]
            if any(row[k]!=original[k] for k in ('country_id','start_date','end_exclusive_utc')):raise ValueError('Event catalogue bounds changed')
        heat_windows,heat_with_context_count=all_year_heat_windows(stages['heat'],catalogue)
        annual=annual_table(stages['quality'].rows('coverage_annual.csv',['country_id','signal','year','expected_points','valid_points','candidate_80pct']))
        stop_records=stages['stop'].json('stop_windows.json')['records']
        stop_windows=defaultdict(list);stop_unresolved=Counter();stop_unknown_end=Counter()
        stop_ids=set()
        for row in stop_records:
            if row['source_row'] in stop_ids:raise ValueError('Duplicate STOP source row')
            stop_ids.add(row['source_row'])
            if row['windows']:
                if row['country_id'] not in mapping or row['reasons'] or row['national_outage_inferred'] is not False:raise ValueError('Invalid STOP candidate window')
                window=row['windows']['main']
                interval_mask(np.array([],dtype=np.int64),[window])
                stop_windows[row['country_id']].append(tuple(window))
                stop_unknown_end[row['country_id']]+=int(row['end_unknown'])
            else:stop_unresolved[row['country_id']]+=1
        cyclone_stage=stages['cyclone']
        provenance=cyclone_stage.json('provenance.json')
        if provenance['rules'].get('closed_utc_windows') is not True:raise ValueError('Cyclone windows must be explicitly closed')
        if not set(selected)<=set(cyclone_stage.status['completed_countries']) or not set(selected)<=set(provenance['selected_ids']):
            raise ValueError('Selected cyclone countries not completed')
        cyclone_windows={};known_windows={}
        for country in selected:
            data=cyclone_stage.json(country+'.json')
            if data['country']!=country:raise ValueError('Cyclone country mismatch')
            conservative,known=scenario.select_windows(data['windows'],country,cyclone_radius,cyclone_hours)
            cyclone_windows[country],known_windows[country]=conservative,known
        chosen=[r for r in routes if r['route']=='forward' and r['country_id'] in selected]
        grouped=defaultdict(list)
        for index,row in enumerate(chosen):grouped[row['country_id']].append((index,row))
        products={};audits=[];phases={}
        for signal in signals:
            times,matrix,history=load_signal(cs,signal,[mapping[c] for c in selected],progress)
            phases[signal]=history
            for ci,country in enumerate(selected):
                windows=(heat_windows[country],stop_windows[country],cyclone_windows[country],known_windows[country])
                source_bits=scenario.masks(times,*windows,cyclone_hours)
                source_annual=annual_mask(times,mapping[country],signal,annual)
                for index,row in grouped[country]:
                    start,end,full=_event_bounds(row)
                    targets=np.arange(start,full,600,dtype=np.int64)
                    result=core.retrospective_baseline(times,matrix[ci],reference_excluded=source_bits!=0,
                                                      annual_eligible=source_annual,target_timestamps=targets)
                    queries=targets[:,None]+np.array(core.RETROSPECTIVE_OFFSETS_DAYS)[None,:]*86400
                    target_bits=scenario.masks(targets,*windows,cyclone_hours)
                    reference_bits=scenario.masks(queries,*windows,cyclone_hours)
                    unconfounded=result['analysis_available'] & ((target_bits&22)==0)
                    arrays={k:v for k,v in result.items() if isinstance(v,np.ndarray)}
                    arrays.update(event_id=np.array(row['event_id']),country_id=np.array(country),signal=np.array(signal),
                                  core_mask=targets<end,target_exclusion_bits=target_bits,
                                  reference_exclusion_bits=reference_bits,
                                  target_mask_coverage_complete=(target_bits&16)==0,
                                  target_analysis_unconfounded=unconfounded,
                                  reference_annual_eligible=annual_mask(queries,mapping[country],signal,annual),
                                  reference_present=(queries>=times[0])&(queries<=times[-1]))
                    name=f'points_{index:06d}_{signal}.npz'
                    temporary=output/('.'+name)
                    with temporary.open('wb') as stream:np.savez_compressed(stream,**arrays)
                    os.replace(temporary,output/name)
                    products[name]=archive.fingerprint(output/name)
                    confound=(target_bits&6)!=0
                    audits.append(dict(event_id=row['event_id'],country_id=country,ioda_iso2=mapping[country],signal=signal,
                        point_file=name,expected_full_slots=len(targets),target_valid_slots=int(result['target_valid'].sum()),
                        baseline_available_slots=int(result['baseline_available'].sum()),analysis_available_slots=int(result['analysis_available'].sum()),
                        full_target_and_baseline=bool(result['analysis_available'].all()),target_stop_or_cyclone_slots=int(confound.sum()),
                        target_cyclone_uncertain_slots=int(np.count_nonzero(target_bits&8)),
                        target_mask_coverage_unknown_slots=int(np.count_nonzero(target_bits&16)),
                        unresolved_stop_country_records=stop_unresolved[country],unknown_end_stop_country_records=stop_unknown_end[country],
                        full_observed_unconfounded=bool(unconfounded.all()),
                        final_sample_eligible=False))
                    progress(stage='compute_baseline',signal=signal,country=country,processed_signal_windows=len(audits))
            del matrix
        for name in ('event_routing.csv','held_stop_review.csv'):
            archive.atomic(output/name,stages['candidate'].read(name));products[name]=archive.fingerprint(output/name)
        audit_fields=list(audits[0]) if audits else ['event_id','country_id','signal','point_file','final_sample_eligible']
        archive.write_csv(output/'event_baseline_audit.csv',audit_fields,audits)
        products['event_baseline_audit.csv']=archive.fingerprint(output/'event_baseline_audit.csv')
        summary=dict(status='completed',selection='existing_forward_only_conservative_selection_held_not_released',
            cyclone_radius_km=cyclone_radius,cyclone_half_width_hours=cyclone_hours,
            cyclone_complete_bounds=list(scenario.coverage_bounds(cyclone_hours)),
            route_counts=dict(Counter(r['route'] for r in routes)),exact_country_count=len(mapping),selected_countries=selected,
            selected_signals=signals,selected_events=len(chosen),signal_windows=len(audits),all_year_heat_events=len(catalogue),
            heat_processes_including_2021_context=heat_with_context_count,
            full_target_and_baseline_by_signal={s:sum(r['full_target_and_baseline'] for r in audits if r['signal']==s) for s in signals},
            mask_bits=MASK_BITS,reference_rule='exact +/-7/14/21/28 UTC days; >=4 valid references, both sides, positive median; zero valid',
            native_phase_history=phases,annual_rule='source and target own calendar year; missing/failed annual record false; >=80% native coverage',
            missing_annual_keys=[dict(country_id=c,ioda_iso2=mapping[c],signal=s,year=y) for c in selected for s in signals for y in range(2022,2026) if (mapping[c],s,y) not in annual],
            confirmed_measurement_anomaly_exclusions=0,measurement_anomaly_policy='No confirmed anomaly evidence supplied; candidate anomalies not excluded in primary baseline',
            stop_policy='Finite possible-confound windows only; local/service scope does not infer national outage; unresolved uncertainty retained',
            stop_unresolved_by_country=dict(stop_unresolved),cyclone_policy=f'{cyclone_radius}km +/-{cyclone_hours}h closed windows, conservative includes unknown edges; bit8 is conservative-minus-known at each slot',
            cyclone_calendar_coverage_policy='Documented 2018-2025 calendar eroded by selected half width on both ends; outside buffer unavailable, not inferred storm-free.',
            reference_time_semantics='UTC 600-second interval labels, not asserted exact native measurement instants',
            baseline_computed=True,past_only_sensitivity_computed=False,dhrd_computed=False,final_sample_eligible=False)
        publish('summary.json',summary);products['summary.json']=archive.fingerprint(output/'summary.json')
        sources.check()
        publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products,
                                    numpy_version=np.__version__,scope='Only consumed selected-signal archives/country windows hashed; all metadata manifests retained'))
        publish('status.json',dict(status='completed',pid=os.getpid()))
        return summary
    except BaseException as exc:
        publish('status.json',dict(status='failed',pid=os.getpid(),error=str(exc)))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('preflight','candidate','connection','quality','heat','stop','cyclone','output'):parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--countries',nargs='+');parser.add_argument('--signals',nargs='+',choices=list(archive.SIGNALS))
    parser.add_argument('--cyclone-radius',type=int,required=True,choices=[100,300,500])
    parser.add_argument('--cyclone-hours',type=int,required=True,choices=[24,72])
    args=parser.parse_args()
    print(json.dumps(run(**vars(args)),sort_keys=True))
