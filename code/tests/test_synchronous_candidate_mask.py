import unittest
import numpy as np

class SynchronousCandidateMaskTest(unittest.TestCase):
    def test_exact_labels_arbitrary_query_shape_no_expansion(self):
        from scripts.synchronous_candidate_mask import candidate_mask
        t=np.array([0,600,1200],dtype=np.int64);flags=np.array([False,True,False])
        q=np.array([[0,599,600],[601,1200,1800]],dtype=np.int64)
        np.testing.assert_array_equal(candidate_mask(q,t,flags),[[False,False,True],[False,False,False]])
        for bad in (t[::-1],np.array([0,600,600])):
            with self.assertRaises(ValueError):candidate_mask(q,bad,flags)
        with self.assertRaises(ValueError):candidate_mask(q,t,np.array([0,1,0]))
        with self.assertRaises(ValueError):candidate_mask(q,t,flags[:2])
        self.assertFalse(candidate_mask(q,np.array([],dtype=np.int64),np.array([],dtype=bool)).any())

if __name__=='__main__':unittest.main()
