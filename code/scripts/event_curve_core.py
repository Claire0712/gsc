"""Weighted sparse nuisance projection; point estimates, not inference."""
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import lsqr

def fit(x,y,nuisance,weights):
    x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float);w=np.asarray(weights,dtype=float)
    z=sparse.csr_matrix(nuisance,dtype=float)
    if x.ndim!=2 or y.ndim!=1 or w.shape!=y.shape or x.shape[0]!=len(y) or z.shape[0]!=len(y):raise ValueError('Misaligned model arrays')
    if not x.shape[1] or not z.shape[1] or not len(y):raise ValueError('Empty design')
    if any(not np.isfinite(a).all() for a in (x,y,w,z.data)) or np.any(w<=0):raise ValueError('Finite inputs and positive weights required')
    root=np.sqrt(w);a=z.multiply(root[:,None]).tocsr();v=np.column_stack([y,x])*root[:,None]
    projected=np.empty_like(v);diagnostics=[]
    anorm=float(np.sqrt(a.multiply(a).sum()))
    for j in range(v.shape[1]):
        result=lsqr(a,v[:,j],atol=1e-12,btol=1e-12,iter_lim=20000,conlim=1e14)
        if result[1] not in (0,1,2,4,5):raise ValueError('Nuisance projection did not converge')
        r=v[:,j]-a@result[0]
        error=float(np.linalg.norm(a.T@r))/(max(1.,anorm)*max(1.,float(np.linalg.norm(v[:,j]))))
        if error>1e-9:raise ValueError('Projection orthogonality failed')
        projected[:,j]=r;diagnostics.append(dict(iterations=int(result[2]),stop=int(result[1]),normal_error=error))
    yy=projected[:,0];xx=projected[:,1:];norms=np.linalg.norm(xx,axis=0)
    if np.any(norms<1e-9*np.maximum(1,np.linalg.norm(v[:,1:],axis=0))):raise ValueError('Absorbed focal column')
    scaled=xx/norms;singular=np.linalg.svd(scaled,compute_uv=False)
    if singular[-1]/singular[0]<1e-9:raise ValueError('Focal design rank deficient')
    beta=np.linalg.lstsq(scaled,yy,rcond=1e-9)[0]/norms
    return dict(beta=beta,residual=yy-xx@beta,residualized_x=xx,projection=diagnostics,condition=float(singular[0]/singular[-1]))
