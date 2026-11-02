"""Exact identity-only replacement of descriptive metrics, retaining covariates."""
def combine(panel,metrics):
    index={}
    for row in metrics:
        key=row['event_id'],row['signal']
        if key in index:raise ValueError('Duplicate replacement event/signal')
        index[key]=row
    result=[];seen=set()
    for row in panel:
        key=row['event_id'],row['signal']
        if key in seen or key not in index:raise ValueError('Duplicate or missing panel event/signal')
        seen.add(key);replacement=index[key]
        for field in ('country_id','source_point_file'):
            if row[field]!=replacement[field]:raise ValueError('Metric identity mismatch: '+field)
        result.append(dict(row,metrics=replacement['metrics']))
    if seen!=set(index):raise ValueError('Unaccounted replacement event/signal')
    return result
