"""Verify a frozen archive and rebuild downstream presentation in a new temporary root.

No downloads, servers, original-input writes, or new statistical fits.
"""
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile,time,zipfile
from pathlib import Path

def verify_manifest(root,entries):
 root=Path(root).resolve()
 for name,meta in entries.items():
  p=Path(name)
  if p.is_absolute() or '..' in p.parts:raise ValueError('Unsafe archive path '+name)
  p=root/p
  if not p.resolve().is_relative_to(root):raise ValueError('Source escapes root '+name)
  if not p.is_file() or p.stat().st_size!=meta['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('Source mismatch '+name)
 return len(entries)

def semantic_docx(path):
 from docx import Document
 doc=Document(path)
 with zipfile.ZipFile(path) as z:media={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('word/media/')}
 return dict(paragraphs=[p.text for p in doc.paragraphs],tables=[[[c.text for c in row.cells] for row in t.rows] for t in doc.tables],sections=len(doc.sections),media=media)

def rebuild_commands(manifest,python):
 scripts=manifest.get('export_scripts',[f'scripts/export_main_table{i}_20261101.py' for i in (1,2,3,4)]+['scripts/export_supplement_tables_20261101.py'])
 return [[python,name] for name in scripts]+[[python,'scripts/assemble_manuscript_docx_20261101_v24.py','--source',manifest.get('text_source','deliverables/2026-11-01_HeatSignal_manuscript_text_v26.txt'),'--output','deliverables/rebuilt_base.docx','--receipt','outputs/rebuilt_base.json']]

def compose_extra_documents(root,manifest):
 try:from .merge_paper_tables import merge_documents
 except ImportError:from merge_paper_tables import merge_documents
 for rec in manifest.get('composed_documents',[]):
  out=root/rec['target'];out.parent.mkdir(parents=True,exist_ok=True)
  merge_documents(root/rec['base'],[root/p for p in rec['appendices']],out)

def rebuild(root,manifest):
 started=time.monotonic();checks=[]
 with tempfile.TemporaryDirectory(prefix='heatsignal-reproduction-') as folder:
  tmp=Path(folder)
  for name in manifest['files']:
   p=tmp/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,p)
  for name in manifest['regenerated_directories']:
   p=tmp/name
   if p.exists():shutil.rmtree(p)
  for rec in manifest.get('composed_documents',[]):
   target=tmp/rec['target']
   if target.exists():target.unlink()
  (tmp/'outputs').mkdir(exist_ok=True)
  env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
  commands=rebuild_commands(manifest,sys.executable)
  for cmd in commands:
   r=subprocess.run(cmd,cwd=tmp,env=env,capture_output=True,text=True)
   if r.returncode:raise RuntimeError('Rebuild failed: '+str(cmd)+'\n'+r.stdout[-1000:]+'\n'+r.stderr[-3000:])
   checks.append(dict(command=cmd[1:],returncode=r.returncode))
  compose_extra_documents(tmp,manifest)
  for rec in manifest.get('composed_documents',[]):
   if semantic_docx(tmp/rec['target'])!=semantic_docx(root/rec['target']):raise ValueError('Composed document differs '+rec['target'])
  for name in manifest['numerical_outputs']:
   if (tmp/name).read_bytes()!=(root/name).read_bytes():raise ValueError('Rebuilt numerical object differs '+name)
  for name in manifest['table_docx_outputs']:
   if semantic_docx(tmp/name)!=semantic_docx(root/name):raise ValueError('Rebuilt table DOCX content differs '+name)
  sys.path.insert(0,str(tmp/'scripts'))
  from merge_paper_tables import merge_documents
  merged=tmp/'deliverables/rebuilt_manuscript.docx'
  merge_documents(tmp/'deliverables/rebuilt_base.docx',[tmp/n for n in manifest['table_docx_outputs'][:4]],merged)
  if semantic_docx(merged)!=semantic_docx(root/manifest['manuscript']):raise ValueError('Rebuilt integrated manuscript differs')
 return dict(status='passed',elapsed_seconds=time.monotonic()-started,commands=checks,exact_numerical_files=len(manifest['numerical_outputs']),semantic_table_documents=len(manifest['table_docx_outputs']),composed_documents=len(manifest.get('composed_documents',[])),integrated_manuscript_content_images_sections_equal=True,raw_observational_pipeline_rerun=False,pdf_rerendered=False,browser_verified=False)

def main():
 a=argparse.ArgumentParser();a.add_argument('--rebuild',action='store_true');a.add_argument('--receipt',type=Path);args=a.parse_args();root=Path(__file__).resolve().parents[1];m=json.loads((root/'REPRO_MANIFEST.json').read_text());result=dict(verified_files=verify_manifest(root,m['files']),scope=m['scope'])
 if args.rebuild:result['rebuild']=rebuild(root,m)
 if args.receipt:
  if args.receipt.exists():raise FileExistsError(args.receipt)
  args.receipt.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
