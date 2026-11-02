"""Explicit archived cyclone scenarios; no storm-free inference at calendar edges."""
import numpy as np
from . import run_connection_baseline as primary


def coverage_bounds(hours):
    if hours not in (24,72):
        raise ValueError('Unsupported cyclone half width')
    delta=(hours-24)*3600
    return primary.CYCLONE_COMPLETE_START+delta,primary.CYCLONE_COMPLETE_END-delta


def select_windows(rows,country,radius,hours):
    if radius not in (100,300,500):
        raise ValueError('Unsupported cyclone radius')
    coverage_bounds(hours)
    conservative,known=[],[]
    for row in rows:
        if row['country']!=country:
            raise ValueError('Cyclone window country mismatch')
        if row['radius_km']==radius and row['half_width_hours']==hours:
            if row['mode'] not in ('conservative','known'):
                raise ValueError('Unknown cyclone mode')
            window=(row['start_utc_seconds'],row['end_utc_seconds'])
            primary.interval_mask(np.array([],dtype=np.int64),[window],closed=True)
            (conservative if row['mode']=='conservative' else known).append(window)
    return conservative,known


def masks(stamps,heat,stop,cyclone,known,hours):
    start,end=coverage_bounds(hours)
    bits=primary.masks(stamps,heat,stop,cyclone,known)
    bits[(stamps<start)|(stamps>=end)] |= 16
    return bits
