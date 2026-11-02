"""Population-conserving ADM0 weights for the native global 0.25 degree ERA5 grid.

Population counts are never interpolated or averaged. Each native population
pixel is assigned once, then its count is summed at its nearest ERA5 node.
"""

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import MergeAlg
from rasterio.features import rasterize
from rasterio.windows import Window, bounds as window_bounds
from scipy import sparse
from shapely.geometry import box
from shapely.strtree import STRtree
import xarray as xr


ERA5_LATITUDE = np.arange(90., -90.01, -.25, dtype=np.float64)
ERA5_LONGITUDE = np.arange(-180., 180., .25, dtype=np.float64)


def validate_era5_grid(latitude, longitude):
    """Require the ordered grid used by the hourly aggregation pipeline."""
    for actual, expected in [(latitude, ERA5_LATITUDE), (longitude, ERA5_LONGITUDE)]:
        actual = np.asarray(actual)
        if actual.shape != expected.shape or not np.allclose(actual, expected, atol=1e-10, rtol=0):
            raise ValueError('ERA5 grid must be latitude 90..-90 and longitude -180..179.75 at 0.25 degrees')


def nearest_era5_indices(latitude, longitude):
    """Assign centers to nearest nodes; exact ties go south/east, longitude wraps."""
    latitude, longitude = np.asarray(latitude), np.asarray(longitude)
    if not np.all(np.isfinite(latitude)) or np.any(np.abs(latitude) > 90):
        raise ValueError('Population pixel latitude must be finite and in [-90, 90]')
    if not np.all(np.isfinite(longitude)):
        raise ValueError('Population pixel longitude must be finite')
    rows = np.clip(np.floor((90. - latitude) * 4 + .5), 0, 720).astype(np.int64)
    cols = (np.floor(((longitude + 180.) % 360.) * 4 + .5).astype(np.int64) % 1440)
    return rows, cols


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def source_fingerprint(path, content_hash=False):
    path = Path(path).resolve()
    stat = path.stat()
    return {'path': str(path), 'size_bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns,
            'sha256': sha256(path) if content_hash else None,
            'verification': 'sha256_and_file_stat' if content_hash else 'file_stat_only'}


def validate_cached(output_dir, provenance, sources, grid):
    try:
        metadata = json.loads((output_dir / 'weights_metadata.json').read_text())
    except (OSError, ValueError) as exc:
        raise ValueError('Existing weights cache is incomplete; use a new output directory') from exc
    if (metadata.get('provenance') != provenance or metadata.get('sources') != sources
            or metadata.get('grid') != grid):
        raise ValueError('Existing weights cache provenance does not match; use a new output directory')
    for name in ['weights.npz', 'country_metadata.csv']:
        path = output_dir / name
        if not path.is_file() or sha256(path) != metadata.get('artifacts_sha256', {}).get(name):
            raise ValueError('Existing weights cache artifact integrity check failed: ' + name)
    return metadata


def read_grid(sample):
    with xr.open_dataset(sample, decode_times=False) as dataset:
        if 'latitude' not in dataset.coords or 'longitude' not in dataset.coords:
            raise ValueError('ERA5 grid requires latitude and longitude coordinates')
        latitude = dataset.latitude.values.astype(np.float64)
        longitude = dataset.longitude.values.astype(np.float64)
    validate_era5_grid(latitude, longitude)
    return {'latitude': latitude.tolist(), 'longitude': longitude.tolist(),
            'shape': [len(latitude), len(longitude)], 'flatten_order': 'C',
            'latitude_sha256': hashlib.sha256(latitude.astype('<f8').tobytes()).hexdigest(),
            'longitude_sha256': hashlib.sha256(longitude.astype('<f8').tobytes()).hexdigest()}


