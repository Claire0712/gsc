"""Conservative spatial prefilter and closed UTC windows; not cyclone hits.

WGS84 meridional/prime-vertical curvature radii exceed 6,335 km.
Thus an ellipsoidal distance ball is enclosed by this smaller-sphere ball.
Boxes are ONLY candidates: polygon distance still requires verification.
"""
import math
from numbers import Real, Integral


def candidate_boxes(lon, lat, radius_m):
    """Return inclusive lon/lat boxes enclosing a WGS84 distance ball."""
    for value in (lon, lat, radius_m):
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError('Finite numeric coordinates and radius required')
    if not -90 <= lat <= 90 or radius_m < 0:
        raise ValueError('Invalid latitude or negative radius')
    lon = (lon + 180) % 360 - 180
    angle = radius_m / 6335000.0
    extent = math.degrees(angle)
    south, north = max(-90, lat-extent), min(90, lat+extent)
    if south == -90 or north == 90:
        return [(-180, south, 180, north)]
    width = math.degrees(math.asin(min(1, math.sin(angle)/math.cos(math.radians(lat)))))
    west, east = lon-width, lon+width
    if west < -180:
        return [(-180, south, east, north), (west+360, south, 180, north)]
    if east > 180:
        return [(west, south, 180, north), (-180, south, east-360, north)]
    return [(west, south, east, north)]


def merge_point_windows(times, half_width_seconds):
    """Merge inclusive integer-second windows, including touching endpoints."""
    if isinstance(half_width_seconds, bool) or not isinstance(half_width_seconds, Integral) or half_width_seconds < 0:
        raise ValueError('Nonnegative integer window width required')
    times = list(times)
    if any(isinstance(t, bool) or not isinstance(t, Integral) for t in times):
        raise ValueError('UTC timestamps must be integer seconds')
    merged = []
    width = int(half_width_seconds)
    for t in sorted(map(int, times)):
        start, end = t-width, t+width
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged
