"""Immutable membership-only views of the original event panel."""
import argparse
import json
from pathlib import Path
from .common_panel_subset import subset
from .run_connection_baseline import Sources, Stage

p=argparse.ArgumentParser()
p.add_argument('--panel',required=True)
p.add_argument('--mode',choices=('clean','matched'),required=True)
p.add_argument('--output',required=True)
a=p.parse_args()
out=Path(a.output)
if out.exists():raise FileExistsError(out)
src=Sources(); stage=Stage(a.panel,src,status_key='status',manifest_key=('status','completed'))
rows=subset(stage.json('rows.json'),a.mode)
for name,entry in stage.manifest['inputs'].items():src.verify(name,entry)
for name in ('run_common_panel_subset.py','common_panel_subset.py','common_signal_summary.py'):src.verify(Path(__file__).with_name(name))
src.check();out.mkdir(parents=True)
def save(name,value):(out/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
save('rows.json',rows)
save('summary.json',dict(mode=a.mode,rows=len(rows),events=len({r['event_id'] for r in rows}),scope='Unmodified original rows, exact common-three-signal full-clean or full-clean/main-integral membership. Conditions on future completeness; not common controls or causal certification.'))
save('manifest.json',dict(status='completed',inputs=src.entries,outputs={n:Sources().verify(out/n) for n in ('rows.json','summary.json')}))
save('status.json',dict(status='completed'))
