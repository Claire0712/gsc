import unittest
import numpy as np
from scripts.modifier_models import support_mask

class ModifierModels(unittest.TestCase):
    def test_range_intersection_excludes_nonoverlap(self):
        mask,bounds=support_mask(np.array([[0],[2],[3],[5.]]),np.array([0,0,1,1]))
        self.assertFalse(mask.any())
        self.assertEqual(bounds,[(3.,2.)])
    def test_overlap_keeps_both_groups(self):
        mask,_=support_mask(np.array([[0],[2],[1],[3.]]),np.array([0,0,1,1]))
        np.testing.assert_array_equal(mask,[False,True,True,False])
    def test_missing_group_rejected(self):
        with self.assertRaises(ValueError):support_mask(np.ones((2,1)),np.zeros(2))
