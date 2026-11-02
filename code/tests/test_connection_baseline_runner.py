import calendar
import csv
import hashlib
import gzip
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from scripts import audit_candidate_connectivity as archive


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/run_connection_baseline.py'
T = archive.utc('2024-04-01T00:00:00Z')


class BaselineRunnerTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'baseline runner missing')
        spec = importlib.util.spec_from_file_location('scripts.runner', SCRIPT)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dirs = {k: self.root/k for k in ('preflight', 'candidate', 'connection', 'quality', 'heat', 'stop', 'cyclone')}
        for p in self.dirs.values(): p.mkdir()
        self.manifests = {k: {'outputs': {}} for k in self.dirs}
        for k, state in [('preflight','completed'), ('candidate','completed'), ('stop','completed'), ('cyclone','completed')]:
            self.write_json(k, 'status.json', {('state' if k=='cyclone' else 'status'):state}, manifest=False)
        self.write_json('cyclone', 'status.json', {'state':'completed','completed_countries':['AAA']}, manifest=False)
        self.manifests['candidate']['status'] = 'completed'
        self.manifests['connection'].update(state='complete', quarters=archive.QUARTERS)
        self.manifests['heat']['state'] = 'complete'
        self.manifests['quality']['state'] = 'completed'
        self.write_json('quality', 'summary.json', {'quality_pass':True})
        self.cross = [dict(ioda_iso2='AA', joint_country_id='AAA', joint_status='exact_joint_match')]
        self.write_csv('preflight','joint_crosswalk.csv',self.cross)
        self.events = [self.event('forward', T, 'forward'), self.event('held', T+100*86400, 'held_stop_review'),
                       self.event('cold', T+7*86400, 'not_weather_candidate')]
        self.write_events()
        annual=[]
        for signal,cadence in archive.SIGNALS.items():
            for year in range(2022,2026):
                total=(366 if calendar.isleap(year) else 365)*86400//cadence
                annual.append(dict(country_id='AA', signal=signal, year=year, expected_points=total,
                                   valid_points=total,candidate_80pct='True'))
        self.annual=annual
        self.write_csv('quality','coverage_annual.csv',annual)
        self.write_json('stop','stop_windows.json',{'records':[dict(source_row='1',country_id='AAA',windows={'main':[T-7*86400,T-7*86400+86400]},reasons=[],end_unknown=True,national_outage_inferred=False)]})
        self.write_json('cyclone','AAA.json',dict(country='AAA',windows=[dict(country='AAA',sid='X',radius_km=300,half_width_hours=24,mode='conservative',start_utc_seconds=T-14*86400-86400,end_utc_seconds=T-14*86400)],points=[]))
        self.write_json('cyclone','provenance.json',dict(selected_ids=['AAA'],rules={'closed_utc_windows':True}))
        for signal in archive.SIGNALS:
            for q in archive.QUARTERS:
                start,end=archive.BOUNDS[q]
                times=np.arange(start,end,600,dtype=np.int64)
                values=np.full((1,len(times)),10.,dtype=np.float64)
                values[0,times==T]=0
                self.write_npz(q,signal,values=values,country_ids=np.array(['AA']),native_phase_seconds=np.array([0],dtype=np.int16),interval_start_utc=times)
        self.flush()

    def event(self,eid,start,route):
        return dict(event_id=eid,country_id='AAA',start_date=archive.iso(start)[:10],end_exclusive_utc=archive.iso(start+86400),
                    weather_candidate=str(route!='not_weather_candidate'),network_screened='False',review_only='1',
                    review_window_start_utc=archive.iso(start),review_window_end_exclusive_utc=archive.iso(start+4*86400),route=route,ioda_iso2='AA')

    def write_events(self):
        self.write_csv('candidate','event_routing.csv',self.events)
        self.write_csv('candidate','forward_candidates.csv',[e for e in self.events if e['route']=='forward'])
        self.write_csv('candidate','held_stop_review.csv',[e for e in self.events if e['route']=='held_stop_review'])
        self.write_csv('heat','analysis_events.csv',[{k:v for k,v in e.items() if k not in ('route','ioda_iso2')} for e in self.events])
        self.daily=[dict(country_id=e['country_id'],date=e['start_date'],analysis_event_id=e['event_id']) for e in self.events]
        self.write_daily()

    def write_daily(self):
        stream=io.StringIO();w=csv.DictWriter(stream,fieldnames=list(self.daily[0]));w.writeheader();w.writerows(self.daily)
        (self.dirs['heat']/'daily_heat_flags.csv.gz').write_bytes(gzip.compress(stream.getvalue().encode()))
        self.register('heat','daily_heat_flags.csv.gz')

    def register(self,k,name):
        b=(self.dirs[k]/name).read_bytes()
        entry={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
        self.manifests[k]['outputs'][name]=entry

    def write_json(self,k,name,value,manifest=True):
        (self.dirs[k]/name).write_text(json.dumps(value))
        if manifest:self.register(k,name)

    def write_csv(self,k,name,rows):
        stream=io.StringIO();w=csv.DictWriter(stream,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        (self.dirs[k]/name).write_text(stream.getvalue());self.register(k,name)

    def write_npz(self,q,signal,**arrays):
        name=f'ioda_{q}_{signal}.npz';np.savez_compressed(self.dirs['connection']/name,**arrays);self.register('connection',name)

    def flush(self):
        for k,m in self.manifests.items():
            value=dict(m)
            if k=='connection':value['outputs']=[dict(file=n,**entry) for n,entry in m['outputs'].items()]
            if k=='cyclone':value['outputs']=[dict(path=str(self.dirs[k]/n),size_bytes=e['bytes'],sha256=e['sha256']) for n,e in m['outputs'].items()]
            if k=='heat':value['outputs']={n:{'sha256':e['sha256']} for n,e in m['outputs'].items()}
            (self.dirs[k]/'manifest.json').write_text(json.dumps(value))

    def run_stage(self,**kw):
        return self.m.run(**self.dirs,output=self.root/'output',countries=['AAA'],signals=['ping-slash24'],**kw)

    def points(self):
        paths=list((self.root/'output').glob('points_*.npz'));self.assertEqual(len(paths),1)
        with np.load(paths[0],allow_pickle=False) as a:return {k:a[k] for k in a.files}

    def test_masks_counts_complete_window_zero_target_and_held_preserved(self):
        r=self.run_stage();p=self.points()
        self.assertEqual(r['selected_events'],1)
        self.assertEqual(r['route_counts']['held_stop_review'],1)
        self.assertEqual(len(p['target_timestamps']),576)
        self.assertEqual(p['reference_count'][0],5)
        self.assertEqual(p['baseline'][0],10)
        self.assertTrue(p['target_valid'][0])
        self.assertEqual(p['target_values'][0],0)
        self.assertTrue(p['target_exclusion_bits'][0]&1)
        self.assertEqual(p['reference_exclusion_bits'][0].tolist(),[0,0,12,2,1,0,0,0])
        self.assertEqual((self.root/'output'/'held_stop_review.csv').read_bytes(),(self.dirs['candidate']/'held_stop_review.csv').read_bytes())
        self.assertFalse(r['dhrd_computed'])

    def test_annual_gate_is_source_year_specific_and_missing_is_false(self):
        self.annual=[r for r in self.annual if not (r['signal']=='ping-slash24' and r['year']==2024)]
        self.write_csv('quality','coverage_annual.csv',self.annual);self.flush();self.run_stage();p=self.points()
        self.assertEqual(p['reference_count'][0],0)
        self.assertFalse(p['target_annual_eligible'][0])

    def test_failed_cyclone_stage_blocks(self):
        self.write_json('cyclone','status.json',{'state':'running'},manifest=False)
        with self.assertRaisesRegex(ValueError,'completed'):self.run_stage()

    def test_failed_stop_stage_blocks(self):
        self.write_json('stop','status.json',{'status':'failed'},manifest=False)
        with self.assertRaisesRegex(ValueError,'completed'):self.run_stage()

    def test_hash_mismatch_blocks(self):
        with (self.dirs['stop']/'stop_windows.json').open('a') as f:f.write(' ')
        with self.assertRaisesRegex(ValueError,'hash|provenance'):self.run_stage()

    def test_cross_quarter_phase_mismatch_blocks(self):
        name=self.dirs['connection']/'ioda_2024Q2_ping-slash24.npz'
        with np.load(name) as a:arrays={k:a[k] for k in a.files}
        arrays['native_phase_seconds'][0]=1
        self.write_npz('2024Q2','ping-slash24',**arrays);self.flush()
        with self.assertRaisesRegex(ValueError,'phase'):self.run_stage()

    def test_offgrid_archive_blocks(self):
        name=self.dirs['connection']/'ioda_2024Q2_ping-slash24.npz'
        with np.load(name) as a:arrays={k:a[k] for k in a.files}
        arrays['interval_start_utc']+=1
        self.write_npz('2024Q2','ping-slash24',**arrays);self.flush()
        with self.assertRaisesRegex(ValueError,'grid'):self.run_stage()

    def test_catalogue_missing_nonwarm_event_blocks(self):
        self.write_csv('heat','analysis_events.csv',self.events[:2]);self.flush()
        with self.assertRaisesRegex(ValueError,'catalogue'):self.run_stage()

    def test_forward_file_cannot_silently_release_held_event(self):
        self.write_csv('candidate','forward_candidates.csv',self.events[:2]);self.flush()
        with self.assertRaisesRegex(ValueError,'routing'):self.run_stage()

    def test_boundary_window_preserved_outside_source_grid(self):
        self.events[0]=self.event('forward',archive.ANALYSIS_END-86400,'forward')
        self.write_events();self.flush();self.run_stage();p=self.points()
        self.assertEqual(len(p['target_timestamps']),576)
        self.assertEqual(np.count_nonzero(p['target_present']),144)
        self.assertEqual(np.count_nonzero(p['analysis_available'][144:]),0)

    def test_unknown_country_and_existing_output_rejected(self):
        with self.assertRaises(ValueError):self.m.run(**self.dirs,output=self.root/'bad',countries=['BBB'],signals=['ping-slash24'])
        self.run_stage()
        with self.assertRaises(FileExistsError):self.run_stage()

    def test_closed_cyclone_and_rightopen_stop_endpoints(self):
        stamps=np.array([0,600,1200,1800],dtype=np.int64)
        np.testing.assert_array_equal(self.m.interval_mask(stamps,[(600,1200)],closed=True),[False,True,True,False])
        np.testing.assert_array_equal(self.m.interval_mask(stamps,[(600,1200)],closed=False),[False,True,False,False])

    def test_2021_heat_recovery_context_excludes_2022_reference(self):
        self.events[0]=self.event('forward',archive.utc('2022-01-08T00:00:00Z'),'forward')
        self.write_events()
        self.daily.append(dict(country_id='AAA',date='2021-12-31',analysis_event_id='prior_context'))
        self.write_daily();self.flush();self.run_stage();p=self.points()
        self.assertTrue(p['reference_exclusion_bits'][0,3]&1)

    def test_last_day_reference_and_target_cyclone_coverage_unknown(self):
        self.events[0]=self.event('forward',archive.utc('2025-12-24T00:00:00Z'),'forward')
        self.write_events();self.flush();self.run_stage();p=self.points()
        self.assertTrue(p['reference_exclusion_bits'][0,4]&16)
        self.assertTrue(p['target_mask_coverage_complete'].all())

    def test_target_cyclone_coverage_edge_diagnostic(self):
        self.events[0]=self.event('forward',archive.utc('2025-12-31T00:00:00Z'),'forward')
        self.write_events();self.flush();self.run_stage();p=self.points()
        self.assertTrue(np.all(p['target_exclusion_bits']&16))
        self.assertFalse(p['target_mask_coverage_complete'].any())
        self.assertFalse(p['target_analysis_unconfounded'].any())

    def test_target_confound_mask_separate_from_valid_baseline(self):
        self.write_json('cyclone','AAA.json',dict(country='AAA',windows=[dict(country='AAA',sid='X',radius_km=300,half_width_hours=24,mode='conservative',start_utc_seconds=T,end_utc_seconds=T+600)]))
        self.flush();self.run_stage();p=self.points()
        self.assertTrue(p['analysis_available'][:3].all())
        np.testing.assert_array_equal(p['target_analysis_unconfounded'][:3],[False,False,True])


if __name__=='__main__': unittest.main()
