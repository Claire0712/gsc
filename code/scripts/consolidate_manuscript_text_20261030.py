"""Integrate completed components; preserve earlier manuscript versions."""
from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1];base=root/'deliverables'
names=['2026-10-28_HeatSignal_manuscript_text_v12.txt','2026-10-29_HeatSignal_precipitation_addendum.txt','2026-10-29_HeatSignal_temperature_agreement_addendum.txt']
main,rain,temp=[(base/n).read_text() for n in names]
marker='\nReferences\n';assert main.count(marker)==1
position=main.index(marker);references=main[position:];main=main[:position]
main=main.replace('Consolidated manuscript text as of 28 October 2026','Consolidated manuscript text as of 30 October 2026',1)
old='Their full coverage and the\ncost of a consistent reference/event reconstruction still require assessment.'
new='A subsequent retained-source inventory found complete hourly calendars for\n2018-01 through 2019-06, but 30 reference months (2019-07 through 2021-12)\nwere absent from that archived source directory. This is a necessary-input\nobstacle to reconstructing the full old-product reference, not evidence that\nall possible external copies are absent. Header/calendar checks do not certify\nraw temperature values. The old-product effect branch remains incomplete;\nthe reference is not shortened or borrowed from the primary product.'
assert temp.count(old)==1;temp=temp.replace(old,new)
note='Integration status, 30 October 2026\n\nThe two components below are incorporated into this manuscript text rather than held until every analysis is complete. Their numerical and descriptive claims retain their stated samples and limitations. Nonheat pseudo-event production has completed, but its statistical acceptance is still pending and its results are not asserted here. Sequence-preserving date-block placebo, other outstanding supported exposure checks, final Word/PDF, publication figures, interactive-system acceptance and complete reproducibility delivery are not certified. The original delivery deadline was missed; no replacement date or reduced scope is declared.\n\n'
target=base/'2026-10-30_HeatSignal_manuscript_text_v13.txt';assert not target.exists()
target.write_text(main+'\n\n'+note+rain+'\n\n'+temp+references)
content=target.read_text();assert content.count(marker)==1 and content.index(marker)>content.index('Existing temperature products on common country days')
receipt=dict(output=str(target.relative_to(root)),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),inputs={n:hashlib.sha256((base/n).read_bytes()).hexdigest() for n in names},references_after_all_components=True,whole_study_accepted=False,formatted_document_accepted=False)
path=root/'outputs/2026-10-30_manuscript_text_v13_receipt.json';assert not path.exists();path.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
