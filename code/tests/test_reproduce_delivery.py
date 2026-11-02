import tempfile,unittest,hashlib
from pathlib import Path
from scripts.reproduce_delivery import verify_manifest
class ManifestTests(unittest.TestCase):
 def test_valid_and_corruption(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'a').write_bytes(b'abc');entry={'a':{'sha256':hashlib.sha256(b'abc').hexdigest(),'bytes':3}}
   self.assertEqual(verify_manifest(p,entry),1);(p/'a').write_bytes(b'bad')
   with self.assertRaises(ValueError):verify_manifest(p,entry)
 def test_escape(self):
  with tempfile.TemporaryDirectory() as d:
   for name in ('../escape','/tmp/escape'):
    with self.assertRaises(ValueError):verify_manifest(Path(d),{name:{'sha256':'','bytes':0}})

class RebuildSpecificationTests(unittest.TestCase):
 def test_declared_exporters_and_text_are_used(self):
  from scripts.reproduce_delivery import rebuild_commands
  commands=rebuild_commands({'export_scripts':['scripts/a.py','scripts/b.py'],'text_source':'deliverables/new_text.txt'},'python')
  self.assertEqual(commands[:2],[['python','scripts/a.py'],['python','scripts/b.py']]);self.assertIn('deliverables/new_text.txt',commands[-1]);self.assertNotIn('deliverables/2026-11-01_HeatSignal_manuscript_text_v26.txt',commands[-1])
 def test_extra_document_composition(self):
  from scripts.reproduce_delivery import compose_extra_documents,semantic_docx
  from docx import Document
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for name,text in [('base.docx','Original'),('added.docx','All interactions')]:
    x=Document();x.add_paragraph(text);x.save(root/name)
   compose_extra_documents(root,{'composed_documents':[{'base':'base.docx','appendices':['added.docx'],'target':'merged.docx'}]})
   self.assertEqual([p for p in semantic_docx(root/'merged.docx')['paragraphs'] if p],['Original','All interactions'])
