"""Frozen nested numerical policies, independent of effect direction."""
import numpy as np
POLICIES={'strict':(1e-6,1e-7,1e9),'main':(1e-5,1e-8,1e10),'loose':(1e-4,1e-9,1e11)}
def decisions(beta,score,cov,information,messages):
 bad=any('converg' in str(m).lower() for m in messages) or not all(np.isfinite(a).all() for a in (beta,score,cov,information))
 if bad or np.any(np.diag(cov)<0):return {k:False for k in POLICIES}
 ev=np.linalg.eigvalsh((information+information.T)/2)
 return {k:bool(np.max(np.abs(score))<=s and ev[0]>e and ev[-1]/ev[0]<=c) for k,(s,e,c) in POLICIES.items()}
