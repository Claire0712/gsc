"""Format the integrated text without changing evidence; render QA stays separate."""
from pathlib import Path
import re,json,hashlib,argparse
from docx import Document
from docx.shared import Inches,Pt,RGBColor
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--source',default='deliverables/2026-11-01_HeatSignal_manuscript_text_v21.txt');parser.add_argument('--output',default='deliverables/2026-11-01_HeatSignal_manuscript_v22.docx');parser.add_argument('--receipt',default='outputs/2026-11-01_manuscript_v22_source_receipt.json');args=parser.parse_args()
source=root/args.source
target=root/args.output;assert not target.exists()
text=source.read_text();assert text.count('\nReferences\n')==1
doc=Document();section=doc.sections[0]
section.page_width=Inches(8.5);section.page_height=Inches(11)
section.top_margin=section.bottom_margin=Inches(.8)
section.left_margin=section.right_margin=Inches(.85)
for name in ('Normal','Title','Heading 1','Heading 2'):
 s=doc.styles[name];s.font.name='Arial';s.font.color.rgb=RGBColor(0,0,0)
doc.styles['Normal'].font.size=Pt(11)
doc.styles['Normal'].paragraph_format.space_after=Pt(7)
doc.styles['Normal'].paragraph_format.line_spacing=1.12
figure=root/'deliverables/2026-10-28_figures_loyo/loyo_dayzero.png'
caption=root/'deliverables/2026-10-28_figures_loyo/caption.txt'
spatial_figure=root/'deliverables/2026-11-01_pixel_spatial_map_v3/pixel_local_exceedance_country_map.png'
spatial_caption=root/'deliverables/2026-11-01_pixel_spatial_map_v3/caption.txt'
blocks=re.split(r'\n\s*\n',text)
for i,block in enumerate(blocks):
 p=' '.join(block.split())
 if not p:continue
 if i==0:doc.add_paragraph(p,style='Title');continue
 if p=='References':
  doc.add_page_break();doc.add_heading('Short reference sensitivity figure',level=1)
  doc.add_picture(str(figure),width=Inches(5.6));doc.add_paragraph(' '.join(caption.read_text().split('\n\nSelection record:')[0].split()))
  doc.add_page_break();doc.add_heading('Local exceedance below the country threshold',level=1)
  doc.add_picture(str(spatial_figure),width=Inches(6.75));doc.add_paragraph(' '.join(spatial_caption.read_text().replace('No new geographic data were downloaded.','').split()))
  doc.add_page_break()

 if '\n' not in block.strip() and len(p)<90 and not re.search(r'[.;:\[\]]',p):doc.add_heading(p,level=1)
 else:doc.add_paragraph(p)
for tree in (doc.styles.element,doc.element):
 for border in tree.xpath('.//w:pBdr'):border.getparent().remove(border)
assert not doc.styles.element.xpath('.//w:pBdr') and not doc.element.xpath('.//w:pBdr')
doc.save(target)
assert len(doc.paragraphs)>50
receipt=dict(output=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),inputs={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,figure,caption,spatial_figure,spatial_caption,Path(__file__))},status='created_render_QA_pending',whole_study_accepted=False)
out=root/args.receipt;assert not out.exists();out.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
