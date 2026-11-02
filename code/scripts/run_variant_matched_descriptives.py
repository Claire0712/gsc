"""Pre-feature balance and unadjusted equal-event response differences."""
import argparse,csv,io,json,math,statistics,time
from pathlib import Path
from collections import defaultdict
from .matched_descriptives import summary,paired
from .run_connection_baseline import Sources,Stage,_json
from .run_variant_matching import ancestry_entry

FEATURES=('log_pre_level','pre_mad_over_median','pre_slope','pre_tmax_c','pre_dewpoint_c')
OUTCOMES=('dhrd_hours','signed_deviation_hours','mean_deficit_core','maintenance_core','peak_loss_core','disruption_hours_full')

def run(args):
    started=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError('Fresh output required')
    sources=Sources();stages={name:Stage(getattr(args,name),sources,status_key='status',manifest_key=('status','completed')) for name in ('responses','matching','comparison','weather')}
    for parent,child in [('matching','responses'),('comparison','responses'),('weather','matching')]:
        p=Path(getattr(args,parent))/'manifest.json';sources.verify(p,ancestry_entry(stages[child].manifest['inputs'],p))
    def read(stage,name):return sources.read(Path(getattr(args,stage))/name,stages[stage].manifest['outputs'][name])
    metrics={(r['window_id'],r['signal']):r for r in _json(read('responses','metrics.json'))}
    weather={r['window_id']:r for r in _json(read('weather','features.json'))}
    table=list(csv.DictReader(io.StringIO(read('comparison','window_audit.csv').decode())))
    features={}
    for r in table:
        key=r['window_id'],r['signal']
        if key not in metrics:continue
        w=weather[r['window_id']]
        features[key]=[math.log(float(r['raw_pre_level'])),float(r['raw_pre_mad_over_median']),float(r['raw_pre_slope_per_day_over_median']),float(w['tmax_mean_c']),float(w['dewpoint_mean_c'])]
    balance=[];contrasts=[];summaries={}
    for scale in ('0.5','1','2'):
        pairs=_json(read('matching','selected_'+scale+'.json'));groups=defaultdict(list)
        if args.country:pairs=[r for r in pairs if r['country_id']==args.country]
        for p in pairs:groups[p['parent_event_id'],p['signal'],p['purpose']].append(p)
        dateweights=defaultdict(list)
        for row in csv.DictReader(io.StringIO(read('responses','daily_'+scale+'.csv').decode())):
            if -7<=int(row['relative_day'])<=-1:dateweights[row['group_id'],row['signal'],row['purpose'],row['window_id']].append(float(row['weight']))
        buckets=defaultdict(lambda: {'heat':[],'control':[]})
        for (g,sig,purpose),pp in sorted(groups.items()):
            ids=[pp[0]['heat_id']]+[p['control_id'] for p in pp]
            for i,wid in enumerate(ids):
                role='heat' if i==0 else 'control';base=1 if i==0 else 1/len(pp)
                ww=dateweights[g,sig,purpose,wid]
                if len(ww)!=7:raise ValueError('Exactly seven pre-day weights required')
                for weighting,weight in [('equal_event',base),('date_normalized_pre',statistics.mean(ww))]:
                    buckets[sig,purpose,weighting][role].append((features[wid,sig],weight))
            if purpose=='integral':
                for outcome in OUTCOMES:
                    h=metrics[ids[0],sig]['metrics'][outcome];cc=[metrics[wid,sig]['metrics'][outcome] for wid in ids[1:]]
                    contrasts.append(dict(scale=scale,group_id=g,signal=sig,country_id=pp[0]['country_id'],outcome=outcome,heat=h,control_mean=summary(cc,[1]*len(cc))['mean'],difference=paired(h,cc),controls=len(cc)))
        for (sig,purpose,weighting),roles in sorted(buckets.items()):
            for j,name in enumerate(FEATURES):
                a={role:summary([x[j] for x,w in vals],[w for x,w in vals]) for role,vals in roles.items()}
                diff=a['heat']['mean']-a['control']['mean'];sd=math.sqrt((a['heat']['variance']+a['control']['variance'])/2)
                balance.append(dict(scale=scale,signal=sig,purpose=purpose,weighting=weighting,feature=name,heat=a['heat'],control=a['control'],difference=diff,standardized_difference=diff/sd if sd>0 else None))
        outcomes={}
        for sig in sorted({r['signal'] for r in pairs}):
            outcomes[sig]={}
            for outcome in OUTCOMES:
                rr=[r for r in contrasts if r['scale']==scale and r['signal']==sig and r['outcome']==outcome];xx=[r['difference'] for r in rr]
                outcomes[sig][outcome]=dict(events=len(rr),countries=len({r['country_id'] for r in rr}),mean=statistics.mean(xx),median=statistics.median(xx),minimum=min(xx),maximum=max(xx))
        summaries[scale]=outcomes
    for name in ('matched_descriptives.py','run_variant_matched_descriptives.py','run_connection_baseline.py','run_variant_matching.py'):sources.verify(Path(__file__).parent/name)
    sources.verify(Path(args.design));sources.check();out.mkdir(parents=True)
    products={}
    def publish(name,obj):
        p=out/name;p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n');return Sources().verify(p)
    for name,obj in [('balance.json',balance),('paired_contrasts.json',contrasts),('summary.json',dict(status='completed',specifications=summaries,elapsed_seconds=time.monotonic()-started,scope='Unadjusted equal-event paired differences; no causal effect, uncertainty interval or hypothesis test. Matched balance only, not before-after improvement.'))]:products[name]=publish(name,obj)
    publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products));publish('status.json',dict(status='completed'))
    print(json.dumps(dict(status='completed',balance_rows=len(balance),contrast_rows=len(contrasts),elapsed_seconds=time.monotonic()-started,main=summaries['1'])))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('responses','matching','comparison','weather','design','output'):p.add_argument('--'+n,required=True)
    p.add_argument('--country');run(p.parse_args())
