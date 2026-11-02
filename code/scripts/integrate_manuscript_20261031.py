"""Preserve prior manuscript; integrate completed diagnostics and scope correction."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]
paths=['deliverables/2026-10-30_HeatSignal_manuscript_text_v17.txt','deliverables/2026-10-30_HeatSignal_calendar_blocks_addendum.txt','deliverables/2026-10-31_HeatSignal_solar_definition_addendum.txt','deliverables/2026-10-30_SCOPE_RECONCILIATION.txt','analysis/2026-10-31_adm1_support/v1/support_summary/summary.json','analysis/2026-10-31_adm1_name_links/v1/summary.json','analysis/2026-10-31_adm1_name_links/v1/links.json']
content={p:(root/p).read_text() for p in paths};text=content[paths[0]]
old='''were absent from that archived source directory. This is a necessary-input
obstacle to reconstructing the full old-product reference, not evidence that
all possible external copies are absent. Header/calendar checks do not certify
raw temperature values. The old-product effect branch remains incomplete;
the reference is not shortened or borrowed from the primary product.'''
new='''were absent from that archived source directory. This inventory does not
establish that all possible external copies are absent. Header/calendar checks
do not certify raw temperature values. The proposal explicitly excludes completing
the old hourly queue from mandatory work and calls for the existing common-month
comparison, which is provided here. A full alternative-reference effect model
was not performed and is not claimed. Treating that optional reconstruction as
a mandatory delivery prerequisite was a scope error, corrected without replacing,
shortening or borrowing its missing reference data.'''
assert text.count(old)==1;text=text.replace(old,new)
links=json.loads(content[paths[-1]]);s=json.loads(content[paths[-2]])
assert len(links)==226 and s['approved_spatial_links']==0
assert sum(x['status']=='unique_exact_name_candidate' for x in links)==91
assert all(not x['approved_for_spatial_exposure'] for x in links)
adm='''Existing ADM1 support and geographic correspondence

The retained IODA ADM1 archive covers six countries (AU, BR, CA, CN, RU and US)
and 226 source regions. The 2018-2021 requests returned no series; these empty
responses are not observations or zeros. In 2022-2025, 2256 retained requests
returned 10572 series and 276 absent-series records. Independent scalar checks
reproduced every available native-sampling count and vector digest.

Of 2712 region by source by year records, 2554 had at least 80 percent finite
nonnegative coverage at their observed native sampling frequency, 95 were below
80 percent and 63 had no identifiable single annual sampling denominator.
These counts do not certify ten-minute eligibility. Twelve groups of regions
had exactly identical signal vectors; they cannot automatically be treated as
independent spatial evidence or confirmed measurement failures.

The retained IODA region metadata and geoBoundaries ADM1 file were both found.
Within source country codes linked through the retained World Bank ISO2/ISO3
metadata, 91 regions had one exact normalized-name boundary candidate and 135
had none. Only Unicode NFC, case folding and whitespace normalization were used;
there was no fuzzy matching, transliteration or invented ID correspondence.
Name equality does not certify administrative extent, vintage or geographic
correspondence. No links are approved for exposure aggregation on this evidence
alone, and no ADM1 temperature or effect estimates are asserted. The proposal
makes reliable ADM1 analysis conditional on support; this support assessment
is retained explicitly rather than reporting an unsupported regional effect.

Evidence: analysis/2026-10-31_adm1_support/v1 and
analysis/2026-10-31_adm1_name_links/v1 preserve complete records and source hashes.
'''
insert='\n\n'+content[paths[1]].strip()+'\n\n'+content[paths[2]].strip()+'\n\n'+adm.strip()+'\n\n'
assert text.count('\nReferences\n')==1;text=text.replace('\nReferences\n',insert+'References\n')
out=root/'deliverables/2026-10-31_HeatSignal_manuscript_text_v19.txt';assert not out.exists();out.write_text(text)
receipt=dict(inputs={p:hashlib.sha256(content[p].encode()).hexdigest() for p in paths},output=str(out.relative_to(root)),output_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),references_sections=text.count('\nReferences\n'),scope_correction_replacements=1,integrated=['supported calendar blocks','solar weather definitions','ADM1 native support and name-only mapping limits'],complete_delivery=False,docx_visual_acceptance=False)
(root/'outputs/2026-10-31_manuscript_text_v19_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
