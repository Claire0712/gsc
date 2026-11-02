"""Provisional matching on verified pre-features; does not open outcome NPZs."""
import argparse
from collections import Counter
import csv
import io
import json
from pathlib import Path
import time
from .match_windows import match

def ancestry_entry(entries,path):
    matches=[v for k,v in entries.items() if Path(k).resolve()==Path(path).resolve()]
    if len(matches)!=1:raise ValueError('Missing or ambiguous weather ancestry')
    return matches[0]


def run(args):
    out=Path(args.output)
    if out.exists():raise FileExistsError('Output already exists')
    from .run_connection_baseline import Sources,Stage,_json
    started=time.monotonic();sources=Sources()
    comp=Stage(args.comparison,sources,status_key='status',manifest_key=('status','completed'))
    weather=Stage(args.weather,sources,status_key='status',manifest_key=('status','completed'))
    table=Path(args.comparison)/'window_audit.csv'
    for path in (Path(args.comparison)/'manifest.json',table):
        expected=ancestry_entry(weather.manifest['inputs'],path)
        if expected is None:raise ValueError('Weather comparison ancestry missing')
        sources.verify(path,expected)
    windows=list(csv.DictReader(io.StringIO(sources.read(table,comp.manifest['outputs']['window_audit.csv']).decode())))
    features=_json(sources.read(Path(args.weather)/'features.json',weather.manifest['outputs']['features.json']))
    from .stop_scenario_matching import apply_scenario
    stop_stage=Stage(args.stop_review,sources,status_key='status',manifest_key=('status','completed'))
    weather_manifest=Path(args.weather)/'manifest.json'
    sources.verify(weather_manifest,ancestry_entry(stop_stage.manifest['inputs'],weather_manifest))
    review=_json(sources.read(Path(args.stop_review)/'window_review.json',stop_stage.manifest['outputs']['window_review.json']))
    windows=apply_scenario(windows,review,args.scenario)
    if args.country:
        windows=[r for r in windows if r['country_id']==args.country]
        if not windows:raise ValueError('No windows for country')
    for name in ('run_stop_scenario_matching.py','stop_scenario_matching.py','match_windows.py','run_connection_baseline.py'):
        sources.verify(Path(__file__).parent/name)
    sources.verify(Path(args.design))
    products={};summaries={}
    out.mkdir(parents=True)
    def publish(name,data):
        p=out/name;p.write_text(json.dumps(data,allow_nan=False,indent=2)+'\n')
        products[name]=Sources().verify(p)
    for scale in (.5,1,2):
        pairs,selection=match(windows,features,scale)
        groups={(r['parent_event_id'],r['signal'],purpose) for r in windows if r['role']=='heat' for purpose in ('integral','curve')}
        selectedgroups={(r['parent_event_id'],r['signal'],r['purpose']) for r in selection}
        counts={}
        for signal in sorted({r['signal'] for r in windows}):
            counts[signal]={p:sum(g[1]==signal and g[2]==p for g in selectedgroups) for p in ('integral','curve')}
        reuse=Counter((r['signal'],r['purpose'],r['country_id'],r['control_start'],r['control_end']) for r in selection)
        label=str(scale)
        publish('pairs_'+label+'.json',pairs)
        publish('selected_'+label+'.json',selection)
        publish('reuse_'+label+'.json',[dict(signal=k[0],purpose=k[1],country_id=k[2],start=k[3],end=k[4],uses=n) for k,n in sorted(reuse.items())])
        summaries[label]=dict(candidate_pairs=len(pairs),supported_pairs=sum(r['supported'] for r in pairs),selected_pairs=len(selection),heat_signal_purpose_groups=len(groups),matched_groups=len(selectedgroups),unmatched_groups=len(groups-selectedgroups),matched_by_signal_purpose=counts,max_window_reuse=max(reuse.values(),default=0))
    sources.check()
    summary=dict(scenario=args.scenario,reference_remasking=False,status='completed',selected_country=args.country,specifications=summaries,elapsed_seconds=time.monotonic()-started,provisional=True,final_sample_eligible=False,final_weights_computed=False,scope='Outcome-blind provisional support/selection; pending measurement/STOP adjudication and date-level weight normalization')
    publish('summary.json',summary)
    (out/'manifest.json').write_text(json.dumps(dict(status='completed',inputs=sources.entries,outputs=products),indent=2)+'\n')
    (out/'status.json').write_text(json.dumps(dict(status='completed',elapsed_seconds=time.monotonic()-started))+'\n')
    print(json.dumps(summary))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('comparison','weather','output','design','stop-review','scenario'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--country')
    run(parser.parse_args())


