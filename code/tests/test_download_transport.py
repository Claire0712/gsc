import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile
import hashlib
import io
import json
from unittest.mock import patch


def load():
    p = Path(__file__).resolve().parents[1] / 'scripts/server_fetch.py'
    spec = importlib.util.spec_from_file_location('transport', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class TransportTests(unittest.TestCase):
    def test_empty_partial_can_be_retried(self):
        m = load()
        content = b'CDF\x01transport fixture'
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            identity = hashlib.sha256(b'job1').hexdigest()[:16]
            (root / ('test.' + identity + '.part')).touch()
            response = io.BytesIO(content)
            response.status = 200
            response.headers = {'Content-Length': str(len(content))}
            request = {'id': 'test', 'url': 'https://example.org/data', 'bytes': len(content),
                       'job_id': 'job1', 'target_stem': 'test'}
            with patch.object(m.urllib.request, 'urlopen', return_value=response):
                result = m.fetch(root, request)
            self.assertEqual(result['status'], 'downloaded_verified')
            self.assertEqual((root / 'test.nc').read_bytes(), content)

    def test_published_file_recovered_after_crash_before_final_record(self):
        m = load()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = root / 'test.nc'
            p.write_bytes(b'CDF\x01transport fixture')
            records = root / 'metadata/full_download_v2/records'
            records.mkdir(parents=True)
            record = records / 'test.json'
            record.write_text(json.dumps({'status': 'validated_pending_publish', 'file': 'test.nc',
                                         'bytes': p.stat().st_size, 'sha256': m.sha(p)}))
            with patch.object(m.urllib.request, 'urlopen', side_effect=AssertionError('must not download again')):
                result = m.fetch(root, {'id': 'test', 'url': 'https://example.org/data', 'bytes': p.stat().st_size})
            self.assertEqual(result['status'], 'downloaded_verified')
            self.assertEqual(json.loads(record.read_text())['status'], 'downloaded_verified')

    def test_path_escape_is_rejected(self):
        m = load()
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                m.safe_path(Path(d), '../outside')
            self.assertEqual(m.safe_path(Path(d), 'era5_land/a'), Path(d).resolve()/'era5_land/a')

    def test_range_must_match_existing_offset(self):
        m = load()
        self.assertTrue(m.valid_range(206, 'bytes 10-99/100', 10, 100))
        self.assertFalse(m.valid_range(200, None, 10, 100))
        self.assertFalse(m.valid_range(206, 'bytes 0-99/100', 10, 100))
        self.assertFalse(m.valid_range(206, 'bytes 10-100/101', 10, 100))

    def test_html_response_is_not_accepted_as_climate_data(self):
        m = load()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'part'
            p.write_bytes(b'<html>expired download link</html>')
            with self.assertRaises(ValueError):
                m.inspect_format(p)

    def test_zip_requires_crc_and_netcdf_members(self):
        m = load()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'part'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('value.nc', b'CDF\x01test')
            self.assertEqual(m.inspect_format(p), '.zip')
            q = Path(d)/'bad'
            with zipfile.ZipFile(q, 'w') as z:
                z.writestr('error.txt', 'no data')
            with self.assertRaises(ValueError):
                m.inspect_format(q)


if __name__ == '__main__':
    unittest.main()
