"""Pure synchronous-anomaly diagnostics; never creates exclusion flags.

Rows are UTC slots; columns are entities. The caller must align the previous
day and combine both days' annual eligibility with the selected universe.
"""
import numpy as np


def annual_mask(times, country_ids, coverage, universe):
    """Build single-signal annual eligibility using integer 5*valid >= 4*expected.

    coverage keys are (ISO2, year), values are (valid_points, expected_points).
    Missing rows fail closed rather than being silently treated as ineligible.
    """
    times = np.asarray(times)
    countries = list(country_ids)
    if (times.ndim != 1 or not np.issubdtype(times.dtype, np.integer)
            or len(countries) != len(set(countries))
            or not set(universe).issubset(countries)):
        raise ValueError('Invalid times, duplicate entities, or unknown universe entity')
    years = times.astype('datetime64[s]').astype('datetime64[Y]').astype(int) + 1970
    result = np.zeros((len(times), len(countries)), dtype=bool)
    for year in np.unique(years):
        for j, country in enumerate(countries):
            key = (country, int(year))
            if key not in coverage:
                raise ValueError(f'Missing annual coverage: {key}')
            valid, expected = coverage[key]
            if (type(valid) is not int or type(expected) is not int
                    or expected <= 0 or not 0 <= valid <= expected):
                raise ValueError(f'Invalid annual counts: {key}')
            result[years == year, j] = country in universe and valid * 5 >= expected * 4
    return result


def align_previous_day(times, values, annual_eligible):
    """Pair exact UTC seconds, permitting gaps but never positional shifting.

    Callers concatenate chronological quarter chunks (or include the prior
    day's tail). Missing predecessor times are returned separately from the
    paired eligibility mask, so boundary absence is not annual ineligibility.
    """
    times = np.asarray(times)
    values = np.asarray(values, dtype=float)
    annual_eligible = np.asarray(annual_eligible)
    if (times.ndim != 1 or not np.issubdtype(times.dtype, np.integer)
            or values.ndim != 2 or len(times) != len(values)
            or values.shape != annual_eligible.shape
            or annual_eligible.dtype != np.dtype(bool)):
        raise ValueError('Require integer UTC seconds and aligned values/boolean eligibility')
    if np.any(times < 86400) or np.any(times % 600) or np.any(np.diff(times) <= 0):
        raise ValueError('Times must be increasing unique 10-minute UTC slots after epoch day one')
    previous = np.full_like(values, np.nan)
    paired = np.zeros_like(annual_eligible)
    found = np.zeros(len(times), dtype=bool)
    if not len(times):
        return previous, paired, found
    targets = times - 86400
    index = np.searchsorted(times, targets)
    safe = np.minimum(index, len(times) - 1)
    found = (index < len(times)) & (times[safe] == targets)
    previous[found] = values[index[found]]
    paired[found] = annual_eligible[found] & annual_eligible[index[found]]
    return previous, paired, found


def paired_counts(current, previous, eligible):
    current = np.asarray(current, dtype=float)
    previous = np.asarray(previous, dtype=float)
    eligible = np.asarray(eligible)
    if current.ndim != 2 or current.shape != previous.shape or current.shape != eligible.shape:
        raise ValueError('Require identically shaped slot-by-entity arrays')
    if eligible.dtype != np.dtype(bool):
        raise ValueError('Eligibility must be boolean')
    if np.any(current < 0) or np.any(previous < 0):
        raise ValueError('Negative connection values require upstream review')
    finite = np.isfinite(current) & np.isfinite(previous)
    valid = eligible & finite & (previous > 0)
    # Compare the difference, avoiding the rounded ratio at exactly 20%.
    drop = valid & ((previous - current) > previous * .2)
    denominator = valid.sum(axis=1)
    numerator = drop.sum(axis=1)
    fraction = np.full(denominator.shape, np.nan, dtype=float)
    np.divide(numerator, denominator, out=fraction, where=denominator > 0)
    return dict(denominator=denominator, numerator=numerator, fraction=fraction,
                previous_zero=(eligible & finite & (previous == 0)).sum(axis=1),
                missing_pair=(eligible & ~finite).sum(axis=1),
                annual_ineligible=(~eligible).sum(axis=1))


def candidate_flags(fractions):
    fractions = np.asarray(fractions, dtype=float)
    valid = np.isfinite(fractions)
    threshold = float(np.quantile(fractions[valid], .999, method='linear')) if valid.any() else float('nan')
    return threshold, valid & (fractions > threshold)
