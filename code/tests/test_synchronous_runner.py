import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from scripts.run_synchronous_screen import run


class RunnerTests(unittest.TestCase):
    def fixture(self, root):
        for name in ['connection', 'quality', 'cross']:
            (root / name).mkdir()
        c, q, x = (root / n for n in ['connection', 'quality', 'cross'])
        start = int(np.datetime64('2022-01-01', 's').astype(int))
        end = int(np.datetime64('2022-04-01', 's').astype(int))
        t = np.arange(start, end, 600)
        values = np.full((2, len(t)), 10.)
        values[0, 144] = 0.
        outputs = []
        for signal in ['ping-slash24', 'bgp', 'merit-nt']:
            p = c / f'ioda_2022Q1_{signal}.npz'
            np.savez_compressed(p, values=values, country_ids=np.array(['AA', 'BB']),
                                interval_start_utc=t, native_phase_seconds=np.array([0, 0]))
            outputs.append(dict(file=p.name, sha256=hashlib.sha256(p.read_bytes()).hexdigest(), bytes=p.stat().st_size))
        (c / 'manifest.json').write_text(json.dumps(dict(outputs=outputs)))
        (c / 'status.json').write_text(json.dumps(dict(state='complete')))
        for folder, filename, fields, rows in [
            (q, 'coverage_annual.csv', ['country_id', 'year', 'signal', 'valid_points', 'expected_points'],
             [dict(country_id=id,year=2022,signal=s,valid_points=52560 if s=='ping-slash24' else 105120,expected_points=52560 if s=='ping-slash24' else 105120) for id in ['AA','BB'] for s in ['ping-slash24','bgp','merit-nt']]),
            (x, 'joint_crosswalk.csv', ['ioda_iso2', 'joint_status', 'joint_country_id'],
             [dict(ioda_iso2='AA',joint_status='exact_joint_match',joint_country_id='AAA'), dict(ioda_iso2='BB',joint_status='source_not_exact',joint_country_id='')])]:
            p = folder / filename
            with p.open('w') as f:
                w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
            meta=dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            (folder/'manifest.json').write_text(json.dumps(dict(outputs={filename:meta})))
        (q/'summary.json').write_text(json.dumps(dict(quality_pass=True)))
        (x/'status.json').write_text(json.dumps(dict(status='completed')))
        return c,q,x

    def test_pilot_outputs_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); c,q,x=self.fixture(root)
            result=run(c,q,x,root/'out',['2022Q1'])
            self.assertFalse(result['full_period'])
            self.assertFalse(result['exclusions_generated'])
            self.assertEqual(len(result['screens']),6)
            with np.load(root/'out'/'ping-slash24_joint.npz') as a:
                self.assertEqual(a['denominator'][144],1)
                self.assertEqual(a['numerator'][144],1)
                self.assertTrue(a['candidate'][144])
                self.assertTrue(np.isnan(a['fraction'][:144]).all())
            with self.assertRaises(FileExistsError):
                run(c,q,x,root/'out',['2022Q1'])

    def test_tampered_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); c,q,x=self.fixture(root)
            with (q/'coverage_annual.csv').open('a') as f:f.write('bad')
            with self.assertRaises(ValueError):run(c,q,x,root/'out',['2022Q1'])


if __name__ == '__main__': unittest.main()
