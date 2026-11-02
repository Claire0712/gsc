"""Exact candidate-label sensitivity mask; not an outage/fault classifier."""
import numpy as np


def candidate_mask(queries,timestamps,candidate):
    q=np.asarray(queries);t=np.asarray(timestamps);c=np.asarray(candidate)
    if q.dtype.kind not in 'iu' or t.dtype.kind not in 'iu':
        raise ValueError('Integer UTC labels required')
    if t.ndim!=1 or c.shape!=t.shape or c.dtype.kind!='b':
        raise ValueError('One-dimensional timestamps and Boolean candidate flags required')
    if len(t)>1 and np.any(t[1:]<=t[:-1]):
        raise ValueError('Unique increasing screen labels required')
    selected=t[c]
    if not len(selected):return np.zeros(q.shape,dtype=bool)
    indices=np.searchsorted(selected,q)
    return (indices<len(selected)) & (selected[np.minimum(indices,len(selected)-1)]==q)
