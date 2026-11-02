"""Finite STOP candidate windows, not inferred nationwide outages."""
from datetime import datetime, timezone, timedelta
import re
import argparse
import csv
import hashlib
import io
import json
import os
import time
from pathlib import Path
from collections import Counter


def classify_record(row, allowed_countries):
    record={k:row[k] for k in ['source_row','normalized_geo_scope','area_name','shutdown_extent','date_interval_status','qa_flags']}
    cid=row['matched_worldbank_iso3']
    record.update(country_id=cid,windows={},reasons=[],national_outage_inferred=False,scope_uncertain=row['normalized_geo_scope']=='unknown',end_unknown=not row['normalized_end_date'],source_timezone='unknown',interval_semantics='UTC_calendar_proxy_right_open')
    reasons=record['reasons']
    if row['country_match_status']!='exact_name_match' or cid not in allowed_countries:
        reasons.append('unmatched_joint_country')
    dates={}
    for label in ['start','end']:
        value=row[f'normalized_{label}_date']
        if not value:
            if label=='start': reasons.append('missing_start')
            dates[label]=None
        else:
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value): raise ValueError()
                dates[label]=datetime.strptime(value,'%Y-%m-%d').replace(tzinfo=timezone.utc)
            except ValueError:
                dates[label]=None; reasons.append('invalid_'+label)
        if f'{label}_date_invalid' in row['qa_flags']:
            reasons.append('upstream_invalid_'+label)
    start,end=dates['start'],dates['end']
    if row['date_interval_status']=='reversed' or (start and end and end<start): reasons.append('reversed_dates')
    if end and (row['date_interval_status']!='complete' or row['bounded_interval_eligible']!='1'):
        reasons.append('inconsistent_complete_status')
    if not row['normalized_end_date'] and (row['date_interval_status']!='incomplete' or row['bounded_interval_eligible']!='0'):
        reasons.append('inconsistent_missing_end_status')
    if reasons: return record
    if start is None: raise ValueError('Missing start was not classified')
    finish=(end or start)+timedelta(days=1)
    for name,days in [('main',0),('unknown_end_plusminus7',7),('unknown_end_plusminus30',30)]:
        expand=timedelta(days=days if end is None else 0)
        record['windows'][name]=[int((start-expand).timestamp()),int((finish+expand).timestamp())]
    return record


def run(auxiliary, crosswalk, output):
    auxiliary,crosswalk,output=map(Path,[auxiliary,crosswalk,output])
    output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic(); sources={}; stamps={}
    def publish(name,value):
        temp=output/('.'+name)
        temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        os.replace(temp,output/name)
    def read(path):
        before=path.stat(); b=path.read_bytes(); after=path.stat()
        stamp=lambda s:(s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if stamp(before)!=stamp(after): raise ValueError('Source changed during read')
        stamps[path]=stamp(after)
        sources[str(path)]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
        return b
    def verified_rows(folder,name):
        entries=json.loads(read(folder/'manifest.json'))['outputs']
        if isinstance(entries,list): entries={v['file']:v for v in entries}
        b=read(folder/name)
        expected=entries[name]
        actual=sources[str(folder/name)]
        if actual['bytes']!=expected.get('bytes',expected.get('size_bytes')) or actual['sha256']!=expected['sha256']:
            raise ValueError('Input hash/size mismatch: '+name)
        reader=csv.DictReader(io.StringIO(b.decode('utf-8-sig')))
        if not reader.fieldnames or len(reader.fieldnames)!=len(set(reader.fieldnames)): raise ValueError('Invalid header')
        rows=list(reader)
        if any(None in row or None in row.values() for row in rows): raise ValueError('Invalid CSV width')
        return rows
    publish('status.json',dict(status='running',pid=os.getpid()))
    try:
        read(Path(__file__))
        cross=verified_rows(crosswalk,'joint_crosswalk.csv')
        ids=[r['joint_country_id'] for r in cross if r['joint_status']=='exact_joint_match']
        if not ids or len(set(ids))!=len(ids) or '' in ids: raise ValueError('Invalid joint country IDs')
        rows=verified_rows(auxiliary,'stop_cleaned.csv')
        rowids=[r['source_row'] for r in rows]
        if len(set(rowids))!=len(rowids) or '' in rowids: raise ValueError('Invalid source row IDs')
        records=[classify_record(row,set(ids)) for row in rows]
        for path,expected in stamps.items():
            s=path.stat()
            if (s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)!=expected: raise ValueError('Source changed before publication')
        result=dict(status='completed',elapsed_seconds=time.monotonic()-started,sources=sources,counts=dict(records=len(records),with_windows=sum(bool(r['windows']) for r in records),unresolved=sum(not r['windows'] for r in records),unknown_end_with_windows=sum(r['end_unknown'] and bool(r['windows']) for r in records)),unresolved_reasons=dict(Counter(reason for r in records for reason in r['reasons'])),national_outage_inferred=False,baseline_computed=False)
        publish('stop_windows.json',dict(records=records))
        publish('summary.json',result)
        outputs={}
        for name in ['stop_windows.json','summary.json']:
            b=(output/name).read_bytes();outputs[name]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
        publish('manifest.json',dict(outputs=outputs))
        publish('status.json',dict(status='completed',pid=os.getpid(),elapsed_seconds=result['elapsed_seconds']))
        return result
    except BaseException as error:
        publish('status.json',dict(status='failed',pid=os.getpid(),error=str(error)))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['auxiliary','crosswalk','output']: parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    result=run(args.auxiliary,args.crosswalk,args.output)
    print(json.dumps({k:v for k,v in result.items() if k!='sources'}))
