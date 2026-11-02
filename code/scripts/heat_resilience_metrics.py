"""Pure event metrics for HeatSignal proposal sections 6.4--6.6; no I/O.

Inputs are interval-start UTC Unix seconds on the 600-second lattice, matching
connection_baseline outputs. Core [start, end) includes caller-labelled bridge
days. The fixed main window is [start, end + 72h); never shorten or fill it.

Frozen operational choices (before effect estimation): core metrics require a
complete core; full metrics require the entire fixed window. Recovery scans
post-end intervals only; confirmation is at the END of the 24th qualifying
interval (earliest end + 4h). A missing slot stops primary followup permanently:
missing suffix beyond the supplied trace is administrative censoring; internal
gaps, invalid values/references or failed availability are missingness censoring.
No observed-only integral is returned. Unknown review flags are diagnostic,
never silently promoted to confirmed exclusions.

Full-window classification requires complete observation. Survival eligibility
is separately determined from a complete core ending below threshold, allowing
missing post-event followup to be censored rather than excluded. This reconciles
the proposal's class-3 condition with its explicit missing-followup censoring.
Awaiting-confirmation events receive a separate supplementary recovery record.
No-initial-deficit events never receive a zero-valued primary recovery time.
Core recurrence separately requires an observed deficit, a subsequent complete
confirmation run, and another core deficit. Initial healthy slots alone cannot
establish recovery. Incomplete core observation makes this diagnostic unknown.

Caller must establish annual eligibility, target exclusions, mask provenance,
event boundaries and native measurement phase upstream. Unknown review flags
do not certify eligibility or causality. 90%/98% thresholds and 2/6h confirmation
may be requested as separately labelled sensitivities; the main defaults are
95% and 24 slots. The 72h followup and 1/6h interval remain fixed.
"""

import numpy as np