def load_countries(path, id_field=None, name_field=None):
    frame = gpd.read_file(path)
    if frame.crs is None or frame.crs.to_epsg() != 4326:
        raise ValueError('Boundaries must use geographic WGS84 (EPSG:4326)')
    if id_field is None:
        id_field = next((field for field in ['shapeGroup', 'country_id', 'id'] if field in frame), None)
    if id_field is None or id_field not in frame:
        raise ValueError('No stable country ID field; supply --id-field explicitly')
    if name_field is None:
        name_field = next((field for field in ['shapeName', 'country_name', 'name'] if field in frame), None)
    if name_field is not None and name_field not in frame:
        raise ValueError('Country name field is missing: ' + name_field)
    countries = []
    seen = set()
    for _, row in frame.iterrows():
        raw_id = row[id_field]
        if raw_id is None or (isinstance(raw_id, float) and not np.isfinite(raw_id)):
            raise ValueError('Country ID is missing')
        code = str(raw_id).strip()
        if not code or code in seen:
            raise ValueError('Duplicate or empty country ID: ' + code)
        seen.add(code)
        geometry = row.geometry
        if geometry is None or geometry.is_empty or geometry.geom_type not in ['Polygon', 'MultiPolygon']:
            raise ValueError('Country must have a nonempty polygon: ' + code)
        if not geometry.is_valid:
            raise ValueError('Invalid boundary geometry: ' + code)
        name = str(row[name_field]) if name_field is not None else ''
        countries.append({'country_id': code, 'country_name': name, 'geometry': geometry})
    if not countries or len(countries) >= np.iinfo(np.uint16).max:
        raise ValueError('Expected between 1 and 65534 country units')
    countries.sort(key=lambda item: item['country_id'])
    return countries, id_field, name_field


