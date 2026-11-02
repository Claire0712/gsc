"""Package exact offline platform plus retained rebuild inputs; not final study acceptance."""
from pathlib import Path
import hashlib,json,zipfile
root=Path(__file__).resolve().parents[1]
output=root/'deliverables/2026-10-29_platform_rebuild_bundle.zip'
assert not output.exists()
names=['deliverables/2026-10-29_platform/index.html','deliverables/2026-10-29_platform/manifest.json',
 'deliverables/2026-10-29_platform/README.txt','deliverables/2026-10-16/replay_full/index.html',
 'data/worldbank/countries.json','web/platform/core.js','web/platform/app.js','web/platform/index.template.html',
 'scripts/build_platform_20261029.py','scripts/package_platform_sources_20261029.py',
 'tests/platform_core.test.cjs','tests/platform_integration.test.cjs',
 'outputs/2026-10-29_verify_platform_data.py','outputs/2026-10-29_platform_data_audit.json',
 'docs/superpowers/specs/2026-10-29-interactive-workbench-design.md']
manifest={}
with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for name in names:
        path=root/name;assert path.is_file() and not path.is_symlink()
        blob=path.read_bytes();manifest[name]=dict(bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest())
        archive.writestr(name,blob)
    archive.writestr('REBUILD_INSTRUCTIONS.txt','Open deliverables/2026-10-29_platform/index.html directly. For rebuilding, unpack into a NEW directory and rename the delivered platform folder before running python3 scripts/build_platform_20261029.py; the builder deliberately refuses an existing output. It uses Python standard library only. Run node --test tests/platform_core.test.cjs tests/platform_integration.test.cjs after building. No package installation or network is needed. This is a platform source/data bundle, not raw research observations, full-study reproduction, public hosting or browser acceptance.\n')
    archive.writestr('MEMBERS.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(output) as archive:
    assert archive.testzip() is None
    for name,record in manifest.items():
        blob=archive.read(name)
        assert len(blob)==record['bytes'] and hashlib.sha256(blob).hexdigest()==record['sha256']
receipt=dict(archive=output.name,bytes=output.stat().st_size,sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
 source_and_data_members=len(names),crc_and_all_member_hashes_verified=True,
 browser_visual_acceptance=False,whole_study_accepted=False)
path=root/'outputs/2026-10-29_platform_bundle_receipt.json';assert not path.exists()
path.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
