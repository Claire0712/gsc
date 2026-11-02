import importlib.util
import csv
import json
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from scipy import sparse
from shapely.geometry import box, mapping
import xarray as xr


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/build_era5_population_weights.py'


def module(test):
    test.assertTrue(SCRIPT.is_file(), 'Population-conserving ERA5 weight builder is missing')
    spec = importlib.util.spec_from_file_location('era5_population_weights', SCRIPT)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class GridTests(unittest.TestCase):
    def test_nearest_nodes_include_poles_dateline_wrap_and_half_step_ties(self):
        m = module(self)
        rows, cols = m.nearest_era5_indices(
            np.array([90., 89.875, 0., -89.999, -90., 0., 0.]),
            np.array([-180., -179.875, 179.99, 180., 540., -180.125, -0.125]))
        np.testing.assert_array_equal(rows, [0, 1, 360, 720, 720, 360, 360])
        np.testing.assert_array_equal(cols, [0, 1, 0, 0, 0, 0, 720])

    def test_wrong_grid_resolution_order_and_latitude_are_rejected(self):
        m = module(self)
        lat = np.arange(90., -90.01, -.25)
        lon = np.arange(-180., 180., .25)
        m.validate_era5_grid(lat, lon)
        for a, b in [(lat[::-1], lon), (lat, lon + 180), (lat[::2], lon)]:
            with self.assertRaisesRegex(ValueError, 'ERA5 grid'):
                m.validate_era5_grid(a, b)
        with self.assertRaisesRegex(ValueError, 'latitude'):
            m.nearest_era5_indices(np.array([90.1]), np.array([0.]))


