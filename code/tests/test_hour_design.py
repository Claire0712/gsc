import unittest,importlib.util
import numpy as np
class HourDesignTests(unittest.TestCase):
 def test_hour_weekday_effects_and_repeated_focal(self):
  self.assertIsNotNone(importlib.util.find_spec('scripts.run_hour_curve'),'hour runner missing')
  from scripts.run_hour_curve import design
  rows=[dict(group_id='g',window_id='w',country_id='AA',date_utc='0',relative_day='0',role='heat')]
  x,z,w=design(rows,np.array([[1.,2.]]),np.array([.25]))
  np.testing.assert_array_equal(x,np.tile([1.,2.],(24,1)))
  np.testing.assert_array_equal(w,np.full(24,1.5))
  self.assertEqual(z.shape,(24,27))
  np.testing.assert_array_equal(z.sum(axis=1),np.full((24,1),4))
  self.assertEqual((z[0]!=z[1]).nnz,2)
