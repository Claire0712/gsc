from pathlib import Path
import json,hashlib
p=Path('deliverables/2026-11-01_HeatSignal_manuscript_text_v23.txt');s=p.read_text();a='Composite Global Administrative Zones (CGAZ)';b='Comprehensive Global Administrative Zones (CGAZ)';assert s.count(a)==1
out=Path('deliverables/2026-11-01_HeatSignal_manuscript_text_v24.txt');assert not out.exists();out.write_text(s.replace(a,b))
Path('outputs/2026-11-01_cgaz_citation_correction.json').write_text(json.dumps(dict(old=a,new=b,source='https://www.geoboundaries.org/globalDownloads.html',checked_utc_date='2026-11-01',scope='Correct full product title from primary provider; snapshot, data, numerical results and study scope unchanged',source_text_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),output_text_sha256=hashlib.sha256(out.read_bytes()).hexdigest()),indent=2)+'\n')
