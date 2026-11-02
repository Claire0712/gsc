"""Quarter-streamed candidate diagnostics. No automatic exclusions or baseline."""
import argparse
import calendar
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import time
import numpy as np
try:
    from .synchronous_screen import annual_mask, align_previous_day, paired_counts, candidate_flags
except ImportError:
    from synchronous_screen import annual_mask, align_previous_day, paired_counts, candidate_flags

SIGNALS = ['ping-slash24', 'bgp', 'merit-nt']
QUARTERS = [f'{y}Q{q}' for y in range(2022, 2026) for q in range(1, 5)]


def run(connection, quality, cross, output, quarters):
    connection, quality, cross, output = map(Path, [connection, quality, cross, output])
    quarters = list(quarters)
    indices = [QUARTERS.index(q) for q in quarters]
    if not indices or indices != list(range(indices[0], indices[-1] + 1)):
        raise ValueError('Quarters must be nonempty, unique and contiguous')
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    sources = {}
    stats = {}

    def publish(name, value):
        temporary = output / ('.' + name)
        temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
        os.replace(temporary, output / name)

    def read(path):
        path = Path(path)
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        stamp = lambda s: (s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if stamp(before) != stamp(after):
            raise ValueError(f'Input changed: {path}')
        stats[path] = stamp(after)
        sources[str(path)] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        return data

    def manifest(folder):
        m = json.loads(read(folder / 'manifest.json'))['outputs']
        if isinstance(m, list):
            if len({r['file'] for r in m}) != len(m): raise ValueError('Duplicate manifest paths')
            m = {r['file']: r for r in m}
        return m

    def verified(folder, name, entries):
        data = read(folder / name)
        meta = entries[name]
        if any(sources[str(folder/name)][k] != meta[k] for k in ['bytes', 'sha256']):
            raise ValueError(f'Hash/size mismatch: {name}')
        return data

    def rows(data):
        reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError('Invalid CSV fields')
        result = list(reader)
        if any(None in row or None in row.values() for row in result): raise ValueError('Invalid CSV width')
        return result

    publish('status.json', dict(status='running', pid=os.getpid(), quarters=quarters))
    try:
        for path in [Path(__file__), Path(__file__).with_name('synchronous_screen.py')]: read(path)
        if json.loads(read(connection/'status.json')).get('state') != 'complete': raise ValueError('Incomplete panel')
        if json.loads(read(cross/'status.json')).get('status') != 'completed': raise ValueError('Incomplete crosswalk')
        if json.loads(read(quality/'summary.json')).get('quality_pass') is not True: raise ValueError('Failed quality gate')
        cm, qm, xm = manifest(connection), manifest(quality), manifest(cross)
        annual = {s: {} for s in SIGNALS}
        for row in rows(verified(quality, 'coverage_annual.csv', qm)):
            signal = row['signal']; year = int(row['year']); country = row['country_id']
            valid, expected = int(row['valid_points']), int(row['expected_points'])
            theoretical = (366 if calendar.isleap(year) else 365) * (144 if signal == 'ping-slash24' else 288)
            key = (country, year)
            if signal not in annual or key in annual[signal] or expected != theoretical or not 0 <= valid <= expected:
                raise ValueError('Invalid/duplicate annual row')
            annual[signal][key] = (valid, expected)
        crossrows = rows(verified(cross, 'joint_crosswalk.csv', xm))
        all_ids = [r['ioda_iso2'] for r in crossrows]
        exact = [r for r in crossrows if r['joint_status'] == 'exact_joint_match']
        joint = {r['ioda_iso2'] for r in exact}
        if len(all_ids) != len(set(all_ids)) or len({r['joint_country_id'] for r in exact}) != len(exact) or not joint:
            raise ValueError('Nonunique/empty mapping')
        screens = []
        for signal in SIGNALS:
            chunks = {u: [] for u in ['joint', 'all']}
            times_all = []; tail_t = None; tail_v = None; ids = None; prior_phases = None
            for quarter in quarters:
                name = f'ioda_{quarter}_{signal}.npz'
                with np.load(io.BytesIO(verified(connection, name, cm)), allow_pickle=False) as a:
                    t, values, countries, phases = [a[k] for k in ['interval_start_utc', 'values', 'country_ids', 'native_phase_seconds']]
                countries = countries.astype(str)
                year, q = int(quarter[:4]), int(quarter[-1]); month = 3*q-2
                start = int(np.datetime64(f'{year}-{month:02d}-01', 's').astype(int))
                end = int(np.datetime64(f'{year+1}-01-01' if q==4 else f'{year}-{month+3:02d}-01', 's').astype(int))
                if t.dtype != np.dtype('int64') or not np.array_equal(t, np.arange(start,end,600)):
                    raise ValueError('Invalid quarterly time grid')
                if values.dtype != np.dtype('float64') or values.shape != (len(countries),len(t)):
                    raise ValueError('Invalid panel dimensions/type')
                if set(countries) != set(all_ids) or len(countries) != len(all_ids) or np.isinf(values).any() or (values<0).any():
                    raise ValueError('Invalid panel entities/values')
                if phases.shape != countries.shape or phases.dtype.kind not in 'iu' or np.any((phases < -1) | (phases >= (600 if signal=='ping-slash24' else 300))):
                    raise ValueError('Invalid native phases')
                if ids is not None and not np.array_equal(ids,countries): raise ValueError('Country order changed')
                if prior_phases is not None and np.any((phases>=0)&(prior_phases>=0)&(phases!=prior_phases)):
                    raise ValueError('Native phases changed')
                ids=countries; prior_phases=phases
                v=values.T
                tt=t if tail_t is None else np.concatenate([tail_t,t])
                vv=v if tail_v is None else np.concatenate([tail_v,v])
                offset=len(tt)-len(t)
                for universe in chunks:
                    select=np.array([c in joint for c in ids]) if universe=='joint' else np.ones(len(ids),dtype=bool)
                    selected=ids[select]; data=vv[:,select]
                    eligible=annual_mask(tt,selected,annual[signal],set(selected))
                    previous, paired, found=align_previous_day(tt,data,eligible)
                    counts=paired_counts(data,previous,paired)
                    # A missing predecessor time is separate from annual ineligibility.
                    counts['annual_ineligible'][~found]=0
                    counts['previous_time_missing']=~found
                    chunks[universe].append({k:x[offset:].copy() for k,x in counts.items()})
                times_all.append(t); tail_t=t[-144:].copy(); tail_v=v[-144:].copy()
                publish('status.json',dict(status='running',pid=os.getpid(),signal=signal,quarter=quarter,elapsed_seconds=time.monotonic()-started))
            timestamps=np.concatenate(times_all)
            for universe, pieces in chunks.items():
                arrays={k:np.concatenate([piece[k] for piece in pieces]) for k in pieces[0]}
                threshold, flags=candidate_flags(arrays['fraction'])
                arrays.update(interval_start_utc=timestamps,candidate=flags)
                name=f'{signal}_{universe}.npz'
                np.savez_compressed(output/name,**arrays)
                indices=np.flatnonzero(flags); intervals=[]
                for index in indices:
                    stamp=int(timestamps[index])
                    if intervals and intervals[-1]['end_exclusive_utc']==stamp: intervals[-1]['end_exclusive_utc']=stamp+600
                    else: intervals.append(dict(start_utc=stamp,end_exclusive_utc=stamp+600))
                screens.append(dict(signal=signal,universe=universe,slots=len(timestamps),valid_ratios=int(np.isfinite(arrays['fraction']).sum()),candidate_slots=int(flags.sum()),threshold=threshold if np.isfinite(threshold) else None,intervals=intervals,file=name))
        for path, stamp in stats.items():
            s=path.stat()
            if (s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)!=stamp: raise ValueError('Input changed before publication')
        result=dict(full_period=quarters==QUARTERS,quarters=quarters,screens=screens,exclusions_generated=False,baseline_computed=False,elapsed_seconds=time.monotonic()-started,sources=sources)
        publish('summary.json',result)
        files={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in output.iterdir() if p.suffix=='.npz' or p.name=='summary.json'}
        publish('manifest.json',dict(outputs=files))
        publish('status.json',dict(status='completed',pid=os.getpid(),full_period=result['full_period'],elapsed_seconds=result['elapsed_seconds']))
        return result
    except BaseException as error:
        publish('status.json',dict(status='failed',pid=os.getpid(),error=str(error)))
        raise


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    for name in ['connection','quality','cross','output']: p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--quarters',nargs='+',default=QUARTERS)
    a=p.parse_args()
    result=run(a.connection,a.quality,a.cross,a.output,a.quarters)
    print(json.dumps({k:v for k,v in result.items() if k not in ['sources','screens']}))
