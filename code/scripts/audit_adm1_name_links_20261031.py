"""Existing metadata only: exact same-country name candidates, never fuzzy links."""
from pathlib import Path
from collections import defaultdict,Counter
import sqlite3,json,time,unicodedata
from .run_connection_baseline import Sources
started=time.monotonic();out=Path('analysis/2026-10-31_adm1_name_links/v1');assert not out.exists();sources=Sources()
entities_path=Path('downloads_v2/ioda_adm1_entities.json');countries_path=Path('data/worldbank/countries.json');boundary=Path('data/boundaries/geoBoundariesCGAZ_ADM1.gpkg')
entities=json.loads(sources.read(entities_path))['regions'];countries=json.loads(sources.read(countries_path))[1];sources.verify(boundary)
iso={}
for r in countries:
 code=r.get('iso2Code')
 if code and r['region']['id']!='NA':assert code not in iso;iso[code]=r['id']
normalize=lambda s:' '.join(unicodedata.normalize('NFC',s).casefold().split())
with sqlite3.connect('file:'+str(boundary.resolve())+'?mode=ro',uri=True) as db:rows=db.execute('select shapeName,shapeGroup,shapeID from globalADM1').fetchall()
index=defaultdict(list)
for name,country,code in rows:index[country,normalize(name)].append(dict(shapeName=name,shapeGroup=country,shapeID=code))
records=[];seen=set()
for e in entities:
 code=str(e['code']);assert code not in seen;seen.add(code);country=e['attrs']['country_code'];country3=iso.get(country);matches=index.get((country3,normalize(e['name'])),[]) if country3 else []
 records.append(dict(ioda_region=code,ioda_country=country,wb_country_id=country3,ioda_name=e['name'],ioda_ne_region_id=e['attrs'].get('ne_region_id'),candidate_boundaries=matches,status='unique_exact_name_candidate' if len(matches)==1 else 'unmatched_exact_name' if not matches else 'ambiguous_exact_name',approved_for_spatial_exposure=False,reason='Name equality only: source administrative extent, version and geometry correspondence not established; do not infer a mapping from IODA or NaturalEarth IDs to geoBoundaries shapeID.'))
sources.verify(Path(__file__));sources.check();out.mkdir(parents=True)
summary=dict(ioda_entities=len(records),statuses=dict(Counter(r['status'] for r in records)),boundary_attributes=len(rows),approved_spatial_links=0,elapsed_seconds=time.monotonic()-started,scope='Candidate crosswalk audit only. Exact source country codes linked through retained WorldBank iso2Code/id; NFC casefold whitespace only, no accent stripping, transliteration, aliases or fuzzy matching. GeoNames/name equality is not spatial validation. No new downloads or geometry edits.')
for n,v in [('links.json',records),('summary.json',summary)]: (out/n).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
(out/'manifest.json').write_text(json.dumps(dict(inputs=sources.entries,outputs={n:Sources().verify(out/n) for n in ('links.json','summary.json')}),indent=2)+'\n');print(json.dumps(summary))