def accumulate_population(population, countries, block_rows, block_cols, overlap_policy, progress=False):
    if not 1 <= block_rows <= 256 or not 1 <= block_cols <= 4096:
        raise ValueError('Window limits require 1..256 rows and 1..4096 columns')
    if overlap_policy not in ['first', 'error']:
        raise ValueError('Unknown overlap policy')
    geometries, owners = [], []
    for country_index, country in enumerate(countries):
        geometry = country['geometry']
        for part in geometry.geoms if geometry.geom_type == 'MultiPolygon' else [geometry]:
            geometries.append(part)
            owners.append(country_index)
    tree = STRtree(geometries)
    aggregate = {}
    audit = dict(raw_population_sum=0., assigned_population_sum=0., unassigned_population_sum=0.,
                 valid_population_pixels=0, nodata_pixels=0, nonfinite_pixels=0,
                 overlap_positive_population_pixels=0, overlap_population_sum=0.,
                 max_window_pixels=0, windows_processed=0)
    with rasterio.Env(GDAL_CACHEMAX=64 * 1024 * 1024), rasterio.open(population) as source:
        if source.crs is None or source.crs.to_epsg() != 4326:
            raise ValueError('Population raster must use geographic WGS84 (EPSG:4326)')
        transform = source.transform
        if source.count != 1 or transform.b != 0 or transform.d != 0 or transform.a <= 0 or transform.e >= 0:
            raise ValueError('Population raster must be one-band, north-up, unrotated')
        if source.bounds.left < -180.00001 or source.bounds.right > 180.00001:
            raise ValueError('Population raster longitude extent must be in [-180, 180]')
        if source.bounds.bottom < -90.00001 or source.bounds.top > 90.00001:
            raise ValueError('Population raster latitude extent must be in [-90, 90]')
        raster_metadata = {'crs': source.crs.to_string(), 'transform': list(transform)[:6],
                           'width': source.width, 'height': source.height,
                           'nodata': float(source.nodata) if source.nodata is not None and np.isfinite(source.nodata) else None}
        total_windows = ((source.height + block_rows - 1) // block_rows) * ((source.width + block_cols - 1) // block_cols)
        if progress:
            print(json.dumps({'event': 'population_weights_start', 'rows': source.height,
                              'columns': source.width, 'countries': len(countries),
                              'total_windows': total_windows, 'window_shape': [block_rows, block_cols]}),
                  file=sys.stderr, flush=True)
        for top in range(0, source.height, block_rows):
            for left in range(0, source.width, block_cols):
                height, width = min(block_rows, source.height - top), min(block_cols, source.width - left)
                window = Window(left, top, width, height)
                values = source.read(1, window=window, masked=True)
                data = values.data
                nodata = np.ma.getmaskarray(values)
                finite = np.isfinite(data)
                valid = ~nodata & finite
                if np.any(data[valid] < 0):
                    raise ValueError('Population raster contains negative non-nodata counts')
                audit['windows_processed'] += 1
                audit['max_window_pixels'] = max(audit['max_window_pixels'], width * height)
                audit['nodata_pixels'] += int(nodata.sum())
                audit['nonfinite_pixels'] += int((~nodata & ~finite).sum())
                audit['valid_population_pixels'] += int(valid.sum())
                total = float(data[valid].sum(dtype=np.float64))
                audit['raw_population_sum'] += total
                if progress and (audit['windows_processed'] == 1 or audit['windows_processed'] % 20 == 0):
                    print(json.dumps({'event': 'population_weights_progress',
                                      'windows_read': audit['windows_processed'], 'total_windows': total_windows,
                                      'raw_population_sum': audit['raw_population_sum'],
                                      'sparse_country_cells_accumulated': len(aggregate)}), file=sys.stderr, flush=True)
                positive = valid & (data > 0)
                if not np.any(positive):
                    continue
                candidates = sorted(tree.query(box(*window_bounds(window, transform))),
                                    key=lambda index: (owners[index], int(index)), reverse=True)
                if not candidates:
                    audit['unassigned_population_sum'] += total
                    continue
                shapes = [(geometries[index], owners[index] + 1) for index in candidates]
                labels = rasterize(shapes, out_shape=(height, width), transform=source.window_transform(window),
                                   fill=0, all_touched=False, dtype='uint16')
                coverage = rasterize([(geometries[index], 1) for index in candidates],
                                     out_shape=(height, width), transform=source.window_transform(window),
                                     fill=0, all_touched=False, dtype='uint16', merge_alg=MergeAlg.add)
                overlap = positive & (coverage > 1)
                audit['overlap_positive_population_pixels'] += int(overlap.sum())
                audit['overlap_population_sum'] += float(data[overlap].sum(dtype=np.float64))
                if np.any(overlap) and overlap_policy == 'error':
                    raise ValueError('Positive population pixel centers overlap multiple boundary polygons')
                assigned = positive & (labels > 0)
                assigned_sum = float(data[assigned].sum(dtype=np.float64))
                audit['assigned_population_sum'] += assigned_sum
                audit['unassigned_population_sum'] += float(data[positive & (labels == 0)].sum(dtype=np.float64))
                if not assigned_sum:
                    continue
                pixel_rows, pixel_cols = np.nonzero(assigned)
                latitude = transform.f + (top + pixel_rows + .5) * transform.e
                longitude = transform.c + (left + pixel_cols + .5) * transform.a
                grid_rows, grid_cols = nearest_era5_indices(latitude, longitude)
                keys = ((labels[assigned].astype(np.int64) - 1) * (721 * 1440)
                        + grid_rows * 1440 + grid_cols)
                unique, inverse = np.unique(keys, return_inverse=True)
                masses = np.bincount(inverse, weights=data[assigned].astype(np.float64))
                for key, mass in zip(unique.tolist(), masses.tolist()):
                    aggregate[key] = aggregate.get(key, 0.) + mass
    keys = np.fromiter(aggregate.keys(), dtype=np.int64, count=len(aggregate))
    masses = np.fromiter(aggregate.values(), dtype=np.float64, count=len(aggregate))
    matrix = sparse.csr_matrix((masses, (keys // (721 * 1440), keys % (721 * 1440))),
                               shape=(len(countries), 721 * 1440))
    totals = np.asarray(matrix.sum(axis=1)).ravel()
    inverses = np.divide(1., totals, out=np.zeros_like(totals), where=totals > 0)
    matrix = sparse.diags(inverses).dot(matrix).tocsr()
    matrix.sort_indices()
    if not np.isclose(totals.sum(), audit['assigned_population_sum'], rtol=1e-10, atol=1e-6):
        raise ValueError('Population mass conservation failed during sparse accumulation')
    if not np.isclose(audit['raw_population_sum'], audit['assigned_population_sum'] +
                      audit['unassigned_population_sum'], rtol=1e-10, atol=1e-6):
        raise ValueError('Population assignment mass conservation failed')
    audit['sparse_nonzero_entries'] = matrix.nnz
    audit['zero_population_countries'] = int((totals == 0).sum())
    return matrix, totals, audit, raster_metadata


def build_weights(population, boundaries, era5_sample, output_dir, *, block_rows=256, block_cols=4096,
                  id_field=None, name_field=None, overlap_policy='error', population_sha256=False, progress=False):
    population, boundaries, era5_sample, output_dir = map(Path, [population, boundaries, era5_sample, output_dir])
    if boundaries.suffix.lower() not in ['.geojson', '.json', '.gpkg']:
        raise ValueError('Use a single-file GeoJSON or GeoPackage boundary source for complete provenance')
    grid = read_grid(era5_sample)
    sources = {'population': source_fingerprint(population, population_sha256),
               'boundaries': source_fingerprint(boundaries, True),
               'era5_sample': source_fingerprint(era5_sample)}
    provenance = {'script_sha256': sha256(Path(__file__)),
                  'parameters': {'block_rows': block_rows, 'block_cols': block_cols,
                                 'id_field': id_field, 'name_field': name_field,
                                 'overlap_policy': overlap_policy, 'population_sha256': population_sha256}}
    if output_dir.exists():
        return validate_cached(output_dir, provenance, sources, grid)
    countries, id_field, name_field = load_countries(boundaries, id_field, name_field)
    matrix, totals, audit, raster_metadata = accumulate_population(
        population, countries, block_rows, block_cols, overlap_policy, progress=progress)
    for source in sources.values():
        current = source_fingerprint(source['path'])
        if any(current[key] != source[key] for key in ['size_bytes', 'mtime_ns']):
            raise ValueError('Input source changed during weight construction: ' + source['path'])
    metadata = {'schema_version': 1, 'grid': grid, 'audit': audit, 'population_raster': raster_metadata,
                'provenance': provenance, 'sources': sources,
                'country_id_field': id_field, 'country_name_field': name_field,
                'method': {
                    'boundary_assignment': 'Native population pixel-center assignment (rasterio all_touched=False)',
                    'boundary_approximation': 'A pixel is assigned wholly by its center, not by fractional area; '
                                              'coastal and border allocations are approximate at native population resolution.',
                    'grid_assignment': 'Nearest ERA5 node; exact half-step ties go south/east; longitude wraps.',
                    'overlap_policy': overlap_policy,
                    'overlap_resolution': ('Reject positive population on overlapping polygons.' if overlap_policy == 'error'
                                           else 'First country in lexical country_id order wins; population is never duplicated.'),
                    'population_resampling': 'None; native nonnegative finite pixel counts are summed.',
                    'normalization': 'Each populated country row sums to one; zero-population rows remain zero.'}}
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.' + output_dir.name + '-', dir=output_dir.parent))
    try:
        sparse.save_npz(staging / 'weights.npz', matrix)
        with (staging / 'country_metadata.csv').open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, ['country_id', 'total_population', 'country_name'])
            writer.writeheader()
            for country, total in zip(countries, totals):
                writer.writerow({'country_id': country['country_id'], 'total_population': format(total, '.17g'),
                                 'country_name': country['country_name']})
        metadata['artifacts_sha256'] = {name: sha256(staging / name)
                                        for name in ['weights.npz', 'country_metadata.csv']}
        (staging / 'weights_metadata.json').write_text(json.dumps(metadata, indent=2, allow_nan=False) + '\n')
        if output_dir.exists():
            raise ValueError('Output directory appeared during construction; refusing to overwrite it')
        os.replace(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--population', type=Path, required=True, help='Native WGS84 population counts GeoTIFF')
    parser.add_argument('--boundaries', type=Path, required=True, help='WGS84 ADM0 GeoPackage or GeoJSON')
    parser.add_argument('--era5-sample', type=Path, required=True, help='ERA5 NetCDF used to verify native grid order')
    parser.add_argument('--output-dir', type=Path, required=True, help='New directory or matching complete cache')
    parser.add_argument('--id-column', '--id-field', dest='id_field')
    parser.add_argument('--name-column', '--name-field', dest='name_field')
    parser.add_argument('--block-rows', type=int, default=256)
    parser.add_argument('--block-cols', type=int, default=4096)
    parser.add_argument('--overlap-policy', choices=['error', 'first'], default='error')
    parser.add_argument('--population-sha256', action='store_true',
                        help='Stream a full population-file SHA256; default records size/mtime only')
    args = parser.parse_args()
    metadata = build_weights(**vars(args), progress=True)
    print(json.dumps({'output_dir': str(args.output_dir.resolve()), 'audit': metadata['audit']}, allow_nan=False))


if __name__ == '__main__':
    main()
