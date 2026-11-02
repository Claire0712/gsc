import unittest
import tempfile
import csv
import json
import hashlib
from pathlib import Path
from scripts import build_stop_windows as module
from scripts.build_stop_windows import classify_record


def row(**changes):
    data=dict(source_row='1',normalized_start_date='2024-01-01',normalized_end_date='2024-01-03',date_interval_status='complete',bounded_interval_eligible='1',country_match_status='exact_name_match',matched_worldbank_iso3='AAA',qa_flags='',normalized_geo_scope='single_locality',area_name='Town',shutdown_extent='Full network')
    data.update(changes)
    return data


class StopWindowsTests(unittest.TestCase):
    def test_driver_fresh_output_and_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); aux=root/'aux'; cross=root/'cross'
            aux.mkdir(); cross.mkdir()
            for folder,name,rows in [(aux,'stop_cleaned.csv',[row()]),(cross,'joint_crosswalk.csv',[dict(ioda_iso2='AA',joint_country_id='AAA',joint_status='exact_joint_match')])]:
                path=folder/name
                with path.open('w',newline='') as f:
                    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
                b=path.read_bytes()
                size_key='size_bytes' if folder==aux else 'bytes'
                (folder/'manifest.json').write_text(json.dumps(dict(outputs={name:{size_key:len(b),'sha256':hashlib.sha256(b).hexdigest()}})))
            self.assertTrue(hasattr(module,'run'),'driver is not implemented')
            result=module.run(aux,cross,root/'output')
            self.assertEqual(result['counts']['records'],1)
            self.assertEqual(result['counts']['with_windows'],1)
            self.assertTrue((root/'output'/'manifest.json').exists())
            with self.assertRaises(FileExistsError): module.run(aux,cross,root/'output')
            (aux/'stop_cleaned.csv').write_text('corrupt')
            with self.assertRaises(ValueError): module.run(aux,cross,root/'bad')

    def test_complete(self):
        result=classify_record(row(),{'AAA'})
        self.assertEqual(result['windows']['main'],[1704067200,1704326400])
        self.assertEqual(result['windows']['main'],result['windows']['unknown_end_plusminus30'])
        self.assertFalse(result['national_outage_inferred'])

    def test_missing_end(self):
        r=classify_record(row(normalized_end_date='',date_interval_status='incomplete',bounded_interval_eligible='0'),{'AAA'})
        self.assertEqual(r['windows']['main'],[1704067200,1704153600])
        self.assertEqual(r['windows']['unknown_end_plusminus7'],[1703462400,1704758400])
        self.assertEqual(r['windows']['unknown_end_plusminus30'],[1701475200,1706745600])
        self.assertTrue(r['end_unknown'])

    def test_bad_dates_not_guessed(self):
        for changes in [dict(normalized_start_date=''),dict(normalized_end_date='2023-12-30',date_interval_status='reversed'),dict(normalized_end_date='',qa_flags='end_date_invalid'),dict(normalized_start_date='notdate'),dict(normalized_end_date='',date_interval_status='complete')]:
            self.assertFalse(classify_record(row(**changes),{'AAA'})['windows'])

    def test_exact_country_gate(self):
        for r,allowed in [(row(),{'BBB'}),(row(country_match_status='unmatched_exact_name'),{'AAA'})]:
            self.assertFalse(classify_record(r,allowed)['windows'])

    def test_scope_preserved(self):
        r=classify_record(row(normalized_geo_scope='unknown',area_name='Nationwide'),{'AAA'})
        self.assertTrue(r['scope_uncertain'])
        self.assertFalse(r['national_outage_inferred'])
        self.assertEqual(r['area_name'],'Nationwide')


if __name__=='__main__': unittest.main()
