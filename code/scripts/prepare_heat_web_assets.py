#!/usr/bin/env python3
"""Create display-only simplified geometry from existing research boundaries."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def sanitize_map(raw, expected_ids):
    features = []
    seen = set()
    for feature in raw['features']:
        props = feature['properties']
        code = str(props['shapeGroup'])
        if code not in expected_ids or code in seen:
            raise ValueError('Boundary country IDs do not uniquely match ERA5 weights')
        seen.add(code)
        features.append({'type': 'Feature', 'properties': {'country_id': code,
                         'country_name': str(props['shapeName'])}, 'geometry': feature['geometry']})
    if seen != expected_ids:
        raise ValueError('Missing geometry for ERA5 country IDs')
    return {'type': 'FeatureCollection', 'features': features}


def sha256(path):
    with path.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256')
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boundaries', type=Path, required=True)
    parser.add_argument('--country-metadata', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    import geopandas as gpd
    gdf = gpd.read_file(args.boundaries)
    if gdf.crs is None:
        raise ValueError('Boundary CRS is missing')
    gdf = gdf.to_crs('EPSG:4326')
    if gdf.geometry.is_empty.any() or (~gdf.geometry.is_valid).any():
        raise ValueError('Invalid source geometries')
    # Simplification is for display only, never used for exposure aggregation.
    gdf.geometry = gdf.geometry.simplify(0.12, preserve_topology=True)
    with args.country_metadata.open() as handle:
        ids = {r['country_id'] for r in csv.DictReader(handle)}
    result = sanitize_map(json.loads(gdf.to_json()), ids)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / 'map.geojson'
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    temp.replace(target)
    provenance = {'updated_utc': datetime.now(timezone.utc).isoformat(), 'country_count': len(ids),
                  'source_sha256': sha256(args.boundaries), 'map_sha256': sha256(target),
                  'simplification_degrees': 0.12, 'display_only': True,
                  'source': str(args.boundaries)}
    (args.output_dir / 'map.provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(json.dumps(provenance), flush=True)


if __name__ == '__main__':
    main()
