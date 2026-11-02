"""Verified component rebuild from retained derived inputs; not raw-data replication."""
from pathlib import Path
import ast,json,hashlib,zipfile,tempfile,subprocess,sys,os,math,importlib.metadata
root=Path(__file__).resolve().parents[1];base='analysis/2026-11-01_geographic_support/v1/full_outputs';manifest=json.loads((root/base/'manifest.json').read_text());members=set(manifest['inputs'])|{str(p.relative_to(root)) for p in (root/base).iterdir() if p.is_file()}|{base+'.verify.json','tests/test_geographic_leverage_diagnostics.py','docs/superpowers/specs/2026-11-01-geographic-interpretation-guard.md','scripts/geographic_leverage_diagnostics.py','scripts/qualify_geographic_comparison_20261101.py','scripts/export_geographic_common_support_20261101.py','scripts/audit_geographic_common_support_20261101.py','scripts/package_geographic_derived_rebuild_20261101_v2.py'}
queue=[p for p in members if p.startswith('scripts/') and p.endswith('.py')]
while queue:
 p=queue.pop()
 for node in ast.walk(ast.parse((root/p).read_text())):
  candidates=[]
  if isinstance(node,ast.ImportFrom):
   if node.level:candidates=[node.module] if node.module else [n.name for n in node.names]
   elif node.module and node.module.startswith('scripts.'):candidates=[node.module.split('.',1)[1]]
  if isinstance(node,ast.Import):candidates += [n.name.removeprefix('scripts.') for n in node.names]
  for n in candidates:
   q='scripts/'+n.replace('.','/')+'.py'
   if (root/q).is_file() and q not in members:members.add(q);queue.append(q)
for n,v in manifest['inputs'].items():assert hashlib.sha256((root/n).read_bytes()).hexdigest()==v['sha256'],n
records={n:dict(bytes=(root/n).stat().st_size,sha256=hashlib.sha256((root/n).read_bytes()).hexdigest()) for n in sorted(members)};out=root/'deliverables/2026-11-01_geographic_derived_rebuild_v2.zip';assert not out.exists()
with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for n in records:z.write(root/n,n)
 z.writestr('MEMBER_SHA256.json',json.dumps(records,indent=2)+'\n');z.writestr('README.txt','Derived-input geographic component only, not whole-study or raw ERA5/IODA replication. Unpack into a NEW directory. Requires existing Python, numpy, scipy and statsmodels; do not fetch data or install packages automatically. Run python3 -m unittest discover -s tests -p "test_geographic*.py"; python3 -m scripts.run_geographic_common_support_20261101 --output reproduced_outputs; python3 -m scripts.audit_geographic_common_support_20261101 reproduced_outputs. Then run python3 -m scripts.export_geographic_common_support_20261101 and python3 -m scripts.qualify_geographic_comparison_20261101 to rebuild the numerical export and the explicit post-hoc interpretation qualification. Original production outputs are under analysis/2026-11-01_geographic_support/v1/full_outputs. 42 support combinations, 126 outcome cases, three numerical fits; the post-hoc design-information guard leaves all qualified regional displays blank. See the guard document; no causal or ranking conclusion.\n')
def equal(a,b):
 if isinstance(a,dict):assert set(a)==set(b);[equal(a[k],b[k]) for k in a]
 elif isinstance(a,list):assert len(a)==len(b);[equal(x,y) for x,y in zip(a,b)]
 elif isinstance(a,float):assert math.isclose(a,b,rel_tol=1e-6,abs_tol=1e-9),(a,b)
 else:assert a==b,(a,b)
with tempfile.TemporaryDirectory(prefix='heatsignal-geographic-rebuild-') as d:
 dest=Path(d)
 with zipfile.ZipFile(out) as z:
  assert z.testzip() is None
  for n,v in records.items():assert hashlib.sha256(z.read(n)).hexdigest()==v['sha256']
  z.extractall(dest)
 env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');commands=[[sys.executable,'-m','unittest','discover','-s','tests','-p','test_geographic*.py'],[sys.executable,'-m','scripts.run_geographic_common_support_20261101','--output','reproduced_outputs'],[sys.executable,'-m','scripts.audit_geographic_common_support_20261101','reproduced_outputs'],[sys.executable,'-m','scripts.export_geographic_common_support_20261101'],[sys.executable,'-m','scripts.qualify_geographic_comparison_20261101']];logs=[]
 for cmd in commands:
  p=subprocess.run(cmd,cwd=dest,env=env,capture_output=True,text=True);logs.append(p.stdout+p.stderr);assert p.returncode==0,p.stdout+p.stderr
 equal(json.loads((dest/'reproduced_outputs/results.json').read_text()),json.loads((dest/base/'results.json').read_text()));equal(json.loads((dest/'reproduced_outputs/support_inputs.json').read_text()),json.loads((dest/base/'support_inputs.json').read_text()))
 qualified=json.loads((dest/'deliverables/2026-11-01_GEOGRAPHIC_COMPARISON.json').read_text());assert qualified['qualified_regional_comparisons']==0 and len(qualified['numerical_rows'])==126 and sum(r['estimable'] for r in qualified['numerical_rows'])==3
receipt=dict(qualification_export_reproduced=True,archive=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),bytes=out.stat().st_size,members=len(records),zip_crc_and_all_member_sha256_verified=True,isolated_derived_rebuild_verified=True,comparison_relative_tolerance=1e-6,comparison_absolute_tolerance=1e-9,local_verification_environment={n:importlib.metadata.version(n) for n in ['numpy','scipy','statsmodels']},logs=logs,raw_data_reproduction_claimed=False,whole_study_accepted=False)
target=root/'outputs/2026-11-01_geographic_derived_rebuild_v2_receipt.json';assert not target.exists();target.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='logs'}))
