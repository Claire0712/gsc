"""Outcome-blind earliest nonheat control anchor; separate from calendar-shift placebo."""
from collections import defaultdict
from .paired_responses import weights

def subset(rows,limit=0):
 groups=defaultdict(list)
 for r in rows:groups[r['group_id']].append(r)
 kept=[];number=0
 for group,rr in sorted(groups.items()):
  windows=defaultdict(list)
  for r in rr:
   if r['role']=='control':windows[r['window_id']].append(r)
  ordered=[]
  for window,ww in windows.items():
   if len(ww)!=15 or {int(r['relative_day']) for r in ww}!=set(range(-7,8)):raise ValueError('Complete unique15day control required')
   starts={int(r['date_utc'])-int(r['relative_day'])*86400 for r in ww}
   if len(starts)!=1:raise ValueError('Inconsistent control anchor')
   ordered.append((starts.pop(),window))
  ordered.sort()
  if not ordered:continue
  start,anchor=ordered[0]
  controls=[w for t,w in ordered[1:] if t-start>=15*86400]
  if not controls:continue
  if limit and number>=limit:break
  number+=1
  for r in rr:
   if r['role']!='control' or r['window_id'] not in [anchor]+controls:continue
   kept.append(dict(r,original_role='control',original_group_id=group,group_id='nonheat:'+group,role='heat' if r['window_id']==anchor else 'control',base_weight=1. if r['window_id']==anchor else 1./len(controls),matched_controls=len(controls)))
 return weights(kept)
