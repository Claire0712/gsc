"""Conservative numerical estimability checks on standardized Cox covariates."""
import numpy as np

def assess(beta,score,cov,information,messages):
    if any('converg' in str(m).lower() for m in messages):return 'Optimizer convergence warning'
    if not all(np.isfinite(a).all() for a in (beta,score,cov,information)):return 'Nonfinite fit, covariance or information'
    if np.linalg.norm(score,np.inf)>1e-5:return 'Score tolerance failed'
    if np.any(np.diag(cov)<0):return 'Negative covariance diagonal'
    ev=np.linalg.eigvalsh((information+information.T)/2)
    if ev[0]<=1e-8 or ev[-1]/ev[0]>1e10:return 'Degenerate standardized information'
    return None
