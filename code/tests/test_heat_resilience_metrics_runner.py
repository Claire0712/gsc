import csv
import importlib.util
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import run_connection_baseline as upstream


class RunnerTests(unittest.TestCase):
    def load(self):
        path=ROOT/'scripts/run_heat_resilience_metrics.py'
        self.assertTrue(path.exists(),'batch metrics runner missing')
        spec=importlib.util.spec_from_file_location('runner',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def fixture(self,p):
        p.mkdir()
        start=upstream.archive.utc('2024-01-01T00:00:00Z'); t=np.arange(start,start+96*3600,600)
        ones=np.ones(576,dtype=bool); bits=np.ones(576,dtype=np.uint8);bits[0]|=2
        np.savez(p/'points_000000_bgp.npz',event_id=np.array('E'),country_id=np.array('TON'),signal=np.array('bgp'),
                 target_timestamps=t,target_values=np.full(576,.9),baseline=np.ones(576),analysis_available=ones,
                 target_valid=ones,baseline_available=ones,core_mask=np.arange(576)<144,target_exclusion_bits=bits,
                 target_mask_coverage_complete=ones,target_analysis_unconfounded=(bits&22)==0)
        audit=dict(event_id='E',country_id='TON',ioda_iso2='TO',signal='bgp',point_file='points_000000_bgp.npz',
                   expected_full_slots=576,target_valid_slots=576,baseline_available_slots=576,analysis_available_slots=576,
                   full_target_and_baseline=True,target_stop_or_cyclone_slots=1,target_cyclone_uncertain_slots=0,
                   target_mask_coverage_unknown_slots=0,unresolved_stop_country_records=0,unknown_end_stop_country_records=0,
                   full_observed_unconfounded=False,final_sample_eligible=False)
        routes=[dict(event_id='E',country_id='TON',route='forward',start_date='2024-01-01',end_exclusive_utc='2024-01-02T00:00:00Z'),
                dict(event_id='H',country_id='TON',route='held_stop_review',start_date='2024-02-01',end_exclusive_utc='2024-02-02T00:00:00Z')]
        upstream.archive.write_csv(p/'event_baseline_audit.csv',list(audit),[audit])
        upstream.archive.write_csv(p/'event_routing.csv',list(routes[0]),routes)
        upstream.archive.write_csv(p/'held_stop_review.csv',list(routes[0]),routes[1:])
        (p/'summary.json').write_text(json.dumps(dict(status='completed',mask_bits=upstream.MASK_BITS,selected_countries=['TON'],selected_signals=['bgp'],signal_windows=1,final_sample_eligible=False)))
        (p/'status.json').write_text('{"status":"completed"}')
        self.manifest(p)

    def manifest(self,p):
        outputs={x.name:upstream.archive.fingerprint(x) for x in p.iterdir() if x.name not in ['manifest.json','status.json']}
        (p/'manifest.json').write_text(json.dumps(dict(status='completed',inputs={'fixture':{}},outputs=outputs)))

    def test_confounded_observation_kept_technical_not_final_and_no_overwrite(self):
        m=self.load()
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'source'; out=Path(temp)/'out'; self.fixture(p)
            result=m.run(p,out)
            self.assertEqual(result['technical_complete_windows'],1)
            self.assertEqual(result['full_observed_unconfounded_windows'],0)
            rows=json.loads((out/'event_metrics.json').read_text())
            self.assertAlmostEqual(rows[0]['metrics']['dhrd_hours'],9.6)
            self.assertFalse(rows[0]['final_sample_eligible'])
            self.assertIn('target_stop_or_conservative_cyclone_flag',rows[0]['qualification_reasons'])
            self.assertEqual(result['held_stop_review_rows'],1)
            with self.assertRaises(FileExistsError):m.run(p,out)

    def test_rejects_corrupt_hash_incomplete_status_and_wrong_schema(self):
        m=self.load()
        for case in ['hash','status','schema','identity','unconfounded']:
            with self.subTest(case=case),tempfile.TemporaryDirectory() as temp:
                p=Path(temp)/'source';self.fixture(p)
                if case=='hash':(p/'event_baseline_audit.csv').write_text('corrupt')
                elif case=='status':(p/'status.json').write_text('{"status":"running"}')
                else:
                    path=p/'points_000000_bgp.npz'
                    with np.load(path,allow_pickle=False) as z:arrays={k:z[k] for k in z.files}
                    if case=='schema':del arrays['core_mask']
                    elif case=='identity':arrays['event_id']=np.array('wrong')
                    else:arrays['target_analysis_unconfounded']=np.ones(576,dtype=bool)
                    np.savez(path,**arrays);self.manifest(p)
                with self.assertRaises((ValueError,KeyError)):m.run(p,Path(temp)/'out')

    def test_cli_imports_under_warnings_as_errors(self):
        self.load()
        result=subprocess.run([sys.executable,'-W','error',str(ROOT/'scripts/run_heat_resilience_metrics.py'),'--help'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
