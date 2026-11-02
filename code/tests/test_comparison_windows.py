import importlib.util
import csv
import hashlib
import json
from pathlib import Path
import unittest
import numpy as np

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/run_comparison_windows.py'
START=1711929600
DAY=86400

class ComparisonWindowsTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(),'comparison implementation missing')
        spec=importlib.util.spec_from_file_location('scripts.comparison',SCRIPT)
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)

    def sample(self,days=2):
        end=START+days*DAY
        times=np.arange(START-7*DAY,max(end+3*DAY,START+8*DAY),600,dtype=np.int64)
        n=len(times)
        result=dict(target_timestamps=times,target_values=np.full(n,10.),target_valid=np.ones(n,dtype=bool),target_annual_eligible=np.ones(n,dtype=bool),baseline_available=np.ones(n,dtype=bool),analysis_available=np.ones(n,dtype=bool))
        bits=np.zeros(n,dtype=np.uint8);bits[(times>=START)&(times<end+3*DAY)]|=1
        return result,bits,np.zeros(n,dtype=bool),end

    def stats(self,result,bits,other,end,role='heat'):
        return self.m.window_stats(result,bits,other,START,end,role)

    def test_exact_short_and_long_windows(self):
        for days,nintegral in [(2,720),(20,3312)]:
            r,b,o,e=self.sample(days);a,s=self.stats(r,b,o,e)
            self.assertEqual(s['preperiod_expected_slots'],1008)
            self.assertEqual(s['integral_expected_slots'],nintegral)
            self.assertEqual(s['curve_expected_slots'],2160)
            self.assertEqual(len(r['target_timestamps']),max(2160,1008+nintegral))
            self.assertTrue(s['matching_technical_available'])

    def test_raw_features_do_not_depend_on_future_reference(self):
        r,b,o,e=self.sample();r['baseline_available'][:1008]=False;r['analysis_available'][:1008]=False
        a,s=self.stats(r,b,o,e)
        self.assertEqual(s['raw_pre_level'],10)
        self.assertEqual(s['raw_pre_mad_over_median'],0)
        self.assertFalse(s['preperiod_reference_complete'])
        self.assertFalse(s['matching_technical_available'])

    def test_raw_features_hand_calculated_linear_time(self):
        r,b,o,e=self.sample();x=np.arange(1008)/144;r['target_values'][:1008]=10+2*x
        a,s=self.stats(r,b,o,e)
        median=10+2*503.5/144
        self.assertAlmostEqual(s['raw_pre_level'],median)
        self.assertAlmostEqual(s['raw_pre_mad_over_median'],3.5/median)
        self.assertAlmostEqual(s['raw_pre_slope_per_day_over_median'],2/median)

    def test_zero_median_retained_with_missing_normalized_features(self):
        r,b,o,e=self.sample();r['target_values'][:1008]=0
        a,s=self.stats(r,b,o,e)
        self.assertEqual(s['raw_pre_level'],0)
        self.assertIsNone(s['raw_pre_mad_over_median'])
        self.assertEqual(s['raw_pre_feature_reason'],'nonpositive_median')

    def test_missing_negative_or_failed_year_prevents_features(self):
        for reason in ('missing','annual','negative'):
            r,b,o,e=self.sample()
            if reason=='annual':r['target_annual_eligible'][0]=False
            else:r['target_values'][0]=np.nan if reason=='missing' else -1;r['target_valid'][0]=False
            a,s=self.stats(r,b,o,e)
            self.assertIsNone(s['raw_pre_level'])
            self.assertFalse(s['preperiod_raw_available'])

    def test_pre_heat_stop_cyclone_edge_all_block_raw_features(self):
        for bit in (1,2,4,16):
            r,b,o,e=self.sample();b[0]|=bit;a,s=self.stats(r,b,o,e)
            self.assertFalse(s['preperiod_raw_available'])
            self.assertIsNone(s['raw_pre_level'])
            field={1:'heat_forbidden',2:'stop',4:'cyclone',16:'coverage_unknown'}[bit]
            self.assertEqual(s['preperiod_'+field+'_slots'],1)

    def test_own_heat_recovery_allowed_control_heat_forbidden(self):
        r,b,o,e=self.sample();a,s=self.stats(r,b,o,e)
        self.assertTrue(s['integral_technical_available'])
        self.assertTrue(a['target_technical_available'][1008:].all())
        a,s=self.stats(r,b,o,e,role='control')
        self.assertFalse(s['integral_technical_available'])

    def test_other_heat_in_curve_tail_blocks_curve_not_integral(self):
        r,b,o,e=self.sample();i=np.where(r['target_timestamps']==START+6*DAY)[0][0];o[i]=True;b[i]|=1
        a,s=self.stats(r,b,o,e)
        self.assertTrue(s['matching_technical_available'])
        self.assertFalse(s['curve_technical_available'])

    def test_no_target_grid_shortening(self):
        r,b,o,e=self.sample();r={k:v[:-1] for k,v in r.items()}
        with self.assertRaises(ValueError):self.stats(r,b[:-1],o[:-1],e)

    def test_control_identity_preserved_for_same_dates(self):
        events=[dict(event_id='A',country_id='AAA',ioda_iso2='AA',start_date='2024-04-01',end_exclusive_utc='2024-04-03T00:00:00Z'),dict(event_id='B',country_id='AAA',ioda_iso2='AA',start_date='2024-04-08',end_exclusive_utc='2024-04-10T00:00:00Z')]
        controls=[dict(event_id=e['event_id'],country_id='AAA',control_id=e['event_id']+'_x',control_start_utc='2024-03-01T00:00:00Z',control_end_exclusive_utc='2024-03-03T00:00:00Z',matching_calendar_candidate='True') for e in events]
        windows=self.m.window_definitions(events,controls)
        self.assertEqual(len(windows),4)
        self.assertEqual(len({w['window_id'] for w in windows}),4)

