"""Deterministic manuscript integration; rendered QA is a separate required gate."""
from pathlib import Path
import hashlib,json,re
from docx import Document
from docx.shared import Inches,Pt,RGBColor

root=Path(__file__).resolve().parents[1]
out=root/'deliverables/2026-10-28_HeatSignal_manuscript_v11.docx'
assert not out.exists()
inputs=['2026-10-26_HeatSignal_essay_referenced_v10.txt','2026-10-27_HeatSignal_sync_results_addendum.txt','2026-10-28_HeatSignal_loyo_results_addendum.txt','2026-10-28_HeatSignal_common_sample_addendum.txt']
doc=Document();section=doc.sections[0]
section.page_width=Inches(8.5);section.page_height=Inches(11)
section.top_margin=section.bottom_margin=Inches(.8)
section.left_margin=section.right_margin=Inches(.85)
for name in ('Normal','Title','Heading 1','Heading 2'):
 style=doc.styles[name];style.font.name='Arial';style.font.color.rgb=RGBColor(0,0,0)
doc.styles['Normal'].font.size=Pt(11)
doc.styles['Normal'].paragraph_format.space_after=Pt(7)
doc.styles['Normal'].paragraph_format.line_spacing=1.12
doc.add_paragraph('Digital connectivity resilience under heat stress',style='Title')
doc.add_paragraph('HeatSignal research manuscript 28 October 2026')
doc.add_paragraph('The supported retrospective comparisons do not establish a consistent heat-associated deterioration across signals and reference definitions. Sample support, uncertain recovery and sensitivity to the short reference constrain interpretation. Remaining uncompleted analyses are identified explicitly; the manuscript does not certify causal attribution or final study acceptance.')
for index,name in enumerate(inputs):
 text=(root/'deliverables'/name).read_text()
 if index==0:
  text='\n'.join(text.splitlines()[5:])
  old='The common-control curve refit addresses daily trajectory support, not\ncommon-sample event-level heat-dose or recovery models.'
  assert text.count(old)==1
  text=text.replace(old,'The common-control curve refit addresses daily trajectory support. Common-sample dose and recovery model checks are reported in the updated component below.')
  text=text.replace('as do separate DLEP social weighting and final reconciliation of threshold\nand season sensitivities.','DLEP social weighting and the four omitted-reference-year curve and model tables have since been completed; their evidence is reported in the updated components and accompanying tables.')
 else:
  doc.add_heading(('Synchronous candidate sensitivity','Short reference sensitivity','Common sample model support')[index-1],level=1)
  text='\n'.join(text.splitlines()[3:])
 for block in re.split(r'\n\s*\n',text):
  paragraph=' '.join(block.split())
  if not paragraph:continue
  if len(block.splitlines())==1 and len(paragraph)<90 and not re.search(r'[.;:\[\]]',paragraph):
   doc.add_heading(paragraph,level=2)
  else:doc.add_paragraph(paragraph)
doc.add_page_break()
doc.add_heading('Short reference sensitivity figure',level=1)
doc.add_picture(str(root/'deliverables/2026-10-28_figures_loyo/loyo_dayzero.png'),width=Inches(5.6))
caption=(root/'deliverables/2026-10-28_figures_loyo/caption.txt').read_text().split('\n\nSelection record:')[0]
doc.add_paragraph(' '.join(caption.split()))
doc.save(out)
manifest={name:hashlib.sha256((root/'deliverables'/name).read_bytes()).hexdigest() for name in inputs}
(root/'deliverables/2026-10-28_manuscript_source_manifest.json').write_text(json.dumps(dict(inputs=manifest,output=out.name,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),status='created_render_QA_pending'),indent=2)+'\n')
