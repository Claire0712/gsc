import unittest
import numpy as np
from scipy.optimize import check_grad
from statsmodels.duration.hazard_regression import PHReg
from scripts.recovery_cox import objective

class CoxTest(unittest.TestCase):
    def test_tied_likelihood_and_gradient(self):
        x=np.array([[0.,1],[1,0],[2,1],[-1,0],[.5,2]]);t=np.array([4,4,8,9,12.]);d=np.array([1,1,0,1,0]);b=np.array([.1,-.2])
        self.assertAlmostEqual(objective(b,x,t,d)[0],-PHReg(t,x,status=d,ties='breslow').loglike(b))
        self.assertLess(check_grad(lambda v:objective(v,x,t,d)[0],lambda v:objective(v,x,t,d)[1],b),1e-6)
        bb=np.r_[b,[.05,-.02]]
        self.assertLess(check_grad(lambda v:objective(v,x,t,d,True)[0],lambda v:objective(v,x,t,d,True)[1],bb),1e-6)

if __name__=='__main__':unittest.main()
