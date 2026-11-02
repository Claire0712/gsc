import unittest
import numpy as np
from scripts.cox_health_sensitivity import decisions
class HealthSensitivity(unittest.TestCase):
 def test_nested_policy_and_strict_eigen_boundary(self):
  b=np.zeros(2);c=np.eye(2);i=np.diag([1e-7,1.])
  d=decisions(b,np.array([5e-6,0]),c,i,[])
  self.assertFalse(d['strict']);self.assertTrue(d['main']);self.assertTrue(d['loose'])
  self.assertFalse(decisions(b,b,c,i,[])['strict'])
 def test_warning_nonfinite_and_negative_variance_rejected(self):
  b=np.zeros(2);c=np.eye(2)
  for score,cov,messages in [(b,c,['convergence warning']),(np.array([np.nan,0]),c,[]),(b,-c,[])]:
   self.assertFalse(any(decisions(b,score,cov,c,messages).values()))
