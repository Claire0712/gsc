import unittest,importlib.util
import numpy as np
from scipy import sparse
class CurveTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.event_curve_core'),'implementation missing')
        from scripts.event_curve_core import fit
        return fit
    def data(self):
        rng=np.random.default_rng(45);n=120
        z=np.column_stack([np.ones(n),np.repeat(np.eye(6),20,axis=0),np.tile(np.eye(4),(30,1))])
        x=rng.normal(size=(n,3));w=rng.uniform(.2,2,n);y=x@np.array([.2,-.3,.7])+z@rng.normal(size=z.shape[1])+rng.normal(size=n)*.1
        return x,y,z,w
    def test_dense_equivalence(self):
        x,y,z,w=self.data();r=self.api()(x,y,sparse.csr_matrix(z),w)
        expected=np.linalg.lstsq(np.column_stack([x,z])*np.sqrt(w[:,None]),y*np.sqrt(w),rcond=None)[0][:3]
        np.testing.assert_allclose(r['beta'],expected,atol=1e-9)
    def test_orthogonality(self):
        x,y,z,w=self.data();r=self.api()(x,y,sparse.csr_matrix(z),w)
        np.testing.assert_allclose((z*np.sqrt(w[:,None])).T@r['residual'],0,atol=1e-8)
    def test_collinear_rejected(self):
        x,y,z,w=self.data();x[:,0]=1
        with self.assertRaises(ValueError):self.api()(x,y,sparse.csr_matrix(z),w)
    def test_bad_weights(self):
        x,y,z,w=self.data();w[0]=0
        with self.assertRaises(ValueError):self.api()(x,y,sparse.csr_matrix(z),w)
    def test_missing(self):
        x,y,z,w=self.data();y[0]=np.nan
        with self.assertRaises(ValueError):self.api()(x,y,sparse.csr_matrix(z),w)
