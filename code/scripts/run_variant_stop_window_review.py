"""Join verified STOP evidence to all comparison identities and selected pairs."""
import argparse,json,time
from pathlib import Path
from .stop_window_review import review,SCENARIOS
from .run_connection_baseline import Sources,Stage,_json
from .run_variant_matching import ancestry_entry

def run(args):
    started=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError('Output already exists')
    sources=Sources()
    weather=Stage(args.weather,sources,status_key='status',manifest_key=('status','completed'))
    stop=Stage(args.stop,sources,status_key='status')
    matching=Stage(args.matching,sources,status_key='status',manifest_key=('status','completed'))
    for path in (Path(args.weather)/'manifest.json',Path(args.weather)/'features.json'):
        sources.verify(path,ancestry_entry(matching.manifest['inputs'],path))
    comp_path=Path(args.comparison)/'manifest.json'
    comp=_json(sources.read(comp_path,ancestry_entry(weather.manifest['inputs'],comp_path)))
    for name in ('manifest.json','stop_windows.json'):
        p=Path(args.stop)/name
        sources.verify(p,ancestry_entry(comp['inputs'],p))
    windows=_json(sources.read(Path(args.weather)/'features.json',weather.manifest['outputs']['features.json']))
    records=_json(sources.read(Path(args.stop)/'stop_windows.json',stop.manifest['outputs']['stop_windows.json']))['records']
    if args.country:windows=[w for w in windows if w['country_id']==args.country]
    if not windows:raise ValueError('Empty windows')
    reviewed=review(windows,records);index={w['window_id']:w for w in reviewed}
    pair_audits={};counts={}
    for scale in ('0.5','1','2'):
        name='selected_'+scale+'.json'
        selected=_json(sources.read(Path(args.matching)/name,matching.manifest['outputs'][name]))
        if args.country:selected=[r for r in selected if r['country_id']==args.country]
        audits=[]
        for p in selected:
            used=('preperiod','integral') if p['purpose']=='integral' else ('preperiod','integral','curve')
            evidence={}
            for scenario in SCENARIOS:
                evidence[scenario]={role:sorted({sid for purpose in used for sid in index[p[role+'_id']]['overlaps'][purpose][scenario]}) for role in ('heat','control')}
            audits.append(dict(heat_id=p['heat_id'],control_id=p['control_id'],signal=p['signal'],purpose=p['purpose'],evidence=evidence,final_sample_eligible=False))
        pair_audits[scale]=audits
        counts[scale]={s:sum(any(a['evidence'][s].values()) for a in audits) for s in SCENARIOS}
    for name in ('stop_window_review.py','run_variant_stop_window_review.py','run_variant_matching.py','run_connection_baseline.py'):
        sources.verify(Path(__file__).parent/name)
    sources.check();out.mkdir(parents=True)
    def publish(name,value):
        p=out/name;p.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');return Sources().verify(p)
    summary=dict(status='completed',windows=len(reviewed),selected_country=args.country,matched_pair_target_overlap_counts=counts,unlocated_country_record_windows=sum(bool(r['unlocated_country_records']) for r in reviewed),elapsed_seconds=time.monotonic()-started,scope='Target-window evidence linkage only; no reference-sensitivity recalculation or nationwide confirmation',final_sample_eligible=False)
    products={}
    for name,obj in [('window_review.json',reviewed),('pair_review.json',pair_audits),('summary.json',summary)]:products[name]=publish(name,obj)
    sources.check()
    publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products))
    publish('status.json',dict(status='completed'))
    print(json.dumps(summary))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for a in ('weather','stop','matching','comparison','output'):p.add_argument('--'+a,required=True)
    p.add_argument('--country');run(p.parse_args())

