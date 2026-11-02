import unittest,importlib,json
import numpy as np
from tests.test_connection_baseline_runner import BaselineRunnerTests

class SyncBaselineRunnerTest(unittest.TestCase):
    def test_empty_candidates_preserve_primary_and_publish_explicit_scope(self):
        f=BaselineRunnerTests();f.setUp();self.addCleanup(f.doCleanups)
        path=f.root/'sync';path.mkdir()
        np.savez(path/'ping-slash24_joint.npz',interval_start_utc=np.array([],dtype=np.int64),candidate=np.array([],dtype=bool))
        entry=f.m.archive.fingerprint(path/'ping-slash24_joint.npz')
        (path/'manifest.json').write_text(json.dumps({'outputs':{'ping-slash24_joint.npz':entry}}))
        (path/'status.json').write_text('{"status":"completed"}')
        f.m=importlib.import_module('scripts.run_sync_baseline')
        summary=f.run_stage(sync=path,universe='joint');points=f.points()
        self.assertEqual(points['reference_exclusion_bits'][0].tolist(),[0,0,12,2,1,0,0,0])
        self.assertFalse(points['target_sync_candidate'].any())
        self.assertEqual(summary['sync_universe'],'joint')
        self.assertEqual(summary['confirmed_measurement_anomaly_exclusions'],0)

if __name__=='__main__':unittest.main()
