"""Byte-identical stage adapter; never rewrite a frozen alternative catalogue."""
import argparse,json,time
from pathlib import Path
from .run_connection_baseline import Sources

def adapt(batch,variant,output):
    started=time.monotonic();batch=Path(batch);out=Path(output)
    if out.exists():raise FileExistsError(out)
    if Path(variant).name!=variant or variant in ['.','..']:raise ValueError('Invalid variant')
    src=Sources();assert json.loads(src.read(batch/'status.json'))['status']=='completed'
    m=json.loads(src.read(batch/'manifest.json'));assert m['status']=='completed'
    payload={}
    for n in ['raw_events.csv','process_events.csv','analysis_events.csv','daily_heat_flags.csv.gz','warm_seasons.csv','rules.json']:
        payload[n]=src.read(batch/variant/n,m['outputs'][variant+'/'+n])
    src.verify(Path(__file__));src.check();out.mkdir(parents=True)
    for n,b in payload.items():(out/n).write_bytes(b)
    products={n:Sources().verify(out/n) for n in payload}
    (out/'manifest.json').write_text(json.dumps(dict(state='complete',inputs=src.entries,outputs=products,variant=variant,scope='Byte-identical copies and input provenance only; no new weather computation or network eligibility.'),indent=2)+'\n')
    (out/'status.json').write_text('{"state":"complete"}\n')
    return dict(variant=variant,files=len(payload),elapsed_seconds=time.monotonic()-started)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['batch','variant','output']:p.add_argument('--'+n,required=True)
    a=p.parse_args();print(json.dumps(adapt(a.batch,a.variant,a.output)))
