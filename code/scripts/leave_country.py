"""Deterministic country deletion; no geographic mapping or resampling."""
def samples(rows):
    if any(not isinstance(r.get('country_id'),str) or not r['country_id'] for r in rows):
        raise ValueError('Explicit nonempty country required')
    for country in sorted({r['country_id'] for r in rows}):
        yield country,[r for r in rows if r['country_id']!=country]
