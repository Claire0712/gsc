import hashlib,json,tempfile,unittest
from pathlib import Path
from scripts.variant_heat_stage import adapt

class HeatStageTests(unittest.TestCase):
    def fixture(self,p):
        (p/'v').mkdir();outputs={}
        for n in ['raw_events.csv','process_events.csv','analysis_events.csv','daily_heat_flags.csv.gz','warm_seasons.csv','rules.json']:
            b=b'fixture';(p/'v'/n).write_bytes(b);outputs['v/'+n]={'sha256':hashlib.sha256(b).hexdigest()}
        (p/'manifest.json').write_text(json.dumps(dict(status='completed',outputs=outputs)));(p/'status.json').write_text('{"status":"completed"}')
    def test_byte_identity_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'source';p.mkdir();self.fixture(p);o=Path(t)/'stage';adapt(p,'v',o)
            self.assertEqual((o/'analysis_events.csv').read_bytes(),b'fixture')
            self.assertEqual(json.loads((o/'manifest.json').read_text())['state'],'complete')
            with self.assertRaises(FileExistsError):adapt(p,'v',o)
    def test_corrupt_source_rejected_before_publishing(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'source';p.mkdir();self.fixture(p);(p/'v/analysis_events.csv').write_bytes(b'changed')
            with self.assertRaises(ValueError):adapt(p,'v',Path(t)/'stage')
