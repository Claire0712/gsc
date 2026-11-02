"""Single-worker full-track cyclone screen. Fresh outputs; no inferred country joins."""
import argparse
import csv
import hashlib
import json
import math
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from .cyclone_distance import BoundaryIndex
    from .cyclone_screen_core import merge_point_windows, candidate_boxes
except ImportError:
    from cyclone_distance import BoundaryIndex
    from cyclone_screen_core import merge_point_windows, candidate_boxes


def clean_tracks(rows):
    groups = defaultdict(list)
    audit = dict(input_rows=0, invalid_rows_excluded=0, conflict_rows_excluded=0,
                 duplicate_rows_removed=0, excluded=[])
    for number, row in enumerate(rows, 1):
        audit['input_rows'] += 1
        try:
            sid = row['normalized_sid'].strip()
            dt = datetime.fromisoformat(row['normalized_time_utc'].replace('Z', '+00:00'))
            lon, lat = float(row['normalized_longitude']), float(row['normalized_latitude'])
            if not sid or dt.utcoffset() is None or dt.utcoffset().total_seconds() != 0 or dt.microsecond or not math.isfinite(lon+lat) or not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise ValueError('Invalid normalized point')
            groups[(sid, int(dt.timestamp()))].append((lon, lat, row.get('conflicting_sid_time', '0'), number))
        except (ValueError, KeyError, TypeError):
            audit['invalid_rows_excluded'] += 1
            audit['excluded'].append(dict(csv_data_row=number, reason='invalid_normalized_point'))
    points = []
    for (sid, stamp), values in sorted(groups.items()):
        if len({v[:2] for v in values}) > 1 or any(v[2] != '0' for v in values):
            audit['conflict_rows_excluded'] += len(values)
            audit['excluded'].extend(dict(csv_data_row=v[3], reason='conflicting_sid_time', sid=sid, time=stamp) for v in values)
            continue
        audit['duplicate_rows_removed'] += len(values)-1
        points.append(dict(sid=sid, time=stamp, lon=values[0][0], lat=values[0][1]))
    audit['valid_unique_points'] = len(points)
    assert audit['input_rows'] == sum(audit[k] for k in ['invalid_rows_excluded', 'conflict_rows_excluded', 'duplicate_rows_removed', 'valid_unique_points'])
    return points, audit


def screen_country(country, geometry, points, candidate_indices=None):
    index = BoundaryIndex(geometry)
    counts = {str(r): dict(hit=0, unknown=0, false=len(points)) for r in (100, 300, 500)}
    selected = []
    groups = defaultdict(list)
    for k in (range(len(points)) if candidate_indices is None else candidate_indices):
        point = points[k]
        answer = index.classify(point['lon'], point['lat'])
        if all(flag is False for flag in answer['within']):
            continue
        selected.append(dict(**point, **answer))
        for radius, flag in zip((100, 300, 500), answer['within']):
            if flag is False:
                continue
            counts[str(radius)]['false'] -= 1
            counts[str(radius)]['hit' if flag else 'unknown'] += 1
            groups[(point['sid'], radius, 'conservative')].append(point['time'])
            if flag is True:
                groups[(point['sid'], radius, 'known')].append(point['time'])
    windows = []
    for (sid, radius, mode), times in sorted(groups.items()):
        for hours in (24, 72):
            for start, end in merge_point_windows(times, hours*3600):
                windows.append(dict(country=country, sid=sid, radius_km=radius, half_width_hours=hours,
                                    mode=mode, start_utc_seconds=start, end_utc_seconds=end))
    return dict(country=country, counts=counts, points=selected, windows=windows,
                roundoff_coordinates=index.roundoff_coordinates)


def fingerprint(path):
    path = Path(path)
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f'Input changed while hashing: {path}')
    return dict(path=str(path.resolve()), size_bytes=after.st_size, mtime_ns=after.st_mtime_ns, sha256=h.hexdigest())


def verify(path, entry):
    actual = fingerprint(path)
    if actual['sha256'] != entry['sha256'] or actual['size_bytes'] != entry.get('size_bytes', entry.get('bytes')):
        raise ValueError(f'Provenance mismatch: {path}')
    return actual


def atomic_json(path, value):
    tmp = path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w') as stream:
        json.dump(value, stream, allow_nan=False)
    tmp.replace(path)


