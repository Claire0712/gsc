"""Keep risk-set membership independent of future confounds/completeness."""
import numpy as np
from .heat_resilience_metrics import event_metrics
from .run_recovery_definition_metrics import validate_definition

def qualify(arrays,start,end,threshold,slots):
    validate_definition(threshold,slots)
    t=arrays['target_timestamps'];bits=arrays['target_exclusion_bits']
    clean=arrays['analysis_available'] & ((bits&30)==0)
    core=t<end
    m=event_metrics(t,arrays['target_values'],arrays['baseline'],start,end,analysis_available=clean,
                    maintenance_threshold=threshold,confirmation_slots=slots)
    eligible=bool(m['core_complete'] and m['core_end_state']=='damaged_at_end')
    cause=None;rec=m['recovery']
    if eligible and rec['status']=='missingness_censored':
        at=end+int(round(rec['followup_hours']*3600));i=np.searchsorted(t,at)
        if i<len(t) and t[i]==at:
            b=int(bits[i]);reasons=[name for flag,name in [(2,'stop_candidate'),(4,'cyclone_candidate'),(8,'uncertain_cyclone_edge'),(16,'unknown_mask_coverage')] if b&flag]
            cause=';'.join(reasons) if reasons else 'observation_or_reference_missing'
        else:cause='absent_internal_timestamp'
    return dict(risk_eligible=eligible,core_confounded_slots=int(np.count_nonzero(bits[core]&30)),recovery=rec,censor_cause=cause,core_state=m['core_end_state'],full_window_clean_complete=m['full_window_complete'])
