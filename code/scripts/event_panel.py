"""Exact event exposure join; preserve technical eligibility and censoring."""
import math
from datetime import datetime, timezone

EXPOSURES=('span_days','hot_days','bridge_days','hd_c_days','mean_hot_excess_c','peak_excess_c','absolute_tmax_c','ntrd_c_days','dewpoint_mean_c')

def utc(text):
    return int(datetime.fromisoformat(text.replace('Z','+00:00')).replace(tzinfo=timezone.utc).timestamp())

def build(records,catalogue,matched):
    lookup={r['event_id']:r for r in catalogue}
    if len(lookup)!=len(catalogue):raise ValueError('Duplicate catalogue event')
    seen=set();result=[]
    for r in records:
        key=r['event_id'],r['signal']
        if key in seen:raise ValueError('Duplicate event-signal')
        seen.add(key);h=lookup[r['event_id']];m=r['metrics'];rec=m['recovery']
        if h['country_id']!=r['country_id'] or utc(h['start_date'])!=m['event_start'] or utc(h['end_exclusive_utc'])!=m['event_end_exclusive']:raise ValueError('Event identity/bounds mismatch')
        exposure={k:float(h[k]) for k in EXPOSURES}
        if not all(math.isfinite(v) for v in exposure.values()):raise ValueError('Missing exposure')
        if exposure['span_days']!=exposure['hot_days']+exposure['bridge_days'] or exposure['span_days']!=(m['event_end_exclusive']-m['event_start'])/86400:raise ValueError('Span decomposition mismatch')
        if not math.isclose(exposure['hd_c_days'],exposure['hot_days']*exposure['mean_hot_excess_c'],rel_tol=1e-8,abs_tol=1e-8):raise ValueError('HD identity mismatch')
        eligible=m['core_complete'] and m['core_end_state']=='damaged_at_end'
        if rec['survival_eligible_from_core']!=eligible:raise ValueError('Recovery risk-set mismatch')
        duration=None;observed=None
        if eligible:
            if rec['status'] not in ('confirmed','right_censored_72h','administrative_censored','missingness_censored'):raise ValueError('Invalid recovery status')
            duration=rec['followup_hours'];observed=rec['status']=='confirmed'
            if duration is None or not math.isfinite(duration) or not 0<=duration<=72:raise ValueError('Invalid followup')
            if observed and (duration<4 or duration!=rec['confirmation_hours']):raise ValueError('Invalid recovery confirmation')
        result.append(dict(r,exposure=exposure,year_month=h['start_date'][:7],matched_integral=key in matched,survival_time_hours=duration,recovery_observed=observed,positive_followup=duration is not None and duration>0))
    return result
