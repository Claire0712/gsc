import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from scripts.run_connection_baseline import Sources

class SourceChainTests(unittest.TestCase):
    def test_preserved_chain_and_tamper_rejected(self):
        from scripts.variant_weather_sources import resolve_sources
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); original=root/'original.json'; batch=root/'batch.json'
            payload={'state':'complete','sources':[{'month':'202201','sha256':'csv','audit_sha256':'audit'}]}
            original.write_text(json.dumps(payload))
            fp={'sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'bytes':original.stat().st_size}
            batch.write_text(json.dumps({'status':'completed','inputs':{str(original):fp}}))
            bfp={'sha256':hashlib.sha256(batch.read_bytes()).hexdigest(),'bytes':batch.stat().st_size}
            heat={'state':'complete','inputs':{str(batch):bfp}}
            self.assertEqual(resolve_sources(heat,batch,original,Sources()),payload['sources'])
            original.write_text('{}')
            with self.assertRaises(ValueError):resolve_sources(heat,batch,original,Sources())

    def test_unlinked_batch_rejected(self):
        from scripts.variant_weather_sources import resolve_sources
        with self.assertRaises(ValueError):resolve_sources({'inputs':{}},Path('/not-linked'),Path('/not-linked-original'),Sources())
