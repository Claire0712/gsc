"""Attach frozen pre-dispersion and season-first modifiers, preserve unknowns."""
import argparse,csv,io,json,math,time
from pathlib import Path
from collections import Counter
from .season_modifier import first_events
from .run_connection_baseline import Sources,Stage,_json

def attach(panel,audits,catalogue):
    index={(r['window_id'],r['signal']):r for r in audits}
    if len(index)!=len(audits):raise ValueError('Duplicate audit identity')
    cat={r['event_id']:r for r in catalogue};first=first_events(catalogue);out=[]
    for r in panel:
        a=index['heat:'+r['event_id'],r['signal']];c=cat[r['event_id']]
        if a['country_id']!=r['country_id'] or c['country_id']!=r['country_id']:raise ValueError('Country identity mismatch')
        try:v=float(a['raw_pre_mad_over_median'])
        except (ValueError,TypeError):v=float('nan')
        good=a['raw_pre_normalized_features_available']=='True' and math.isfinite(v) and v>=0
        out.append(dict(r,pre_connection_dispersion=dict(value=v if good else None,
            status='available' if good else 'unavailable_pre_feature',source_field='raw_pre_mad_over_median'),warm_season=first[r['event_id']]))
    return out

def run(args):
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources();social=Stage(args.social,sources,status_key='status',manifest_key=('status','completed'))
    comp=Stage(args.comparison,sources,status_key='status',manifest_key=('status','completed'))
    rows=social.json('rows.json')
    if args.country:rows=[r for r in rows if r['country_id']==args.country]
    root=Path(args.catalogue);manifest=_json(sources.read(root/'manifest.json'))
    if manifest['state']!='complete':raise ValueError('Incomplete catalogue')
    catalogue=list(csv.DictReader(io.StringIO(sources.read(root/'analysis_events.csv',manifest['outputs']['analysis_events.csv']).decode())))
    audits=list(csv.DictReader(io.StringIO(comp.read('window_audit.csv').decode())))
    result=attach(rows,audits,catalogue)
    summaries={}
    for sig in sorted({r['signal'] for r in result}):
        rr=[r for r in result if r['signal']==sig and r['matched_integral']]
        summaries[sig]=dict(matched_records=len(rr),pre_dispersion_available=sum(r['pre_connection_dispersion']['value'] is not None for r in rr),
            first_status=dict(Counter(str(r['warm_season']['first_warm_season_event']) for r in rr)),
            all_six_complete=sum(r['pre_connection_dispersion']['value'] is not None and r['warm_season']['first_warm_season_event'] is not None and all(v['value'] is not None for v in r['modifiers'].values()) for r in rr))
    for name in ('temporal_modifier_inputs.py','season_modifier.py'):sources.verify(Path(__file__).with_name(name))
    sources.check();out.mkdir(parents=True)
    def save(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    save('rows.json',result);save('summary.json',dict(records=len(result),signals=summaries,elapsed_seconds=time.monotonic()-start,
        scope='Frozen normalized preperiod MAD/median; higher dispersion means less stable. First of full weather catalogue within fixed cross-year 3-month season, before network/matching selection. Left-truncated season unknown. Four social values unchanged; publication dates unknown. No fitted modifier effects or common-support certification.'))
    save('manifest.json',dict(status='completed',inputs=sources.entries,outputs={n:Sources().verify(out/n) for n in ('rows.json','summary.json')}))
    save('status.json',dict(status='completed'));print((out/'summary.json').read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('social','comparison','catalogue','output'):p.add_argument('--'+n,required=True)
    p.add_argument('--country');run(p.parse_args())
