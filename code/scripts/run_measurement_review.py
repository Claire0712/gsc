"""Bounded sequential measurement diagnostics; candidates never auto-excluded."""
import argparse,csv,io,json,os,time
from pathlib import Path
from collections import Counter
import numpy as np
from .measurement_review import diagnose
from .run_connection_baseline import Sources,Stage,_json

def run(args):
    out=Path(args.output)
    if out.exists():raise FileExistsError('Fresh output required')
    started=time.monotonic();sources=Sources()
    comp=Stage(args.comparison,sources,status_key='status',manifest_key=('status','completed'))
    sync=Stage(args.sync,sources,status_key='status')
    table=Path(args.comparison)/'window_audit.csv'
    rows=list(csv.DictReader(io.StringIO(sources.read(table,comp.manifest['outputs']['window_audit.csv']).decode())))
    if args.country:rows=[r for r in rows if r['country_id']==args.country]
    if not rows:raise ValueError('Empty selection')
    sync_summary=_json(sources.read(Path(args.sync)/'summary.json',sync.manifest['outputs']['summary.json']))
    for path,expected in sync_summary['sources'].items():
        if path in comp.manifest['inputs']:
            if expected['sha256']!=comp.manifest['inputs'][path]['sha256']:raise ValueError('Source ancestry mismatch')
    candidates={}
    for sig in sorted({r['signal'] for r in rows}):
        name=sig+'_joint.npz';p=Path(args.sync)/name;sources.verify(p,sync.manifest['outputs'][name])
        with np.load(p,allow_pickle=False) as z:candidates[sig]=z['interval_start_utc'][z['candidate']].copy()
    for name in ('measurement_review.py','run_measurement_review.py','run_connection_baseline.py'):
        sources.verify(Path(__file__).parent/name)
    for name in ('synchronous_candidate_review_diagnostics.json','bgp_candidate_entity_review.json'):
        sources.verify(Path(args.evidence)/name)
    out.mkdir(parents=True)
    def publish(name,value):
        p=out/name;temp=out/('.'+name);temp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');os.replace(temp,p)
    reports=[]
    publish('status.json',dict(status='running',pid=os.getpid(),processed=0,total=len(rows)))
    try:
        for row in rows:
            p=Path(args.comparison)/row['point_file'];sources.verify(p,comp.manifest['outputs'][row['point_file']])
            with np.load(p,allow_pickle=False) as z:
                if str(z['window_id'])!=row['window_id'] or str(z['signal'])!=row['signal']:raise ValueError('NPZ identity mismatch')
                t=z['target_timestamps'];r=diagnose(t,z['target_values'],z['preperiod_mask'])
                flags=np.isin(t,candidates[row['signal']])
                r['synchronous_target_slots']={use:int(np.count_nonzero(flags&z[use+'_mask'])) for use in ('preperiod','integral','curve')}
                refs=t[:,None]+z['reference_offsets_days'][None,:]*86400
                r['synchronous_potential_reference_queries']=int(np.isin(refs,candidates[row['signal']]).sum())
                r.update(window_id=row['window_id'],signal=row['signal'],country_id=row['country_id'],role=row['role'],point_file=row['point_file'],disposition='retain_unconfirmed_candidate' if r['flags'] or flags.any() or r['synchronous_potential_reference_queries'] else 'no_candidate_detected_not_proof_of_validity')
                reports.append(r)
            if len(reports)%100==0:publish('status.json',dict(status='running',pid=os.getpid(),processed=len(reports),total=len(rows),elapsed_seconds=time.monotonic()-started))
        sources.check()
        counts={sig:dict(windows=sum(r['signal']==sig for r in reports),unavailable=sum(r['signal']==sig and not r['normalized_diagnostics_available'] for r in reports),flags=dict(Counter(f for r in reports if r['signal']==sig for f in r['flags'])),synchronous_target_windows=sum(r['signal']==sig and any(r['synchronous_target_slots'].values()) for r in reports),potential_reference_windows=sum(r['signal']==sig and bool(r['synchronous_potential_reference_queries']) for r in reports)) for sig in candidates}
        summary=dict(status='completed',windows=len(reports),counts=counts,elapsed_seconds=time.monotonic()-started,confirmed_faults=0,primary_exclusions=0,scope='Candidate diagnostics and prior evidence review, not fault confirmation; global synchronous times do not prove country-specific drops')
        publish('window_diagnostics.json',reports);publish('summary.json',summary)
        products={name:Sources().verify(out/name) for name in ('window_diagnostics.json','summary.json')}
        publish('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products))
        publish('status.json',dict(status='completed',processed=len(reports),elapsed_seconds=time.monotonic()-started))
        print(json.dumps(summary))
    except BaseException as e:
        publish('status.json',dict(status='failed',error=str(e),processed=len(reports)));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('comparison','sync','evidence','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--country');run(p.parse_args())
