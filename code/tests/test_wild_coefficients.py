import unittest,importlib.util
import numpy as np
class WildTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.wild_coefficients'),'implementation missing')
        from scripts.wild_coefficients import draws
        return draws
    def test_explicit_refit(self):
        rng=np.random.default_rng(12);x=np.c_[np.ones(30),rng.normal(size=(30,2))];y=rng.normal(size=30);b=np.linalg.lstsq(x,y,rcond=None)[0];u=y-x@b;g=np.repeat(np.arange(3),10)
        d,s=self.api()(x,u,g)
        self.assertEqual(d.shape,(8,3));self.assertEqual(len(np.unique(s,axis=0)),8)
        for j in range(8):np.testing.assert_allclose(d[j],np.linalg.lstsq(x,u*s[j,g],rcond=None)[0],atol=1e-12)
    def test_seed(self):
        x=np.c_[np.ones(40),np.arange(40)];u=np.ones(40);g=list(range(40))
        a,s=self.api()(x,u,g);b,t=self.api()(x,u,g);np.testing.assert_array_equal(s,t);np.testing.assert_array_equal(a,b)
    def test_single_group(self):
        with self.assertRaises(ValueError):self.api()(np.eye(2),np.ones(2),[0,0])
