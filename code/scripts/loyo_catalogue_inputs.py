"""Strict adapter for audited omitted-year thresholds and warm-season selection."""
import numpy as np
from .heat_catalogue_variants_core import warm_season


def loyo_inputs(thresholds, frame, omit):
    if omit not in range(2018, 2022):
        raise ValueError('Omit year must be one of 2018–2021')
    columns = [f'q90_{metric}_omit_{omit}_c' for metric in ('tmax', 'tmin')]
    if not {'calendar_day', *columns}.issubset(thresholds.columns):
        raise ValueError('Missing audited omitted-year threshold columns')
    if len(thresholds) != 365 or set(thresholds.calendar_day) != set(range(365)):
        raise ValueError('Exactly one threshold for each calendar day is required')
    selected = thresholds[['calendar_day', *columns]].copy()
    if not np.isfinite(selected[columns].to_numpy(float)).all():
        raise ValueError('Incomplete omitted-year threshold support')
    selected = selected.rename(columns={columns[0]: 'q90_tmax_c', columns[1]: 'q90_tmin_c'})
    remaining = frame.loc[frame.date.dt.year != omit]
    reference = remaining.loc[remaining.date.dt.year.between(2018, 2021)]
    if set(reference.date.dt.year) != set(range(2018, 2022)) - {omit}:
        raise ValueError('All three remaining reference years required')
    season = warm_season(remaining, months_count=3)
    return selected, {key: season[key] for key in (
        'warm_season_start_month', 'warm_season_mean_tmax_c', 'reference_valid_fraction')}
