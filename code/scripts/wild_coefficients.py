import numpy as np
def draws(x,u,groups):
    x=np.asarray(x,dtype=float);u=np.asarray(u,dtype=float)
    labels=sorted(set(groups));g=len(labels)
    if g<2 or len(groups)!=len(x) or u.shape!=(len(x),) or not np.isfinite(x).all() or not np.isfinite(u).all():raise ValueError('Invalid clustered inputs')
    index={label:j for j,label in enumerate(labels)};scores=np.zeros((g,x.shape[1]))
    np.add.at(scores,[index[a] for a in groups],x*u[:,None])
    influence=np.linalg.solve(x.T@x,scores.T).T
    if g<=16:signs=(((np.arange(2**g,dtype=np.uint32)[:,None]>>np.arange(g))&1)*2).astype(np.int8)-1
    else:signs=np.random.default_rng(20261013).choice(np.array([-1,1],dtype=np.int8),size=(9999,g))
    return signs@influence,signs
