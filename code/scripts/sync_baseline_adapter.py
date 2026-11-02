"""Source-and-target candidate sensitivity, preserving raw observations."""
import numpy as np
from .connection_baseline import retrospective_baseline,RETROSPECTIVE_OFFSETS_DAYS
from .synchronous_candidate_mask import candidate_mask

def remasked_baseline(times,values,reference_excluded,annual_eligible,targets,screen_times,flags):
    excluded=candidate_mask(times,screen_times,flags)
    # Isolated computational view only; caller-owned raw arrays stay unchanged.
    view=np.asarray(values,dtype=float).copy();view[excluded]=np.nan
    result=retrospective_baseline(times,view,
        reference_excluded=np.asarray(reference_excluded)|excluded,
        annual_eligible=annual_eligible,target_timestamps=targets)
    indices=np.searchsorted(times,targets);present=indices<len(times)
    if len(times):present &= np.asarray(times)[np.minimum(indices,len(times)-1)]==targets
    raw=np.full(np.asarray(targets).shape,np.nan)
    raw[present]=np.asarray(values)[indices[present]]
    queries=np.asarray(targets)[:,None]+np.array(RETROSPECTIVE_OFFSETS_DAYS)[None,:]*86400
    result.update(raw_target_values=raw,target_sync_candidate=candidate_mask(targets,screen_times,flags),
                  reference_sync_candidate=candidate_mask(queries,screen_times,flags))
    return result