def event_metrics(timestamps, values, baseline, event_start, event_end, *,
                  analysis_available=None, unknown_review=None,
                  maintenance_threshold=.95, confirmation_slots=24):
    """Return scalar event metrics, observation diagnostics, and recovery record.

    Missing scalar metrics are None. Values of zero are valid; negative or
    nonfinite observations and nonpositive/nonfinite references are invalid.
    Optional masks must be Boolean vectors aligned to supplied timestamps.
    ``analysis_available`` can be passed directly from connection_baseline.
    ``unknown_review`` preserves unresolved flags without changing availability.
    A confirmed recovery remains observed if later slots are missing, while its
    recurrence flag becomes None when later observation cannot establish it.
    """
    times=np.asarray(timestamps)
    if times.ndim != 1 or times.dtype.kind not in 'iu':
        raise ValueError('timestamps must be one-dimensional integer UTC seconds')
    bounds=np.iinfo(np.int64)
    if times.size and (int(times.min()) < bounds.min+259200 or int(times.max()) > bounds.max-259200):
        raise ValueError('timestamps outside safe int64 range')
    times=times.astype(np.int64,copy=False)
    if np.any(times % 600) or np.any(times[1:] <= times[:-1]):
        raise ValueError('timestamps must increase uniquely on UTC 600-second lattice')
    for endpoint in [event_start,event_end]:
        if isinstance(endpoint,(bool,np.bool_)) or not isinstance(endpoint,(int,np.integer)) or endpoint % 600:
            raise ValueError('event endpoints must be integer UTC 600-second lattice times')
        if endpoint < bounds.min+259200 or endpoint > bounds.max-259200:
            raise ValueError('event endpoints outside safe int64 range')
    if event_end <= event_start: raise ValueError('event_end must follow event_start')
    if not np.isfinite(maintenance_threshold) or not 0 < maintenance_threshold <= 1:
        raise ValueError('maintenance_threshold must be in (0,1]')
    if isinstance(confirmation_slots,(bool,np.bool_)) or not isinstance(confirmation_slots,(int,np.integer)) or not 1 <= confirmation_slots <= 432:
        raise ValueError('confirmation_slots must be an integer from 1 to 432')
    numeric=[]
    for array in [values,baseline]:
        a=np.asarray(array)
        if a.shape != times.shape or a.dtype.kind not in 'fiu': raise ValueError('values and baseline must match timestamps')
        numeric.append(a.astype(float,copy=False))
    values,baseline=numeric
    masks=[]
    for mask,default in [(analysis_available,True),(unknown_review,False)]:
        if mask is None: masks.append(np.full(len(times),default,dtype=bool))
        else:
            a=np.asarray(mask)
            if a.shape != times.shape or a.dtype.kind != 'b': raise ValueError('masks must be aligned Boolean vectors')
            masks.append(a)
    available,unknown=masks
    window=np.arange(event_start,event_end+259200,600,dtype=np.int64)
    ncore=(event_end-event_start)//600
    indices=np.searchsorted(times,window)
    present=indices < len(times)
    if len(times):
        indices=np.minimum(indices,len(times)-1)
        present &= times[indices] == window
    ratio=np.full(len(window),np.nan)
    observed=np.full(len(window),np.nan)
    reference=np.full(len(window),np.nan)
    gate=np.zeros(len(window),dtype=bool)
    flags=np.zeros(len(window),dtype=bool)
    if len(times):
        observed[present]=values[indices[present]]
        reference[present]=baseline[indices[present]]
        gate[present]=available[indices[present]]
        flags[present]=unknown[indices[present]]
    observed_valid=np.isfinite(observed)&(observed>=0)
    baseline_valid=np.isfinite(reference)&(reference>0)
    valid=present & observed_valid & baseline_valid & gate
    with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
        ratio[valid]=observed[valid]/reference[valid]
    valid &= np.isfinite(ratio)
    ratio[~valid]=np.nan
    signed=ratio-1
    deficit=np.maximum(0,-signed)
    above=ratio >= maintenance_threshold
    core_complete=bool(valid[:ncore].all())
    complete=bool(valid.all())
    recurrence_during_core=None
    if core_complete:
        recurrence_during_core=False
        prior_deficit=False
        recovered_after_deficit=False
        qualifying_run=0
        for qualifies in above[:ncore]:
            if not qualifies:
                if recovered_after_deficit:
                    recurrence_during_core=True
                    break
                prior_deficit=True
                qualifying_run=0
            elif prior_deficit:
                qualifying_run+=1
                if qualifying_run >= confirmation_slots:
                    recovered_after_deficit=True
    core_state='insufficient_observation'
    if core_complete:
        if above[:ncore].all(): core_state='no_core_deficit'
        elif not above[ncore-1]: core_state='damaged_at_end'
        elif ncore >= confirmation_slots and above[ncore-confirmation_slots:ncore].all():
            core_state='stable_recovered_before_end'
        else: core_state='awaiting_confirmation'
    state='insufficient_observation'
    if complete:
        state=core_state
        if core_state=='no_core_deficit':
            state='no_significant_deficit' if above[ncore:].all() else 'delayed_onset'
    recovery=dict(survival_eligible_from_core=core_state=='damaged_at_end',
                  status='not_applicable',confirmation_hours=None,segment_start_hours=None,
                  supplementary_confirmation_hours=None,supplementary_segment_start_hours=None,
                  supplementary_status=None,followup_hours=None,
                  last_observable_followup_hours=None,recurrence_after_confirmation=None)
    if core_state=='insufficient_observation': recovery['status']='insufficient_core_observation'
    elif core_state in ['damaged_at_end','awaiting_confirmation']:
        invalid_post=np.flatnonzero(~valid[ncore:])
        stop=int(invalid_post[0]) if len(invalid_post) else 432
        recovery['last_observable_followup_hours']=stop/6
        run=0; confirmation=None
        for offset in range(stop):
            run=run+1 if above[ncore+offset] else 0
            if run == confirmation_slots:
                confirmation=offset+1
                break
        if confirmation is not None:
            status='confirmed'
            confirmation_hours=confirmation/6
            segment_start=(confirmation-confirmation_slots)/6
            later=slice(ncore+confirmation,None)
            recurrence=bool((valid[later] & ~above[later]).any())
            if not recurrence and not valid[later].all(): recurrence=None
            recovery['recurrence_after_confirmation']=recurrence
            recovery['followup_hours']=confirmation_hours
        else:
            confirmation_hours=None; segment_start=None
            if stop == 432: status='right_censored_72h'
            elif not present[ncore+stop] and (not len(times) or window[ncore+stop] > times[-1]):
                status='administrative_censored'
            else: status='missingness_censored'
            recovery['followup_hours']=stop/6
        if core_state=='damaged_at_end':
            recovery.update(status=status,confirmation_hours=confirmation_hours,segment_start_hours=segment_start)
        else:
            recovery.update(supplementary_status=status,supplementary_confirmation_hours=confirmation_hours,
                            supplementary_segment_start_hours=segment_start)
    elif core_state=='stable_recovered_before_end':
        recurrence=bool((valid[ncore:] & ~above[ncore:]).any())
        recovery['recurrence_after_confirmation']=recurrence if recurrence or valid[ncore:].all() else None
    def summary(selection,eligible):
        if not eligible: return dict(mean_deficit=None,mean_signed_deviation=None,peak_loss=None,disruption_hours=None,maintenance=None)
        return dict(mean_deficit=float(deficit[selection].mean()),
                    mean_signed_deviation=float(signed[selection].mean()),
                    peak_loss=float(deficit[selection].max()),
                    disruption_hours=float(np.count_nonzero(~above[selection])/6),
                    maintenance=float(above[selection].mean()))
    core=summary(slice(0,ncore),core_complete)
    post=summary(slice(ncore,None),bool(valid[ncore:].all()))
    full=summary(slice(None),complete)
    return dict(event_start=int(event_start),event_end_exclusive=int(event_end),
                full_end_exclusive=int(event_end+259200),required_slots=len(window),core_required_slots=int(ncore),
                valid_slots=int(valid.sum()),coverage_fraction=float(valid.mean()),
                core_valid_slots=int(valid[:ncore].sum()),post_valid_slots=int(valid[ncore:].sum()),
                absent_slots=int((~present).sum()),invalid_observation_slots=int((present & ~observed_valid).sum()),
                invalid_baseline_slots=int((present & ~baseline_valid).sum()),unavailable_mask_slots=int((present & ~gate).sum()),
                unknown_review_slots=int(flags.sum()),core_complete=core_complete,full_window_complete=complete,
                dhrd_hours=float(deficit.sum()/6) if complete else None,
                signed_deviation_hours=float(signed.sum()/6) if complete else None,
                mean_deficit=full['mean_deficit'],mean_signed_deviation=full['mean_signed_deviation'],
                mean_deficit_core=core['mean_deficit'],mean_signed_deviation_core=core['mean_signed_deviation'],
                maintenance_core=core['maintenance'],peak_loss_core=core['peak_loss'],peak_loss_full=full['peak_loss'],
                disruption_hours_core=core['disruption_hours'],disruption_hours_post=post['disruption_hours'],
                disruption_hours_full=full['disruption_hours'],state=state,core_end_state=core_state,recovery=recovery,
                recurrence_during_core=recurrence_during_core,
                maintenance_threshold=float(maintenance_threshold),confirmation_slots=int(confirmation_slots),
                specification='main' if maintenance_threshold==.95 and confirmation_slots==24 else 'sensitivity')


def metrics_from_baseline(result,event_start,event_end,**kwargs):
    """Consume one connection_baseline result without recomputing references."""
    return event_metrics(result['target_timestamps'],result['target_values'],result['baseline'],
                         event_start,event_end,analysis_available=result['analysis_available'],**kwargs)