class ComparisonDriverTests(unittest.TestCase):
    def setUp(self):
        ComparisonWindowsTests.setUp(self)
        fixture_path=Path(__file__).with_name('test_connection_baseline_runner.py')
        spec=importlib.util.spec_from_file_location('baseline_fixture',fixture_path)
        fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
        self.f=fixture.BaselineRunnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.run_stage()
        self.calendar=self.f.root/'calendar'
        self.m.calendar.run(self.f.dirs['candidate'],self.f.dirs['heat'],self.calendar)

    def run_stage(self):
        return self.m.run(**self.f.dirs,calendar_dir=self.calendar,baseline=self.f.root/'output',
                          output=self.f.root/'comparison',countries=['AAA'],signals=['ping-slash24'])

    def test_real_fixture_extended_artifacts_and_feature_columns(self):
        self.assertTrue(hasattr(self.m,'run'),'comparison runner missing')
        result=self.run_stage()
        self.assertEqual(result['heat_windows'],1)
        self.assertGreater(result['control_windows'],0)
        with (self.f.root/'comparison/window_audit.csv').open() as f:rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),result['signal_windows'])
        heat=next(r for r in rows if r['role']=='heat')
        self.assertEqual(int(heat['preperiod_expected_slots']),1008)
        self.assertEqual(heat['raw_pre_level'],'')
        self.assertEqual(int(heat['preperiod_stop_slots']),144)
        self.assertEqual(heat['raw_pre_feature_reason'],'raw_preperiod_not_qualified')
        self.assertEqual(heat['matched'],'False')
        with self.assertRaises(FileExistsError):self.run_stage()

    def test_changed_source_chain_rejected(self):
        self.assertTrue(hasattr(self.m,'run'),'comparison runner missing')
        self.f.annual[0]['valid_points']=0;self.f.annual[0]['candidate_80pct']='False'
        self.f.write_csv('quality','coverage_annual.csv',self.f.annual);self.f.flush()
        with self.assertRaisesRegex(ValueError,'chain|ancestry'):self.run_stage()

    def test_calendar_tampered_bound_even_with_updated_hash_rejected(self):
        self.assertTrue(hasattr(self.m,'run'),'comparison runner missing')
        p=self.calendar/'control_calendar.csv'
        with p.open() as f:r=list(csv.DictReader(f))
        r[0]['control_end_exclusive_utc']='2024-04-30T00:00:00Z'
        with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(r[0]));w.writeheader();w.writerows(r)
        m=json.loads((self.calendar/'manifest.json').read_text());b=p.read_bytes()
        m['outputs'][p.name]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
        (self.calendar/'manifest.json').write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError,'[Cc]alendar'):self.run_stage()


if __name__=='__main__':unittest.main()
