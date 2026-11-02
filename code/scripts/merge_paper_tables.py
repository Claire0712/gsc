"""Append image-free table DOCX sources with isolated styles and section geometry."""
from copy import deepcopy
from pathlib import Path
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def merge_documents(main,appendices,output):
 output=Path(output)
 if output.exists():raise FileExistsError(output)
 doc=Document(main);body=doc.element.body
 for index,path in enumerate(appendices,1):
  src=Document(path)
  if src.element.body.xpath('.//*[@r:id or @r:embed or @r:link]'):raise ValueError('Appendices must have no linked media or external relationships')
  prefix=f'Appendix{index}_';styles={s.get(qn('w:styleId')):s for s in src.styles.element};wanted={'Normal'}
  for tag in ('pStyle','rStyle','tblStyle'):
   wanted.update(e.get(qn('w:val')) for e in src.element.body.xpath('.//w:'+tag))
  todo=list(wanted)
  while todo:
   sid=todo.pop()
   if sid not in styles:raise ValueError('Missing source style '+sid)
   for node in styles[sid].xpath('./w:basedOn | ./w:next | ./w:link'):
    parent=node.get(qn('w:val'))
    if parent not in wanted:wanted.add(parent);todo.append(parent)
  for sid in sorted(wanted):
   cloned=deepcopy(styles[sid]);cloned.set(qn('w:styleId'),prefix+sid);cloned.attrib.pop(qn('w:default'),None)
   for node in cloned.xpath('./w:name | ./w:basedOn | ./w:next | ./w:link'):
    value=node.get(qn('w:val'));node.set(qn('w:val'),prefix+value)
   doc.styles.element.append(cloned)
  # End the preceding section; the following terminal section uses source geometry.
  previous=deepcopy(body.sectPr);body.remove(body.sectPr)
  paragraph=OxmlElement('w:p');properties=OxmlElement('w:pPr');properties.append(previous);paragraph.append(properties);body.append(paragraph)
  for item in src.element.body:
   if item.tag==qn('w:sectPr'):continue
   cloned=deepcopy(item)
   pars=([cloned] if cloned.tag==qn('w:p') else [])+cloned.xpath('.//w:p')
   for p in pars:
    prop=p.get_or_add_pPr();style=prop.find(qn('w:pStyle'))
    if style is None:style=OxmlElement('w:pStyle');style.set(qn('w:val'),'Normal');prop.insert(0,style)
   for tag in ('pStyle','rStyle','tblStyle'):
    for node in cloned.xpath('.//w:'+tag):node.set(qn('w:val'),prefix+node.get(qn('w:val')))
   # Presentation-only whitespace correction; original archived reason strings stay intact.
   for node in cloned.xpath('.//w:t'):
    if node.text:node.text=node.text.replace('Below10 events or5 countries','Below 10 events or 5 countries')
   body.append(cloned)
  body.append(deepcopy(src.element.body.sectPr))
 doc.save(output)
 return dict(sections=len(doc.sections),tables=len(doc.tables),figures=len(doc.inline_shapes))
