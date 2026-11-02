"""Immutable available-work packaging; expressly not whole-study acceptance."""
from pathlib import Path
import hashlib,json,zipfile,time

root=Path(__file__).resolve().parents[1]
target=root/'deliverables/2026-10-28_HeatSignal_available_work.zip'
assert not target.exists()
paths=set()
for directory,extensions in [('scripts',{'.py','.sh'}),('tests',{'.py'}),('docs/superpowers',{'.md'})]:
    paths.update(p for p in (root/directory).rglob('*') if p.is_file() and p.suffix in extensions)
paths.add(root/'reference/HeatSignal_proposal.md')
paths.add(root/'HeatSignal_研究进度.md')
paths.add(root/'outputs/2026-10-28_precip_global_cell_comparison.json')
paths.add(root/'outputs/2026-10-28_manuscript_visual_review.json')
for p in (root/'deliverables').rglob('*'):
    if not p.is_file() or p.suffix.lower() not in {'.json','.txt','.docx','.pdf','.svg','.png','.html'}:continue
    if any(part.startswith('.') for part in p.relative_to(root).parts):continue
    paths.add(p)
records={}
for p in sorted(paths):
    assert p.is_file() and not p.is_symlink(),str(p)
    b=p.read_bytes();records[str(p.relative_to(root))]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
manifest=dict(status='AVAILABLE_WORK_ONLY_NOT_FINAL',created_unix=time.time(),
              raw_inputs_included=False,whole_study_accepted=False,members=records)
with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name in records:z.write(root/name,name)
    z.writestr('AVAILABLE_WORK_MEMBER_MANIFEST.json',json.dumps(manifest,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    assert set(z.namelist())==set(records)|{'AVAILABLE_WORK_MEMBER_MANIFEST.json'}
    for name,record in records.items():
        b=z.read(name)
        assert len(b)==record['bytes'] and hashlib.sha256(b).hexdigest()==record['sha256'],name
receipt=dict(archive=str(target.relative_to(root)),bytes=target.stat().st_size,
             sha256=hashlib.sha256(target.read_bytes()).hexdigest(),verified_members=len(records),
             zip_crc_verified=True,all_member_sizes_and_hashes_verified=True,
             whole_study_accepted=False,scope='Available work snapshot only; read DELIVERY_STATUS for unresolved required work.')
output=root/'outputs/2026-10-28_available_work_package_receipt.json'
assert not output.exists();output.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
