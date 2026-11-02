import importlib.util
import pathlib
import unittest
import numpy as np

PATH=pathlib.Path(__file__).resolve().parents[1]/'scripts/heat_resilience_metrics.py'


class MetricsTests(unittest.TestCase):
    def load(self):
        self.assertTrue(PATH.exists(), 'metrics implementation missing')
        spec=importlib.util.spec_from_file_location('metrics',PATH)
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        return m

    def data(self, ratio=1):
        t=np.arange(0,96*3600+600,600,dtype=np.int64)
        return t,np.full(len(t),ratio,dtype=float),np.ones(len(t))

    def run_metric(self,t,v,b,**kwargs):
        return self.load().event_metrics(t,v,b,0,24*3600,**kwargs)

    def test_left_closed_right_open_zero_and_signed_deviation(self):
        t,v,b=self.data(.9); v[-1]=0
        r=self.run_metric(t,v,b)
        self.assertEqual(r['required_slots'],576)
        self.assertAlmostEqual(r['dhrd_hours'],9.6)
        self.assertAlmostEqual(r['signed_deviation_hours'],-9.6)
        self.assertAlmostEqual(r['mean_deficit'],.1)
        self.assertAlmostEqual(r['disruption_hours_full'],96)
        self.assertEqual(r['recovery']['status'],'right_censored_72h')
        self.assertEqual(r['recovery']['followup_hours'],72)
        v[:]=0; r=self.run_metric(t,v,b)
        self.assertAlmostEqual(r['dhrd_hours'],96)
        v[:]=1.1; r=self.run_metric(t,v,b)
        self.assertEqual(r['dhrd_hours'],0)
        self.assertAlmostEqual(r['signed_deviation_hours'],9.6)
        self.assertEqual(r['state'],'no_significant_deficit')
        self.assertIsNone(r['recovery']['confirmation_hours'])

    def test_missing_baseline_masks_and_absent_slots(self):
        t,v,b=self.data(.8); b[150]=np.nan
        r=self.run_metric(t,v,b)
        self.assertIsNone(r['dhrd_hours'])
        self.assertEqual(r['valid_slots'],575)
        self.assertAlmostEqual(r['peak_loss_core'],.2)
        self.assertEqual(r['state'],'insufficient_observation')
        self.assertEqual(r['recovery']['status'],'missingness_censored')
        self.assertEqual(r['recovery']['followup_hours'],1)
        r=self.run_metric(t[:150],v[:150],np.ones(150))
        self.assertEqual(r['recovery']['status'],'administrative_censored')
        self.assertEqual(r['recovery']['followup_hours'],1)
        r=self.run_metric(np.delete(t,150),np.delete(v,150),np.ones(len(t)-1))
        self.assertEqual(r['recovery']['status'],'missingness_censored')
        available=np.ones(len(t),dtype=bool); available[0]=False
        unknown=np.zeros(len(t),dtype=bool); unknown[1]=True
        r=self.run_metric(t,v,np.ones(len(t)),analysis_available=available,unknown_review=unknown)
        self.assertIsNone(r['maintenance_core'])
        self.assertEqual(r['unknown_review_slots'],1)
        self.assertFalse(r['recovery']['survival_eligible_from_core'])

    def test_recovery_confirmation_completion_and_recurrence(self):
        t,v,b=self.data(.8); v[144:]=.95; v[169]=.8
        r=self.run_metric(t,v,b)
        self.assertEqual(r['state'],'damaged_at_end')
        self.assertEqual(r['recovery']['confirmation_hours'],4)
        self.assertEqual(r['recovery']['segment_start_hours'],0)
        self.assertTrue(r['recovery']['recurrence_after_confirmation'])
        self.assertEqual(r['recovery']['status'],'confirmed')
        v[145]=.8; r=self.run_metric(t,v,b)
        self.assertAlmostEqual(r['recovery']['confirmation_hours'],(170+24-144)/6)
        b[145]=np.nan; r=self.run_metric(t,v,b)
        self.assertIsNone(r['recovery']['confirmation_hours'])
        self.assertEqual(r['recovery']['status'],'missingness_censored')

    def test_mutually_exclusive_core_states(self):
        t,v,b=self.data(1)
        v[144]=.8; self.assertEqual(self.run_metric(t,v,b)['state'],'delayed_onset')
        v[:]=1; v[0]=.8
        self.assertEqual(self.run_metric(t,v,b)['state'],'stable_recovered_before_end')
        v[130]=.8
        r=self.run_metric(t,v,b)
        self.assertEqual(r['state'],'awaiting_confirmation')
        self.assertFalse(r['recovery']['survival_eligible_from_core'])
        self.assertIsNone(r['recovery']['confirmation_hours'])
        self.assertAlmostEqual(r['recovery']['supplementary_confirmation_hours'],4)

    def test_grid_validation_and_baseline_output_adapter(self):
        m=self.load(); t,v,b=self.data()
        with self.assertRaises(ValueError): m.event_metrics(t,v,b,0,1)
        with self.assertRaises(ValueError): self.run_metric(t[::-1],v,b)
        with self.assertRaises(ValueError): self.run_metric(t,v,b,analysis_available=np.ones(len(t)))
        result=m.metrics_from_baseline(dict(target_timestamps=t,target_values=v,baseline=b,
                                           analysis_available=np.ones(len(t),dtype=bool)),0,86400)
        self.assertEqual(result['dhrd_hours'],0)

    def test_72h_confirmation_boundary_and_later_missingness(self):
        t,v,b=self.data(.8)
        v[552:576]=.95
        r=self.run_metric(t,v,b)
        self.assertEqual(r['recovery']['confirmation_hours'],72)
        self.assertEqual(r['recovery']['status'],'confirmed')
        v[552]=.8
        r=self.run_metric(t,v,b)
        self.assertEqual(r['recovery']['status'],'right_censored_72h')
        v[144:]=1; b[200]=np.nan
        r=self.run_metric(t,v,b)
        self.assertEqual(r['recovery']['confirmation_hours'],4)
        self.assertIsNone(r['recovery']['recurrence_after_confirmation'])
        self.assertIsNone(r['dhrd_hours'])
        self.assertEqual(r['state'],'insufficient_observation')

    def test_sensitivity_threshold_and_shorter_confirmation(self):
        t,v,b=self.data(.92)
        r=self.run_metric(t,v,b,maintenance_threshold=.9,confirmation_slots=12)
        self.assertEqual(r['specification'],'sensitivity')
        self.assertEqual(r['state'],'no_significant_deficit')
        self.assertAlmostEqual(r['dhrd_hours'],7.68)
        v[:144]=.8
        r=self.run_metric(t,v,b,maintenance_threshold=.9,confirmation_slots=12)
        self.assertEqual(r['recovery']['confirmation_hours'],2)
        t=np.array([],dtype=np.int64)
        r=self.run_metric(t,np.array([]),np.array([]))
        self.assertEqual(r['absent_slots'],576)
        self.assertIsNone(r['dhrd_hours'])
        self.assertEqual(r['recovery']['status'],'insufficient_core_observation')

    def test_recurrence_during_core_requires_prior_deficit_then_confirmed_recovery(self):
        t,v,b=self.data(1)
        v[0]=.8; v[25]=.8; v[143]=.8
        r=self.run_metric(t,v,b)
        self.assertEqual(r['state'],'damaged_at_end')
        self.assertIn('recurrence_during_core',r)
        self.assertTrue(r['recurrence_during_core'])
        v[:]=1; v[25]=.8; v[143]=.8
        self.assertTrue(self.run_metric(t,v,b)['recurrence_during_core'])
        v[:]=1; v[143]=.8
        self.assertFalse(self.run_metric(t,v,b)['recurrence_during_core'])
        v[:]=1; v[0]=.8; v[24:]=.8
        self.assertFalse(self.run_metric(t,v,b)['recurrence_during_core'])
        b[10]=np.nan
        self.assertIsNone(self.run_metric(t,v,b)['recurrence_during_core'])


if __name__=='__main__': unittest.main()
