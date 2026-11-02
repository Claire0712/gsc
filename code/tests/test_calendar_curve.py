import unittest,importlib.util
import numpy as np
from scipy import sparse
class CalendarTests(unittest.TestCase):
    def test_exact_date_dummies(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.calendar_curve'),'implementation missing')
        from scripts.calendar_curve import augment
        z=sparse.csr_matrix(np.ones((4,1)));a=augment(z,[86400,0,86400,172800]).toarray()
        np.testing.assert_array_equal(a[:,0],1);np.testing.assert_array_equal(a[:,-3:],[[0,1,0],[1,0,0],[0,1,0],[0,0,1]])
    def test_nonmidnight(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.calendar_curve'),'implementation missing')
        from scripts.calendar_curve import augment
        with self.assertRaises(ValueError):augment(sparse.eye(2),[0,600])
