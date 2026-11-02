import unittest,tempfile,hashlib
from pathlib import Path
from docx import Document
from docx.shared import Inches,Pt
from scripts.merge_paper_tables import merge_documents
class MergeTests(unittest.TestCase):
 def test_separate_fonts_margins_tables_and_originals(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);a=Document();a.styles['Normal'].font.size=Pt(11);a.sections[0].left_margin=Inches(.85);a.add_paragraph('main');a.save(p/'a.docx')
   b=Document();b.styles['Normal'].font.size=Pt(9);b.sections[0].left_margin=Inches(.65);b.add_paragraph('table section');b.add_table(rows=1,cols=1).cell(0,0).text='scientific value';b.save(p/'b.docx')
   before=[hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ('a.docx','b.docx')];merge_documents(p/'a.docx',[p/'b.docx'],p/'out.docx');d=Document(p/'out.docx')
   self.assertEqual(len(d.sections),2);self.assertAlmostEqual(d.sections[0].left_margin.inches,.85,3);self.assertAlmostEqual(d.sections[1].left_margin.inches,.65,3)
   pp=next(x for x in d.paragraphs if x.text=='table section');self.assertEqual(pp.style.font.size.pt,9);self.assertEqual(d.styles['Normal'].font.size.pt,11);self.assertEqual(d.tables[0].cell(0,0).text,'scientific value');self.assertEqual(d.tables[0].cell(0,0).paragraphs[0].style.font.size.pt,9)
   self.assertEqual(before,[hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ('a.docx','b.docx')])
   with self.assertRaises(FileExistsError):merge_documents(p/'a.docx',[p/'b.docx'],p/'out.docx')
if __name__=='__main__':unittest.main()
