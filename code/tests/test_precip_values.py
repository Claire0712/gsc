"""Read-only precipitation audit, using real small NetCDF fixtures."""
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import h5netcdf
import numpy as np

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/audit_precip_values.py'
GRID = (np.array([90., 89.9]), np.array([0., .1, .2]))


def module():
    assert SCRIPT.exists(), 'precipitation audit implementation is not present'
    spec = importlib.util.spec_from_file_location('precip_values', SCRIPT)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def fixture(path, times, change=None):
    with h5netcdf.File(path, 'w') as f:
        f.dimensions = {'valid_time': len(times), 'latitude': 2, 'longitude': 3}
        for name, values in zip(('latitude', 'longitude'), GRID):
            f.create_variable(name, (name,), dtype='f8', data=values)
        t = f.create_variable('valid_time', ('valid_time',), dtype='i8', data=times)
        t.attrs.update(units='seconds since 1970-01-01', calendar='gregorian')
        v = f.create_variable('tp', ('valid_time', 'latitude', 'longitude'), dtype='f4', fillvalue=np.nan)
        v[:] = np.array([[0., 1., -2.], [np.nan, np.inf, -np.inf]])
        v.attrs.update(units='m', GRIB_stepType='accum', GRIB_dataType='fc')
        if change:
            change(f)