def run(root, output, countries=None):
    import geopandas as gpd
    from shapely import STRtree
    from shapely.geometry import box
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    status = dict(state='running', pid=os.getpid(), completed_countries=[], current_country=None, started_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(output/'status.json', status)
    started = time.monotonic()
    try:
        auxiliary = root/'analysis/2026-10-07_parallel_prep/auxiliary'
        boundary = root/'data/boundaries/geoBoundariesCGAZ_ADM0.gpkg'
        aux_manifest = auxiliary/'manifest.json'
        boundary_manifest = root/'data/metadata/ancillary_file_checksums.json'
        sources = [fingerprint(aux_manifest), fingerprint(boundary_manifest)]
        aux = json.loads(aux_manifest.read_text())
        if aux['state'] != 'complete':
            raise ValueError('Auxiliary stage incomplete')
        sources.append(verify(auxiliary/'ibtracs_cleaned.csv', aux['outputs']['ibtracs_cleaned.csv']))
        entries = [e for e in json.loads(boundary_manifest.read_text())['files'] if e['file'] == 'boundaries/geoBoundariesCGAZ_ADM0.gpkg']
        if len(entries) != 1:
            raise ValueError('Unique boundary manifest entry required')
        sources.append(verify(boundary, entries[0]))
        sources.extend(fingerprint(Path(__file__).with_name(name)) for name in ('run_cyclone_screen.py', 'cyclone_distance.py', 'cyclone_screen_core.py'))
        with (auxiliary/'ibtracs_cleaned.csv').open() as stream:
            points, audit = clean_tracks(csv.DictReader(stream))
        atomic_json(output/'track_audit.json', audit)
        frame = gpd.read_file(boundary)
        if frame.crs.to_epsg() != 4326 or frame.shapeGroup.isna().any() or frame.shapeGroup.duplicated().any():
            raise ValueError('Unique explicit EPSG4326 boundary IDs required')
        ids = sorted(frame.shapeGroup.tolist())
        chosen = ids if countries is None else countries
        if not chosen or len(set(chosen)) != len(chosen) or not set(chosen) <= set(ids):
            raise ValueError('Invalid country selection')
        # A polygon within 500km must intersect the point cap envelope. Query
        # polygon envelopes only to prune; BoundaryIndex makes every final decision.
        boxes, owners = [], []
        for k, point in enumerate(points):
            for bounds in candidate_boxes(point['lon'], point['lat'], 500001):
                boxes.append(box(*bounds)); owners.append(k)
        tree = STRtree(boxes)
        atomic_json(output/'provenance.json', dict(sources=sources, all_boundary_ids=ids, selected_ids=chosen,
                    rules=dict(thresholds_km=[100,300,500], half_width_hours=[24,72], closed_utc_windows=True,
                    conflicts='exclude entire SID/time group', duplicates='collapse identical normalized coordinates',
                    missing_wind='retained', unknown='conservative included, known-only sensitivity')))
        summaries = []
        for country in chosen:
            status['current_country'] = country
            atomic_json(output/'status.json', status)
            geom = frame.loc[frame.shapeGroup == country, 'geometry'].iloc[0]
            candidates = sorted({owners[int(i)] for i in tree.query(geom.envelope)})
            begin = time.monotonic()
            result = screen_country(country, geom, points, candidates)
            result['elapsed_seconds'] = time.monotonic()-begin
            result['candidate_points'] = len(candidates)
            atomic_json(output/f'{country}.json', result)
            summaries.append({k:v for k,v in result.items() if k not in ('points','windows')})
            status['completed_countries'].append(country)
            status['elapsed_seconds'] = time.monotonic()-started
            atomic_json(output/'status.json', status)
            print(json.dumps(summaries[-1]), flush=True)
        for entry in sources:
            if fingerprint(entry['path']) != entry:
                raise ValueError('Source changed during run')
        atomic_json(output/'summary.json', dict(countries=summaries, track_points=len(points), elapsed_seconds=time.monotonic()-started))
        products = [fingerprint(p) for p in sorted(output.glob('*.json')) if p.name != 'status.json']
        atomic_json(output/'manifest.json', dict(sources=sources, outputs=products))
        status.update(state='completed', current_country=None, elapsed_seconds=time.monotonic()-started)
    except Exception as exc:
        status.update(state='failed', error=repr(exc))
        raise
    finally:
        atomic_json(output/'status.json', status)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--countries', nargs='+')
    args = parser.parse_args()
    run(args.root, args.output, args.countries)
