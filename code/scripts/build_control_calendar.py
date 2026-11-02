#!/usr/bin/env python3
"""All forward-event nonheat calendar candidates, never matched/final controls."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import time

DAY = 86400
OFFSETS = (-42, -35, -28, -21, -14, -7, 7, 14, 21, 28, 35, 42)
USES = ('integral', 'matching', 'curve')


def utc(text):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T00:00:00(?:Z|\+00:00)',text):
        raise ValueError('UTC midnight calendar boundary required')
    return int(datetime.fromisoformat(text.replace('Z','+00:00')).timestamp())


def iso(stamp):
    return datetime.fromtimestamp(stamp,timezone.utc).isoformat().replace('+00:00','Z')


CALENDAR_START = utc('2022-01-01T00:00:00Z')
CALENDAR_END = utc('2026-01-01T00:00:00Z')


def bounds(event):
    start=utc(event['start_date']+'T00:00:00Z')
    end=utc(event['end_exclusive_utc'])
    if end<=start:raise ValueError('Event core must have positive integer-day length')
    return start,end


def calendar_rows(event, windows):
    start,end=bounds(event)
    for w in windows:
        if type(w['start']) is not int or type(w['end']) is not int or w['end']<=w['start']:
            raise ValueError('Invalid heat interval')
    rows=[]
    for offset in OFFSETS:
        control=start+offset*DAY
        stop=control+(end-start)
        intervals={'integral':(control,stop+3*DAY),'preperiod':(control-7*DAY,control),'curve':(control-7*DAY,control+8*DAY)}
        same_year=datetime.fromtimestamp(start,timezone.utc).year==datetime.fromtimestamp(control,timezone.utc).year
        row=dict(event_id=event['event_id'],country_id=event['country_id'],ioda_iso2=event.get('ioda_iso2',''),
                 control_id=f"{event['event_id']}__offset_{offset:+d}",offset_days=offset,
                 heat_start_utc=iso(start),heat_end_exclusive_utc=iso(end),core_days=(end-start)//DAY,
                 control_start_utc=iso(control),control_end_exclusive_utc=iso(stop),same_start_year=same_year)
        reasons={}
        for use,(a,b) in intervals.items():
            covered=CALENDAR_START<=a and b<=CALENDAR_END
            overlap=sorted({w['event_id'] for w in windows if a<w['end'] and w['start']<b})
            row.update({use+'_start_utc':iso(a),use+'_end_exclusive_utc':iso(b),
                        use+'_calendar_covered':covered,use+'_heat_overlap':bool(overlap),
                        use+'_heat_event_ids':json.dumps(overlap,separators=(',',':'))})
            reasons[use]=([] if covered else [use+'_outside_connection_calendar'])+([use+'_heat_overlap'] if overlap else [])
        integral=([] if same_year else ['different_start_year'])+reasons['integral']
        matching=integral+reasons['preperiod']
        curve=matching+reasons['curve']
        for use,reason in [('integral',integral),('matching',matching),('curve',curve)]:
            row[use+'_calendar_candidate']=not reason
            row[use+'_rejection_reasons']=json.dumps(reason,separators=(',',':'))
        row.update(final_sample_eligible=False,requires_signal_quality_screen=True,matched=False)
        rows.append(row)
    return rows


def heat_windows(daily_rows,catalogue):
    """All labelled days, including bridges/nonwarm events and 2021 context."""
    groups=defaultdict(set)
    for row in daily_rows:
        if not row['analysis_event_id']:continue
        key=row['country_id'],row['analysis_event_id']
        stamp=utc(row['date']+'T00:00:00Z')
        if stamp in groups[key]:raise ValueError('Duplicate labelled heat day')
        groups[key].add(stamp)
    actual={}
    windows=defaultdict(list)
    for key,days in groups.items():
        start,end=min(days),max(days)+DAY
        if len(days)*DAY!=end-start:raise ValueError('Noncontiguous heat catalogue label')
        actual[key]=(start,end)
        windows[key[0]].append(dict(event_id=key[1],start=start,end=end+3*DAY))
    expected=set()
    for row in catalogue:
        key=row['country_id'],row['event_id']
        if key in expected:raise ValueError('Duplicate heat catalogue event')
        expected.add(key)
        if actual.get(key)!=bounds(row):raise ValueError('Daily heat labels disagree with catalogue')
    if any(key not in expected and b>CALENDAR_START for key,(a,b) in actual.items()):
        raise ValueError('Daily heat label missing from catalogue')
    return windows


def strict_json(data):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('Duplicate JSON key')
            result[k]=v
        return result
    return json.loads(data,object_pairs_hook=pairs)


class Inputs:
    def __init__(self):self.hashes={};self.stamps={}

    @staticmethod
    def stamp(path):
        s=path.lstat()
        if not stat.S_ISREG(s.st_mode):raise ValueError('Input must be regular, not symlink')
        return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns

    def read(self,path,entry=None):
        path=Path(path);before=self.stamp(path)
        if path in self.stamps and before!=self.stamps[path]:raise ValueError('Input changed')
        data=path.read_bytes()
        if self.stamp(path)!=before:raise ValueError('Input changed during read')
        actual=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        if entry is not None:
            size=entry.get('bytes',entry.get('size_bytes'))
            if actual['sha256']!=entry.get('sha256') or (size is not None and size!=len(data)):
                raise ValueError('Input hash/size mismatch: '+str(path))
        self.hashes[str(path)]=actual;self.stamps[path]=before
        return data

    def check(self):
        for p,s in self.stamps.items():
            if self.stamp(p)!=s:raise ValueError('Input changed before publication')


def csv_rows(data,required):
    reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig')),strict=True)
    fields=reader.fieldnames or []
    if len(fields)!=len(set(fields)) or not set(required)<=set(fields):raise ValueError('CSV missing/duplicate fields')
    rows=list(reader)
    if any(None in r or None in r.values() for r in rows):raise ValueError('Malformed CSV width')
    return rows


def output_csv(path,rows,fields):
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=fields)
    writer.writeheader();writer.writerows(rows);atomic(path,stream.getvalue().encode())


def atomic(path,data):
    temp=path.with_name('.'+path.name)
    with temp.open('xb') as stream:stream.write(data)
    os.replace(temp,path)


def run(candidate,heat,output,countries=None):
    candidate,heat,output=map(lambda p:Path(p).absolute(),[candidate,heat,output])
    if any(output.resolve()==p.resolve() or output.resolve() in p.resolve().parents or p.resolve() in output.resolve().parents for p in (candidate,heat)):
        raise ValueError('Input/output overlap')
    output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();tracker=Inputs()
    def publish(name,obj):atomic(output/name,(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n').encode())
    publish('status.json',dict(status='running',pid=os.getpid(),started_utc=iso(int(time.time()))))
    try:
        tracker.read(Path(__file__))
        if strict_json(tracker.read(candidate/'status.json')).get('status')!='completed':raise ValueError('Candidate stage must be completed')
        cm=strict_json(tracker.read(candidate/'manifest.json'));hm=strict_json(tracker.read(heat/'manifest.json'))
        if cm.get('status')!='completed' or hm.get('state')!='complete':raise ValueError('Input manifests must be completed/complete')
        def read(folder,manifest,name):
            entries=manifest['outputs']
            if not isinstance(entries,dict) or name not in entries:raise ValueError('Required manifest output missing')
            return tracker.read(folder/name,entries[name])
        route_data=read(candidate,cm,'event_routing.csv')
        route=csv_rows(route_data,['event_id','country_id','ioda_iso2','route','start_date','end_exclusive_utc','weather_candidate'])
        index={r['event_id']:r for r in route}
        if len(index)!=len(route) or '' in index:raise ValueError('Duplicate/empty routing event')
        for row in route:
            bounds(row)
            if row['route'] not in ('forward','held_stop_review','not_weather_candidate','unmatched_country'):raise ValueError('Unknown routing state')
            if row['route']=='forward' and (row['weather_candidate'] not in ('True','1') or not re.fullmatch('[A-Z]{3}',row['country_id']) or not re.fullmatch('[A-Z]{2}',row['ioda_iso2'])):
                raise ValueError('Invalid forward routing')
        held_data=read(candidate,cm,'held_stop_review.csv')
        for name,state in [('forward_candidates.csv','forward'),('held_stop_review.csv','held_stop_review')]:
            data=held_data if state=='held_stop_review' else read(candidate,cm,name)
            if csv_rows(data,['event_id','route'])!=[r for r in route if r['route']==state]:raise ValueError('Candidate routing subset mismatch')
        catalogue=csv_rows(read(heat,hm,'analysis_events.csv'),['event_id','country_id','start_date','end_exclusive_utc'])
        if len(catalogue)!=len(route) or {r['event_id'] for r in catalogue}!=set(index):raise ValueError('All-year catalogue/routing event mismatch')
        for row in catalogue:
            if any(row[k]!=index[row['event_id']][k] for k in ('country_id','start_date','end_exclusive_utc')):raise ValueError('Catalogue bounds/routing mismatch')
        compressed=read(heat,hm,'daily_heat_flags.csv.gz')
        with io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(compressed)),encoding='utf-8-sig') as stream:
            reader=csv.DictReader(stream,strict=True)
            if not {'country_id','date','analysis_event_id'}<=set(reader.fieldnames or []):raise ValueError('Daily heat labels missing fields')
            windows=heat_windows(reader,catalogue)
        forward=[r for r in route if r['route']=='forward']
        known={r['country_id'] for r in forward}
        selected=sorted(known) if countries is None else list(countries)
        if not selected or len(selected)!=len(set(selected)) or not set(selected)<=known:raise ValueError('Invalid country selection or no forward events')
        chosen=[r for r in forward if r['country_id'] in selected]
        results=[];counts=[]
        for event in chosen:
            candidates=calendar_rows(event,windows[event['country_id']]);results.extend(candidates)
            counts.append(dict(event_id=event['event_id'],country_id=event['country_id'],candidate_rows=12,
                               **{use+'_candidate_count':sum(r[use+'_calendar_candidate'] for r in candidates) for use in USES}))
        assert len(results)==len(chosen)*12
        output_csv(output/'control_calendar.csv',results,list(results[0]))
        output_csv(output/'event_candidate_counts.csv',counts,list(counts[0]))
        atomic(output/'event_routing.csv',route_data);atomic(output/'held_stop_review.csv',held_data)
        summary=dict(status='completed',selected_countries=selected,forward_events_total=len(forward),selected_events=len(chosen),candidate_rows=len(results),offset_days=list(OFFSETS),
                     route_counts=dict(Counter(r['route'] for r in route)),all_year_heat_processes_including_context=sum(map(len,windows.values())),
                     candidate_counts={use:sum(r[use+'_calendar_candidate'] for r in results) for use in USES},
                     zero_candidate_events={use:sum(r[use+'_candidate_count']==0 for r in counts) for use in USES},
                     rejection_reason_counts={use:dict(Counter(reason for r in results for reason in json.loads(r[use+'_rejection_reasons']))) for use in USES},
                     usage_rules={'integral':'same start year; covered nonheat core+72h','matching':'integral plus covered nonheat previous7days','curve':'matching plus covered nonheat start[-7,+8)days'},
                     interpretation='Calendar candidates only; same-start-year and nonheat pre7days are frozen conservative choices. Tmin not screened. Original held routes remain held.',
                     next_stage_required=['annual native coverage','retrospective reference eligibility','STOP and cyclone including calendar edge coverage','signal completeness','preperiod covariates','frozen matching rule and common support'],
                     matched=False,final_sample_eligible=False,effect_estimated=False,elapsed_seconds=time.monotonic()-started)
        publish('summary.json',summary)
        products={}
        for name in ('control_calendar.csv','event_candidate_counts.csv','event_routing.csv','held_stop_review.csv','summary.json'):
            data=(output/name).read_bytes();products[name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        tracker.check()
        publish('manifest.json',dict(status='completed',inputs=tracker.hashes,outputs=products))
        publish('status.json',dict(status='completed',pid=os.getpid(),elapsed_seconds=summary['elapsed_seconds']))
        return summary
    except BaseException as exc:
        publish('status.json',dict(status='failed',pid=os.getpid(),error=str(exc)))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','heat','output'):parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--countries',nargs='+')
    args=parser.parse_args()
    print(json.dumps(run(**vars(args)),sort_keys=True))
