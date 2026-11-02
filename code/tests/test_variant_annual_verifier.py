import csv,hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path

class AnnualVerifierTests(unittest.TestCase):
    def execute(self,claim):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);quality=root/'quality';quality.mkdir();out=root/'output';d=out/'v';d.mkdir(parents=True)
            def write(p,rr):
                with p.open('w',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
            # 2023 passes exactly80%; full right-open window touches missing2024.
            write(quality/'coverage_annual.csv',[dict(country_id='AA',signal='ping-slash24',year='2023',valid_points='80',expected_points='100')])
            row=dict(ioda_iso2='AA',signal='ping-slash24',core_start_utc='2023-12-31T00:00:00Z',full_end_exclusive_utc='2024-01-02T00:00:00Z',annual_years='2023;2024',annual_missing_years='2024',annual_failed_years='',annual_all_window_years_pass=str(claim),complete_full='True',unmasked_potential_reference_all_slots='True',provisional_full_and_annual=str(claim),provisional_full_refs_and_annual=str(claim),final_sample_eligible='False')
            write(d/'annual_event_screen.csv',[row]);h=hashlib.sha256((d/'annual_event_screen.csv').read_bytes()).hexdigest()
            (d/'manifest.json').write_text(json.dumps(dict(status='completed',outputs={'annual_event_screen.csv':{'sha256':h}})))
            return subprocess.run([sys.executable,'outputs/2026-10-20_verify_variant_annual.py','--root',str(out),'--quality',str(quality)],capture_output=True).returncode
    def test_missing_cross_year_is_not_pass(self):self.assertEqual(self.execute(False),0)
    def test_false_pass_is_detected(self):self.assertNotEqual(self.execute(True),0)

if __name__=='__main__':unittest.main()
