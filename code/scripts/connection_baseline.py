"""Pure NumPy connection references, frozen to HeatSignal proposal §6.3.

Input is one audited country/signal series, labelled by integer Unix UTC seconds
on the 600-second interval-start lattice. Missing slots may be absent or NaN;
neither is interpolated. Native measurement phase consistency and full annual
coverage must be audited upstream; interval labels do not prove native phase.

Zero is a valid observation (as in prepare_ioda_quality); negatives/nonfinite
values are invalid. Positivity is required of the final reference median only.
Reference exclusions must combine ALL year-round Tmax cores plus 72h recovery,
STOP, cyclone and confirmed measurement anomaly masks. This module cannot
verify the provenance/completeness of those caller-supplied masks.

These functions do not qualify events, shorten windows, integrate DHRD, or
produce a causal counterfactual. All operations are in memory, without I/O.
"""

import numpy as np


RETROSPECTIVE_OFFSETS_DAYS = (-28, -21, -14, -7, 7, 14, 21, 28)
PAST_ONLY_OFFSETS_DAYS = (-28, -21, -14, -7)


def _timestamps(value, name):
    raw = np.asarray(value)
    if raw.ndim != 1 or raw.dtype.kind not in 'iu':
        raise ValueError(f'{name} must be a 1D integer UTC seconds array')
    # Leave enough room for exact weekly lookup without int64 wraparound.
    limit = np.iinfo(np.int64)
    margin = 28 * 86400
    if raw.size and (int(raw.min()) < limit.min + margin or int(raw.max()) > limit.max - margin):
        raise ValueError(f'{name} outside safe int64 timestamp range')
    result = raw.astype(np.int64, copy=False)
    if np.any(result % 600) or np.any(result[1:] <= result[:-1]):
        raise ValueError(f'{name} must be unique, increasing and aligned to UTC 600-second grid')
    return result


def _mask(value, size, name):
    result = np.asarray(value)
    if result.shape != (size,) or result.dtype.kind != 'b':
        raise ValueError(f'{name} must be a Boolean vector matching source timestamps')
    return result


def _lookup(timestamps, queries):
    """Return indices and presence separately; never snap to a nearby slot."""
    indices = np.searchsorted(timestamps, queries)
    present = indices < len(timestamps)
    if len(timestamps):
        indices = np.minimum(indices, len(timestamps) - 1)
        present &= timestamps[indices] == queries
    return indices, present


def _baseline(timestamps, values, reference_excluded, annual_eligible,
              target_timestamps, valid, offsets, require_both_sides, method):
    times = _timestamps(timestamps, 'timestamps')
    raw_values = np.asarray(values)
    if raw_values.shape != times.shape or raw_values.dtype.kind not in 'fiu':
        raise ValueError('values must be a real numeric vector matching source timestamps')
    values = raw_values.astype(np.float64, copy=False)
    excluded = _mask(reference_excluded, len(times), 'reference_excluded')
    annual = _mask(annual_eligible, len(times), 'annual_eligible')
    observed_valid = np.isfinite(values) & (values >= 0)
    if valid is not None:
        observed_valid &= _mask(valid, len(times), 'valid')
    targets = times if target_timestamps is None else _timestamps(target_timestamps, 'target_timestamps')
    offsets = np.asarray(offsets, dtype=np.int64)
    reference_indices, present = _lookup(times, targets[:, None] + offsets[None, :] * 86400)
    qualified = np.zeros(present.shape, dtype=bool)
    samples = np.full(present.shape, np.inf)
    if len(times):
        source_qualified = observed_valid & annual & ~excluded
        qualified = present & source_qualified[reference_indices]
        samples[qualified] = values[reference_indices[qualified]]
    counts = qualified.sum(axis=1)
    before = qualified[:, offsets < 0].sum(axis=1)
    after = qualified[:, offsets > 0].sum(axis=1)
    median = np.full(len(targets), np.nan)
    has_refs = counts > 0
    ordered = np.sort(samples[has_refs], axis=1)
    nonempty_counts = counts[has_refs]
    rows = np.arange(len(nonempty_counts))
    lo = ordered[rows, (nonempty_counts - 1) // 2]
    hi = ordered[rows, nonempty_counts // 2]
    # Nonnegative finite inputs allow this overflow-safe midpoint.
    median[has_refs] = lo + (hi - lo) / 2
    count_eligible = counts >= 4
    if require_both_sides:
        count_eligible &= (before >= 1) & (after >= 1)
    available = count_eligible & np.isfinite(median) & (median > 0)
    baseline = np.where(available, median, np.nan)

    target_indices, target_present = _lookup(times, targets)
    target_values = np.full(len(targets), np.nan)
    target_valid = np.zeros(len(targets), dtype=bool)
    target_annual = np.zeros(len(targets), dtype=bool)
    if len(times):
        target_values[target_present] = values[target_indices[target_present]]
        target_valid = target_present & observed_valid[target_indices]
        target_annual = target_present & annual[target_indices]
    return dict(method=method, target_timestamps=targets.copy(),
                reference_offsets_days=offsets.copy(), baseline=baseline,
                reference_median=median, reference_count=counts,
                before_count=before, after_count=after,
                reference_count_eligible=count_eligible,
                baseline_available=available, target_values=target_values,
                target_present=target_present, target_finite=np.isfinite(target_values),
                target_valid=target_valid, target_annual_eligible=target_annual,
                analysis_available=available & target_valid & target_annual)


def retrospective_baseline(timestamps, values, *, reference_excluded,
                           annual_eligible, target_timestamps=None, valid=None):
    """Return exact ±7/14/21/28-day medians and independent target diagnostics.

    ``annual_eligible`` qualifies each SOURCE slot's country/signal/year. Missing
    or failed annual records must map to False upstream. ``valid`` optionally
    excludes invalid observations in addition to finite/nonnegative checks.
    Reference exclusions affect candidate references only: a heat target itself
    must remain observable. Target exclusion/event eligibility is the caller's
    responsibility. ``analysis_available`` combines the target observation,
    target annual gate and baseline, not full event eligibility.

    At least four references, at least one on each side, and a positive median
    are mandatory. ``reference_median`` is diagnostic even when counts fail;
    only ``baseline`` is authorized for normalization. All arrays are aligned
    with the supplied target timestamps, or every source slot if omitted.
    """
    return _baseline(timestamps, values, reference_excluded, annual_eligible,
                     target_timestamps, valid, RETROSPECTIVE_OFFSETS_DAYS, True,
                     'retrospective_weekly_28day')


def past_only_28day_baseline(timestamps, values, *, reference_excluded,
                           annual_eligible, target_timestamps=None, valid=None):
    """Separate sensitivity using exact -7/-14/-21/-28 days, all four required.

    This freezes the main minimum-four rule for the past-only sensitivity;
    proposal §6.3 does not independently specify its minimum. No future-side
    requirement applies. Coverage must be reported separately, never substituted
    for missing retrospective references. Other rules match the main function.
    """
    return _baseline(timestamps, values, reference_excluded, annual_eligible,
                     target_timestamps, valid, PAST_ONLY_OFFSETS_DAYS, False,
                     'past_only_28day_sensitivity')
