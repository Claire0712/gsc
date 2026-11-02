"""Exact sparse-calendar translations of intact supported response windows."""
from collections import defaultdict
from datetime import datetime,timezone
from .paired_responses import weights
FIELDS=('signed','deficit','below95','dewpoint')
def source_lookup(rows):
 lookup={};conflicts=set()
 for r in rows:
  key=r['country_id'],int(r['date_utc']);v={k:float(r[k]) for k in FIELDS}
  if key in lookup and any(abs(lookup[key][k]-v[k])>1e-12 for k in FIELDS):conflicts.add(key)
  else:lookup[key]=v
 for k in conflicts:lookup.pop(k,None)
 return lookup,len(conflicts)
def translated(rows,days,lookup,limit=0):
 if days not in (-56,-28,28,56):raise ValueError('Frozen offsets only')
 groups=defaultdict(list)
 for r in rows:groups[r['group_id']].append(r)
 kept=[];number=0
 for group,rr in sorted(groups.items()):
  windows=defaultdict(list)
  for r in rr:windows[r['window_id']].append(r)
  eligible={}
  for w,ww in windows.items():
   if len(ww)==15 and {int(r['relative_day']) for r in ww}==set(range(-7,8)) and all((r['country_id'],int(r['date_utc'])+days*86400) in lookup for r in ww):eligible[w]=ww
  anchors=[w for w,ww in eligible.items() if ww[0]['role']=='heat'];controls=[w for w,ww in eligible.items() if ww[0]['role']=='control']
  if len(anchors)!=1 or not controls:continue
  if limit and number>=limit:break
  number+=1
  for r in rr:
   if r['window_id'] not in eligible:continue
   stamp=int(r['date_utc'])+days*86400
   kept.append(dict(r,**lookup[r['country_id'],stamp],original_group_id=group,original_date_utc=int(r['date_utc']),source_date_utc=stamp,date_utc=stamp,date=datetime.fromtimestamp(stamp,timezone.utc).strftime('%Y-%m-%d'),group_id='shift'+str(days)+':'+group,matched_controls=len(controls),base_weight=1. if r['role']=='heat' else 1./len(controls)))
 return weights(kept)