class PrecipTests(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src = self.root / 'input'
        self.src.mkdir()
        self.out = self.root / 'output'

    def make(self, name='precip_2026_01.nc', change=None):
        path = self.src / name
        fixture(path, self.m.expected_times(name), change)
        return path

    def test_statistics_partition_and_extrema(self):
        result = self.m.slice_statistics(np.array([[0., -0., -2., 3., np.nan, np.inf, -np.inf]]))
        self.assertEqual([result[k] for k in ('cells', 'finite_positive', 'finite_zero', 'finite_negative', 'nan', 'infinity')], [7, 1, 2, 1, 1, 2])
        self.assertEqual((result['finite_min_m'], result['finite_max_m'], result['negative_min_m']), (-2., 3., -2.))
        allnan = self.m.slice_statistics(np.full((2, 3), np.nan))
        self.assertEqual(allnan['nan'], 6)
        self.assertIsNone(allnan['finite_min_m'])
        self.assertIsNone(allnan['negative_min_m'])

    def test_expected_manifest_and_days(self):
        names = self.m.expected_names()
        self.assertEqual(len(names), 97)
        self.assertEqual(sum(len(self.m.expected_times(n)) for n in names), 2923)
        self.assertEqual(self.m.expected_times(names[0])[0], int(dt.datetime(2018, 1, 1, tzinfo=dt.timezone.utc).timestamp()))
        self.assertEqual(len(self.m.expected_times(names[-1])), 1)

    def test_file_audit_retains_anomalies_and_original_time(self):
        path = self.make()
        result = self.m.audit_file(path, grid=GRID)
        self.assertEqual(result['days'], 1)
        self.assertEqual(result['counts']['finite_negative'], 1)
        self.assertEqual(result['counts']['infinity'], 2)
        self.assertEqual(result['time_start'], '2026-01-01T00:00:00Z')
        self.assertEqual(result['daily'][0]['nan'], 1)

    def test_byte_attributes_and_no_fill_attribute(self):
        def change(f):
            f['tp'].attrs['units'] = np.bytes_('m')
            f['tp'].attrs['GRIB_stepType'] = np.bytes_('accum')
            f['tp'].attrs['GRIB_dataType'] = np.bytes_('fc')
            del f['tp'].attrs['_FillValue']
        self.assertEqual(self.m.audit_file(self.make(change=change), grid=GRID)['days'], 1)

    def test_reader_applies_bounded_hdf5_chunk_cache(self):
        path = self.make()
        open_file = h5netcdf.File
        observed = []
        def inspect_cache(*args, **kwargs):
            source = open_file(*args, **kwargs)
            observed.append((kwargs.get('rdcc_nbytes'), source._h5file.id.get_access_plist().get_cache()[2]))
            return source
        with patch.object(self.m.h5netcdf, 'File', inspect_cache):
            result = self.m.audit_file(path, grid=GRID)
        self.assertEqual(observed, [(256 * 1024 * 1024, 256 * 1024 * 1024)])
        self.assertEqual(result['counts']['finite_negative'], 1)

    def test_wrong_dimension_order_rejected(self):
        path = self.make()
        with h5netcdf.File(path, 'a') as f:
            del f._h5group['tp']
        with h5netcdf.File(path, 'a') as f:
            value = f.create_variable('tp', ('valid_time', 'longitude', 'latitude'), dtype='f4')
            value.attrs.update(units='m', GRIB_stepType='accum', GRIB_dataType='fc')
        with self.assertRaisesRegex(ValueError, 'dimensions'):
            self.m.audit_file(path, grid=GRID)

    def test_reject_invalid_schema_time_and_grid(self):
        changes = [
            lambda f: f['tp'].attrs.__setitem__('units', 'mm'),
            lambda f: f['tp'].attrs.__setitem__('GRIB_stepType', 'instant'),
            lambda f: f['tp'].attrs.__setitem__('GRIB_dataType', 'an'),
            lambda f: f['tp'].attrs.__setitem__('scale_factor', 1.),
            lambda f: f['tp'].attrs.__setitem__('add_offset', 0.),
            lambda f: f['valid_time'].__setitem__(0, 0),
            lambda f: f['valid_time'].attrs.__setitem__('calendar', '360_day'),
            lambda f: f['valid_time'].attrs.__setitem__('units', 'hours since 1970-01-01'),
            lambda f: f['latitude'].__setitem__(0, 80.),
            lambda f: f['tp'].attrs.__setitem__('_FillValue', -999.),
        ]
        for change in changes:
            with self.subTest(change=change):
                path = self.make(change=change)
                with self.assertRaises(ValueError):
                    self.m.audit_file(path, grid=GRID)
        path = self.make()
        with self.assertRaisesRegex(ValueError, 'shape'):
            self.m.audit_file(path)

    def test_full_run_hashes_checkpoints_totals_and_status(self):
        for name in self.m.expected_names():
            self.make(name)
        result = self.m.run_audit(self.src, self.out, grid=GRID)
        self.assertEqual((result['files'], result['days'], result['counts']['cells']), (97, 2923, 2923 * 6))
        self.assertEqual(result['counts']['finite_negative'], 2923)
        manifest = json.loads((self.out / 'manifest.json').read_text())
        self.assertEqual(len(manifest['sources']), 97)
        self.assertEqual(manifest.get('hdf5_raw_chunk_cache_bytes'), 256 * 1024 * 1024)
        self.assertEqual(manifest['sources'][0]['sha256'], hashlib.sha256((self.src / 'precip_2018_01.nc').read_bytes()).hexdigest())
        self.assertEqual(manifest['script']['sha256'], hashlib.sha256(SCRIPT.read_bytes()).hexdigest())
        self.assertEqual(len(list((self.out / 'monthly').glob('*.json'))), 97)
        status = json.loads((self.out / 'status.json').read_text())
        self.assertEqual((status['status'], status['files_completed'], status['days_completed']), ('completed', 97, 2923))
        self.assertGreater(status['pid'], 0)
        self.assertIn('baseline_computed', result)
        self.assertFalse(result['baseline_computed'])
        self.assertFalse(result['country_aggregation_computed'])
        self.assertFalse(status['baseline_computed'])
        self.assertFalse(status['country_aggregation_computed'])
        output_manifest = json.loads((self.out / 'output_manifest.json').read_text())
        self.assertEqual(len(output_manifest['outputs']), 98)
        for record in output_manifest['outputs']:
            content = (self.out / record['path']).read_bytes()
            self.assertEqual(record['sha256'], hashlib.sha256(content).hexdigest())
            self.assertEqual(record['bytes'], len(content))
        self.assertFalse(list(self.out.rglob('*.tmp')))
        for source in manifest['sources']:
            self.assertEqual(source['sha256'], hashlib.sha256(Path(source['path']).read_bytes()).hexdigest())
        before = {str(p.relative_to(self.out)): p.read_bytes() for p in self.out.rglob('*') if p.is_file()}
        with self.assertRaises(ValueError):
            self.m.run_audit(self.src, self.out, grid=GRID)
        self.assertEqual(before, {str(p.relative_to(self.out)): p.read_bytes() for p in self.out.rglob('*') if p.is_file()})

    def test_missing_extra_and_overlap_fail_closed(self):
        self.make()
        with self.assertRaisesRegex(ValueError, 'manifest'):
            self.m.run_audit(self.src, self.out, grid=GRID)
        self.assertEqual(json.loads((self.out / 'status.json').read_text())['status'], 'failed')
        with self.assertRaises(ValueError):
            self.m.run_audit(self.src, self.src / 'nested', grid=GRID)
        with self.assertRaises(ValueError):
            self.m.run_audit(self.src, self.root, grid=GRID)
        for name in self.m.expected_names():
            self.make(name)
        (self.src / 'precip_extra.nc').touch()
        with self.assertRaisesRegex(ValueError, 'manifest'):
            self.m.run_audit(self.src, self.root / 'extra', grid=GRID)

    def test_mutation_during_read_fails_and_no_summary_is_published(self):
        for name in self.m.expected_names():
            self.make(name)
        original = self.m.audit_file
        def mutate(path, **kwargs):
            result = original(path, **kwargs)
            with open(path, 'ab') as stream:
                stream.write(b'mutated')
            return result
        with patch.object(self.m, 'audit_file', mutate):
            with self.assertRaisesRegex(ValueError, 'changed'):
                self.m.run_audit(self.src, self.out, grid=GRID)
        self.assertFalse((self.out / 'summary.json').exists())
        self.assertEqual(json.loads((self.out / 'status.json').read_text())['status'], 'failed')

    def test_final_stat_sweep_detects_change_to_earlier_file(self):
        for name in self.m.expected_names():
            self.make(name)
        original = self.m.audit_file
        first = self.src / self.m.expected_names()[0]
        def mutate(path, **kwargs):
            manifest = json.loads((self.out / 'manifest.json').read_text())
            self.assertEqual(len(manifest['sources']), 97)
            result = original(path, **kwargs)
            if path.name == 'precip_2026_01.nc':
                with first.open('ab') as stream:
                    stream.write(b'changed after earlier read')
            return result
        with patch.object(self.m, 'audit_file', mutate):
            with self.assertRaisesRegex(ValueError, 'changed'):
                self.m.run_audit(self.src, self.out, grid=GRID)
        self.assertFalse((self.out / 'summary.json').exists())

    def test_hashing_detects_source_mutation(self):
        path = self.make()
        original = self.m.snapshot
        calls = 0
        def mutate(p):
            nonlocal calls
            calls += 1
            if calls == 2:
                with p.open('ab') as stream:
                    stream.write(b'changed while hashing')
            return original(p)
        with patch.object(self.m, 'snapshot', mutate):
            with self.assertRaisesRegex(ValueError, 'changed'):
                self.m.fingerprint(path)


if __name__ == '__main__':
    unittest.main()
