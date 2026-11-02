"""Target-window scenario exclusions only; no inferred dates or reference remasking."""
def apply_scenario(windows,reviews,scenario):
    if scenario not in ('unknown_end_plusminus7','unknown_end_plusminus30'):raise ValueError('Unknown scenario')
    index={r['window_id']:r for r in reviews}
    if len(index)!=len(reviews):raise ValueError('Duplicate window review')
    result=[]
    for row in windows:
        if row['window_id'] not in index:raise ValueError('Missing window review')
        overlap=index[row['window_id']]['overlaps'];new=dict(row)
        blocked=bool(overlap['preperiod'][scenario] or overlap['integral'][scenario])
        if blocked:new['matching_technical_available']='False'
        if blocked or overlap['curve'][scenario]:new['matching_curve_technical_available']='False'
        result.append(new)
    return result
