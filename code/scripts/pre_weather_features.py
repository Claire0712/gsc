"""Outcome-blind seven-day weather summaries; caller certifies input provenance.

Only [start-7 UTC days,start) is used. No imputation or matching is performed.
Each variable requires all seven finite values; zero/negative Celsius is valid.
This pure function does not certify population weights, units or source hashes.
"""
from datetime import date,timedelta
import math


def pre_weather_features(rows,country_id,start_date):
    start=date.fromisoformat(start_date)
    if start.isoformat()!=start_date:raise ValueError('Expected ISO calendar date')
    expected={(start-timedelta(days=i)).isoformat() for i in range(1,8)}
    selected={}
    for row in rows:
        if row['country_id']!=country_id or row['date'] not in expected:continue
        if row['date'] in selected:raise ValueError('Duplicate country/date in preperiod')
        selected[row['date']]=row
    result=dict(country_id=country_id,start_date=start_date,
                preperiod_start=(start-timedelta(days=7)).isoformat(),
                dates_present=len(selected),required_days=7)
    counts={}
    for source,target in [('tmax_c','tmax_mean_c'),('tmin_c','tmin_mean_c'),('dewpoint_c','dewpoint_mean_c')]:
        values=[]
        for day in sorted(selected):
            value=selected[day].get(source)
            if value is None or value=='':continue
            try:value=float(value)
            except (TypeError,ValueError) as exc:raise ValueError('Invalid weather value: '+source) from exc
            if math.isfinite(value):values.append(value)
        counts[source]=len(values)
        result[target]=math.fsum(values)/7 if len(values)==7 else None
    result.update(valid_days=counts,complete=all(n==7 for n in counts.values()))
    return result
