"""Target-window STOP evidence links; assumed sensitivity bounds are not dates."""
from collections import defaultdict

SCENARIOS=('main','unknown_end_plusminus7','unknown_end_plusminus30')
def review(windows,records):
    grouped=defaultdict(list);seen=set()
    for r in records:
        key=str(r['source_row'])
        if key in seen:raise ValueError('Duplicate STOP source row')
        seen.add(key)
        if 'unmatched_joint_country' not in r['reasons']:
            grouped[r['country_id']].append(r)
    result=[];seen=set()
    for w in windows:
        if w['window_id'] in seen:raise ValueError('Duplicate window ID')
        seen.add(w['window_id'])
        start,end=int(w['start']),int(w['end'])
        if start%86400 or end%86400 or end<=start:raise ValueError('Invalid UTC window')
        bounds=dict(preperiod=[start-7*86400,start],integral=[start,end+3*86400],curve=[start-7*86400,start+8*86400])
        overlaps={p:{s:[] for s in SCENARIOS} for p in bounds}
        unlocated=[];linked={}
        for r in grouped[w['country_id']]:
            key=str(r['source_row'])
            if not r['windows']:
                unlocated.append(key);continue
            for purpose,(a,b) in bounds.items():
                for scenario in SCENARIOS:
                    c,d=r['windows'][scenario]
                    if c%86400 or d%86400 or d<=c:raise ValueError('Invalid STOP interval')
                    if a<d and c<b:
                        overlaps[purpose][scenario].append(key)
                        linked[key]=dict(end_unknown=r['end_unknown'],scope_uncertain=r['scope_uncertain'],national_outage_confirmed=False)
        for purposes in overlaps.values():
            for ids in purposes.values():ids.sort()
        result.append(dict(window_id=w['window_id'],country_id=w['country_id'],bounds=bounds,overlaps=overlaps,linked_uncertainty=linked,unlocated_country_records=sorted(unlocated),scope='target_intervals_only',final_sample_eligible=False))
    return result
