import unittest

class RecoveryDefinitionRunnerTest(unittest.TestCase):
    def test_all_definitions_confirm_after_exact_required_run(self):
        import tempfile,json
        import numpy as np
        from pathlib import Path
        from tests.test_heat_resilience_metrics_runner import RunnerTests
        from scripts.run_recovery_definition_metrics import run
        for threshold,slots in ((.9,24),(.98,24),(.95,12),(.95,36)):
            with tempfile.TemporaryDirectory() as temp:
                source=Path(temp)/'source';out=Path(temp)/'out';fixture=RunnerTests()
                fixture.fixture(source);path=source/'points_000000_bgp.npz'
                with np.load(path,allow_pickle=False) as z:arrays={k:z[k] for k in z.files}
                arrays['target_values']=np.r_[np.full(144,.8),np.ones(432)]
                np.savez(path,**arrays);fixture.manifest(source)
                run(source,out,maintenance_threshold=threshold,confirmation_slots=slots)
                m=json.loads((out/'event_metrics.json').read_text())[0]['metrics']
                self.assertTrue(m['recovery']['survival_eligible_from_core'])
                self.assertEqual(m['recovery']['confirmation_hours'],slots/6)
                self.assertAlmostEqual(m['dhrd_hours'],4.8)

    def test_threshold_reaches_metrics(self):
        import tempfile,json
        from pathlib import Path
        from tests.test_heat_resilience_metrics_runner import RunnerTests
        from scripts.run_recovery_definition_metrics import run
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source';out=Path(temp)/'out'
            RunnerTests().fixture(source)
            result=run(source,out,maintenance_threshold=.9,confirmation_slots=24)
            metric=json.loads((out/'event_metrics.json').read_text())[0]['metrics']
            self.assertEqual(metric['maintenance_threshold'],.9)
            self.assertEqual(metric['state'],'no_significant_deficit')
            self.assertEqual(result['confirmation_slots'],24)

    def test_explicit_preselected_definitions(self):
        from scripts.run_recovery_definition_metrics import validate_definition
        for threshold,slots in ((.9,24),(.98,24),(.95,12),(.95,36)):
            validate_definition(threshold,slots)
        for threshold,slots in ((.92,24),(.95,18),(.9,12)):
            with self.assertRaises(ValueError):validate_definition(threshold,slots)

if __name__=='__main__':unittest.main()