class BuilderTests(unittest.TestCase):
    def fixture(self, root, *, overlaps=False, duplicate=False, crs='EPSG:4326', negative=False):
        population = root / 'population.tif'
        values = np.array([[1, 2, 3, 4], [5, np.nan, 7, 8],
                           [9, -9999, 11, 12], [13, 14, 15, 16]], dtype='float32')
        if negative:
            values[0, 0] = -1
        with rasterio.open(population, 'w', driver='GTiff', width=4, height=4,
                           count=1, dtype='float32', crs=crs,
                           transform=from_origin(-.2, .2, .1, .1), nodata=-9999) as dataset:
            dataset.write(values, 1)
        countries = [('12', 'Numeric unit', box(-.2, -.2, 0, .2)),
                     ('12' if duplicate else 'BBB', 'Beta',
                      box(-.1 if overlaps else 0, -.2, .1, .2)),
                     ('CCC', 'No population', box(10, 10, 11, 11))]
        boundaries = root / 'countries.geojson'
        boundaries.write_text(json.dumps({'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'properties': {'shapeGroup': code, 'shapeName': name},
             'geometry': mapping(geometry)} for code, name, geometry in countries]}))
        sample = root / 'era5.nc'
        xr.Dataset(coords={'latitude': np.arange(90., -90.01, -.25),
                           'longitude': np.arange(-180., 180., .25)}).to_netcdf(sample)
        return population, boundaries, sample

    def test_conserves_native_population_and_keeps_numeric_and_zero_population_units(self):
        m = module(self)
        self.assertTrue(hasattr(m, 'build_weights'), 'Windowed weight construction is missing')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = self.fixture(root)
            meta = m.build_weights(*paths, root / 'weights', block_rows=1, block_cols=2)
            matrix = sparse.load_npz(root / 'weights/weights.npz')
            self.assertEqual(matrix.shape, (3, 721 * 1440))
            np.testing.assert_allclose(np.asarray(matrix.sum(axis=1)).ravel(), [1, 1, 0])
            with (root / 'weights/country_metadata.csv').open() as handle:
                countries = list(csv.DictReader(handle))
            self.assertEqual([row['country_id'] for row in countries], ['12', 'BBB', 'CCC'])
            self.assertEqual([float(row['total_population']) for row in countries], [44, 36, 0])
            self.assertAlmostEqual(matrix[0, 360 * 1440 + 719], 14 / 44)
            self.assertAlmostEqual(matrix[1, 360 * 1440 + 720], 18 / 36)
            self.assertEqual(meta['audit']['raw_population_sum'], 120)
            self.assertEqual(meta['audit']['assigned_population_sum'], 80)
            self.assertEqual(meta['audit']['unassigned_population_sum'], 40)
            self.assertEqual(meta['audit']['nodata_pixels'], 1)
            self.assertEqual(meta['audit']['nonfinite_pixels'], 1)
            self.assertLessEqual(meta['audit']['max_window_pixels'], 2)
            self.assertEqual(meta['grid']['flatten_order'], 'C')
            self.assertIn('pixel-center', meta['method']['boundary_assignment'])

    def test_overlaps_have_explicit_deterministic_assignment_and_strict_mode(self):
        m = module(self)
        self.assertTrue(hasattr(m, 'build_weights'), 'Overlap-aware weight construction is missing')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = self.fixture(root, overlaps=True)
            meta = m.build_weights(*paths, root / 'weights', block_rows=2, block_cols=2, overlap_policy='first')
            self.assertEqual(meta['audit']['overlap_positive_population_pixels'], 2)
            self.assertEqual(meta['audit']['overlap_population_sum'], 16)
            self.assertEqual(meta['audit']['assigned_population_sum'], 80)
            with self.assertRaisesRegex(ValueError, 'overlap'):
                m.build_weights(*paths, root / 'strict', overlap_policy='error')
            self.assertFalse((root / 'strict').exists())

    def test_duplicate_country_ids_non_wgs84_and_negative_population_are_rejected(self):
        m = module(self)
        self.assertTrue(hasattr(m, 'build_weights'), 'Input validation is missing')
        for option, error in [({'duplicate': True}, 'Duplicate'),
                              ({'crs': 'EPSG:3857'}, 'WGS84'), ({'negative': True}, 'negative')]:
            with self.subTest(option=option), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                paths = self.fixture(root, **option)
                with self.assertRaisesRegex(ValueError, error):
                    m.build_weights(*paths, root / 'weights')

    def test_cache_is_reused_only_with_matching_sources_parameters_script_and_artifacts(self):
        m = module(self)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = self.fixture(root)
            output = root / 'weights'
            first = m.build_weights(*paths, output)
            self.assertIn('provenance', first, 'Cache provenance is missing')
            self.assertEqual(first['provenance']['script_sha256'], m.sha256(SCRIPT))
            self.assertIsNone(first['sources']['population']['sha256'])
            original_mtime = (output / 'weights.npz').stat().st_mtime_ns
            self.assertEqual(m.build_weights(*paths, output), first)
            self.assertEqual((output / 'weights.npz').stat().st_mtime_ns, original_mtime)
            with self.assertRaisesRegex(ValueError, 'provenance'):
                m.build_weights(*paths, output, block_rows=32)
            paths[1].write_text(paths[1].read_text() + '\n')
            with self.assertRaisesRegex(ValueError, 'provenance'):
                m.build_weights(*paths, output)

    def test_corrupt_cache_is_rejected_and_optional_population_hash_is_written(self):
        m = module(self)
        self.assertIn('population_sha256', __import__('inspect').signature(m.build_weights).parameters,
                      'Optional population content hash is missing')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = self.fixture(root)
            output = root / 'weights'
            meta = m.build_weights(*paths, output, population_sha256=True)
            self.assertEqual(meta['sources']['population']['sha256'], m.sha256(paths[0]))
            with (output / 'country_metadata.csv').open('a') as handle:
                handle.write('EXTRA,1,Unexpected\n')
            with self.assertRaisesRegex(ValueError, 'integrity'):
                m.build_weights(*paths, output, population_sha256=True)

    def test_dateline_and_polar_population_go_to_wrapped_and_clipped_nodes(self):
        m = module(self)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            population, boundaries, sample = self.fixture(root)
            with rasterio.open(population, 'w', driver='GTiff', width=2, height=2,
                               count=1, dtype='float32', crs='EPSG:4326',
                               transform=from_origin(179.8, 90, .1, .1)) as dataset:
                dataset.write(np.array([[4, 8], [16, 32]], dtype='float32'), 1)
            boundaries.write_text(json.dumps({'type': 'FeatureCollection', 'features': [
                {'type': 'Feature', 'properties': {'shapeGroup': 'PAC', 'shapeName': 'Pacific'},
                 'geometry': mapping(box(179.8, 89.8, 180, 90))}]}))
            m.build_weights(population, boundaries, sample, root / 'weights')
            matrix = sparse.load_npz(root / 'weights/weights.npz')
            for cell, mass in [(1439, 4), (0, 8), (1440 + 1439, 16), (1440, 32)]:
                self.assertAlmostEqual(matrix[0, cell], mass / 60)

    def test_cli_accepts_explicit_country_columns(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = self.fixture(root)
            result = subprocess.run([sys.executable, str(SCRIPT), '--population', str(paths[0]),
                                     '--boundaries', str(paths[1]), '--era5-sample', str(paths[2]),
                                     '--output-dir', str(root / 'weights'), '--id-column', 'shapeGroup',
                                     '--name-column', 'shapeName'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / 'weights/weights_metadata.json').exists(), 'CLI did not build artifacts')
            self.assertIn('population_weights_start', result.stderr)
            self.assertIn('population_weights_progress', result.stderr)


if __name__ == '__main__':
    unittest.main()
