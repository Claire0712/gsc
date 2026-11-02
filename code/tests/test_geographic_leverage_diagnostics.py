import unittest,json
import numpy as np
from scripts.geographic_leverage_diagnostics import diagnostics
class DiagnosticsTest(unittest.TestCase):
 def test_numpy_counts_export_as_finite_json_and_retain_singletons(self):
  x=np.array([[1.,0.],[2.,1.],[1.,1.],[2.,0.],[3.,2.]])
  z=np.array([[1.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,1.,0.],[0.,0.,1.]])
  r=diagnostics(x,z,np.array(['A','A','B','B','C']),{'A'})
  json.dumps(r,allow_nan=False);self.assertEqual(r['singleton_countries'],1);self.assertEqual(r['countries'],3);self.assertGreaterEqual(r['hat_diagonal_near_one'],1)
if __name__=='__main__':unittest.main()

class QualificationTest(unittest.TestCase):
 def test_three_informative_comparator_countries_do_not_inherit_fifty_one_raw_clusters(self):
  from scripts.geographic_leverage_diagnostics import comparison_qualification
  q=comparison_qualification(dict(interaction_residual_information_region_countries=13,interaction_residual_information_other_countries=3))
  self.assertFalse(q['qualified']);self.assertIn('5',q['reason'])
  self.assertTrue(comparison_qualification(dict(interaction_residual_information_region_countries=5,interaction_residual_information_other_countries=5))['qualified'])
