"""First weather event in a fixed three-month season; left truncation unknown."""
from datetime import date

def season_year(start,month):
    d=date.fromisoformat(start);month=int(month)
    if not 1<=month<=12:raise ValueError('Invalid season month')
    if (d.month-month)%12>=3:return None
    return d.year-int(d.month<month)

def first_events(rows,coverage_start='2022-01-01'):
    boundary=date.fromisoformat(coverage_start);groups={};result={}
    for r in rows:
        eid=r['event_id']
        if eid in result:raise ValueError('Duplicate weather event')
        sy=season_year(r['start_date'],r['warm_season_start_month'])
        result[eid]=dict(season_start_year=sy,first_warm_season_event=None,status='outside_warm_season')
        if sy is not None:groups.setdefault((r['country_id'],sy),[]).append(r)
    for (_,sy),rr in groups.items():
        months={int(r['warm_season_start_month']) for r in rr}
        if len(months)!=1:raise ValueError('Inconsistent fixed warm season')
        truncated=date(sy,months.pop(),1)<boundary
        earliest=min(r['start_date'] for r in rr)
        for r in rr:
            result[r['event_id']].update(first_warm_season_event=None if truncated else r['start_date']==earliest,
                status='left_truncated_season' if truncated else 'observed_weather_catalogue')
    return result
