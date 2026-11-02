"""Fixed-scale outcome-blind provisional matching; no final eligibility/weights."""
from collections import defaultdict
from datetime import datetime,timezone
import math

IDENTITY=('window_id','parent_event_id','role','country_id','ioda_iso2','start','end')
def flag(value):
    if value not in ('True','False'):raise ValueError('Invalid boolean')
    return value=='True'
def finite(value):
    if value is None or value=='':return None
    n=float(value)
    return n if math.isfinite(n) else None

def match(windows,weather,multiplier=1):
    if multiplier not in (.5,1,2):raise ValueError('Unregistered sensitivity')
    w={}
    for row in weather:
        if row['window_id'] in w:raise ValueError('Duplicate weather identity')
        w[row['window_id']]=row
    seen=set();heats={};controls=defaultdict(list)
    for row in windows:
        key=(row['window_id'],row['signal'])
        if key in seen:raise ValueError('Duplicate signal/window')
        seen.add(key)
        ww=w[row['window_id']]
        if any(str(row[k])!=str(ww[k]) for k in IDENTITY):raise ValueError('Weather identity mismatch')
        group=(row['parent_event_id'],row['signal'])
        if row['role']=='heat':
            if group in heats:raise ValueError('Duplicate heat parent')
            heats[group]=row
        elif row['role']=='control':controls[group].append(row)
        else:raise ValueError('Invalid window role')
    if set(controls)-set(heats):raise ValueError('Orphan control')
    pairs=[];selected=[]
    for group,h in sorted(heats.items()):
        for purpose,qual in [('integral','matching_technical_available'),('curve','matching_curve_technical_available')]:
            candidates=[]
            for c in sorted(controls[group],key=lambda x:x['window_id']):
                hs,cs=int(h['start']),int(c['start']);offset=(cs-hs)/86400
                if h['country_id']!=c['country_id'] or h['ioda_iso2']!=c['ioda_iso2']:raise ValueError('Cross-country control')
                if hs%86400 or cs%86400 or offset==0 or abs(offset)>42 or offset%7:raise ValueError('Invalid calendar offset')
                if datetime.fromtimestamp(hs,timezone.utc).year!=datetime.fromtimestamp(cs,timezone.utc).year:raise ValueError('Cross-year control')
                if int(h['end'])-hs!=int(c['end'])-cs:raise ValueError('Unequal duration')
                reasons=[]
                for role,r in [('heat',h),('control',c)]:
                    if not flag(r[qual]):reasons.append(role+'_technical')
                    if not flag(r['raw_pre_normalized_features_available']):reasons.append(role+'_pre_features')
                hv=[finite(h[k]) for k in ('raw_pre_level','raw_pre_mad_over_median','raw_pre_slope_per_day_over_median')]+[finite(w[h['window_id']][k]) for k in ('tmax_mean_c','dewpoint_mean_c')]
                cv=[finite(c[k]) for k in ('raw_pre_level','raw_pre_mad_over_median','raw_pre_slope_per_day_over_median')]+[finite(w[c['window_id']][k]) for k in ('tmax_mean_c','dewpoint_mean_c')]
                components=None;distance=None
                if any(v is None for v in hv+cv):reasons.append('missing_pre_features')
                elif hv[0]<=0 or cv[0]<=0:reasons.append('nonpositive_level')
                else:
                    components=[abs(math.log(hv[0])-math.log(cv[0]))/(math.log(1.25)*multiplier)]+[abs(a-b)/(s*multiplier) for a,b,s in zip(hv[1:],cv[1:],(.05,.01,3.,3.))]+[abs(offset)/45]
                    for name,v in zip(('level','mad','slope','tmax','dewpoint'),components[:5]):
                        if v>1+1e-12:reasons.append('caliper_'+name)
                    distance=math.sqrt(sum(v*v for v in components))
                pair=dict(heat_id=h['window_id'],control_id=c['window_id'],parent_event_id=group[0],signal=group[1],country_id=h['country_id'],purpose=purpose,multiplier=multiplier,offset_days=int(offset),control_start=cs,control_end=int(c['end']),distance=distance,scaled_components=components,reasons=reasons,supported=not reasons,selected=False,final_sample_eligible=False)
                pairs.append(pair)
                if not reasons:candidates.append(pair)
            candidates.sort(key=lambda r:(r['distance'],abs(r['offset_days']),r['control_id']))
            for rank,row in enumerate(candidates[:3],1):
                row['selected']=True;row['rank']=rank;selected.append(dict(row))
    return pairs,selected
