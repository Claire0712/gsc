"""Immutable source bundle, then a genuinely isolated rebuild and logic tests."""
from pathlib import Path
import hashlib,json,zipfile,tempfile,subprocess,os,shutil
root=Path(__file__).resolve().parents[1]
platform='deliverables/2026-11-01_platform_v4b'
manifest=json.loads((root/platform/'manifest.json').read_text())
sources=set(manifest['sources'])|{platform+'/index.html',platform+'/manifest.json',platform+'/README.txt',
 'tests/platform_v4_core.test.cjs','tests/platform_v4_event_integration.test.cjs','tests/platform_v4_social.test.cjs','tests/platform_results.test.cjs','tests/platform_v4_results_integration.test.cjs',
 'scripts/package_platform_v4_20261101.py','scripts/export_existing_map_boundaries_20261029.py'}
records={}
for n in sorted(sources):
 p=root/n;assert p.is_file() and not p.is_symlink();b=p.read_bytes()
 records[n]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
for n,digest in manifest['sources'].items():assert records[n]['sha256']==digest,n
assert records[platform+'/index.html']['sha256']==manifest['output_sha256']
target=root/'deliverables/2026-11-01_platform_v4b_rebuild_bundle.zip';assert not target.exists()
with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for n in records:z.write(root/n,n)
 z.writestr('PLATFORM_V4_MEMBER_MANIFEST.json',json.dumps(dict(members=records,whole_study_accepted=False,browser_accepted=False),indent=2)+'\n')
 z.writestr('REBUILD_INSTRUCTIONS.txt','Unpack in a NEW directory. Open deliverables/2026-11-01_platform_v4b/index.html as a local file. Rebuild separately: python3 scripts/build_platform_v4_20261101.py --output rebuilt_platform . Compare rebuilt_platform/index.html with delivered HTML. Set HEATSIGNAL_PLATFORM_HTML=rebuilt_platform/index.html and run node --test tests/platform_v4_core.test.cjs tests/platform_v4_event_integration.test.cjs tests/platform_v4_social.test.cjs tests/platform_results.test.cjs tests/platform_v4_results_integration.test.cjs . No downloads, package install or server required. This is not full research reproduction or certified browser acceptance.\n')
with tempfile.TemporaryDirectory(prefix='heatsignal-v4-rebuild-') as d:
 dest=Path(d)
 with zipfile.ZipFile(target) as z:
  assert z.testzip() is None
  assert set(z.namelist())==set(records)|{'PLATFORM_V4_MEMBER_MANIFEST.json','REBUILD_INSTRUCTIONS.txt'}
  for n,r in records.items():
   b=z.read(n);assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256']
  z.extractall(dest)
 built=subprocess.run(['python3','scripts/build_platform_v4_20261101.py','--output','rebuilt_platform'],cwd=dest,capture_output=True,text=True);assert built.returncode==0,built.stderr
 assert (dest/'rebuilt_platform/index.html').read_bytes()==(dest/platform/'index.html').read_bytes()
 node=shutil.which('node') or '/Users/zhangshizhuo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
 env=dict(os.environ,HEATSIGNAL_PLATFORM_HTML='rebuilt_platform/index.html')
 tests=subprocess.run([node,'--test','tests/platform_v4_core.test.cjs','tests/platform_v4_event_integration.test.cjs','tests/platform_v4_social.test.cjs','tests/platform_results.test.cjs','tests/platform_v4_results_integration.test.cjs'],cwd=dest,env=env,capture_output=True,text=True)
 assert tests.returncode==0,tests.stdout+tests.stderr
 assert '# tests 9' in tests.stdout and '# pass 9' in tests.stdout and '# fail 0' in tests.stdout
 receipt=dict(archive=str(target.relative_to(root)),bytes=target.stat().st_size,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),verified_members=len(records),zip_crc_verified=True,all_member_bytes_verified=True,isolated_rebuild_byte_identical=True,rebuilt_html_sha256=manifest['output_sha256'],tests_stdout=tests.stdout,browser_accepted=False,whole_study_accepted=False)
out=root/'outputs/2026-11-01_platform_v4b_bundle_receipt.json';assert not out.exists();out.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
