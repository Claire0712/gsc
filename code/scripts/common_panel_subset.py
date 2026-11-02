"""Reuse frozen three-signal membership; no metric/model modification."""
from .common_signal_summary import select

def subset(rows, mode):
    if mode not in ('clean', 'matched'):
        raise ValueError('Common subset must be clean or matched')
    return select(rows, matched=mode=='matched')
