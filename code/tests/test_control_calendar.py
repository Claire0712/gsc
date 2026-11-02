import csv
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1]/'scripts/build_control_calendar.py'
DAY = 86400


def stamp(day):
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())


def event(start='2024-06-01', end='2024-06-03', **changes):
    row = dict(event_id='AAA_test', country_id='AAA', ioda_iso2='AA',
               start_date=start, end_exclusive_utc=end+'T00:00:00Z', route='forward',
               weather_candidate='True', review_only='1')
    row.update(changes)
    return row


class ControlCalendarTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'control calendar implementation missing')
        spec = importlib.util.spec_from_file_location('control_calendar', SCRIPT)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def at(self, offset=7, windows=(), row=None):
        return next(r for r in self.m.calendar_rows(row or event(), windows) if r['offset_days']==offset)

    def test_twelve_offsets_no_zero_preserve_same_weekday_and_span(self):
        rows = self.m.calendar_rows(event(), [])
        self.assertEqual([r['offset_days'] for r in rows], [-42,-35,-28,-21,-14,-7,7,14,21,28,35,42])
        for r in rows:
            self.assertEqual(stamp(r['control_end_exclusive_utc'][:-1])-stamp(r['control_start_utc'][:-1]), 2*DAY)
            self.assertEqual(datetime.fromisoformat(r['control_start_utc']).weekday(), 5)
            self.assertTrue(r['integral_calendar_candidate'])
            self.assertTrue(r['matching_calendar_candidate'])
            self.assertTrue(r['curve_calendar_candidate'])
            self.assertFalse(r['final_sample_eligible'])

    def test_rightopen_adjacency_not_overlap_but_600_second_overlap_is(self):
        end = stamp('2024-06-13')
        window = dict(event_id='OTHER', start=end, end=end+DAY)
        self.assertTrue(self.at(windows=[window])['integral_calendar_candidate'])
        window['start'] -= 600
        r = self.at(windows=[window])
        self.assertFalse(r['integral_calendar_candidate'])
        self.assertIn('integral_heat_overlap', json.loads(r['integral_rejection_reasons']))

    def test_preperiod_overlap_preserves_integral_but_rejects_matching(self):
        r = self.at(windows=[dict(event_id='PRE', start=stamp('2024-06-02'), end=stamp('2024-06-03'))])
        self.assertTrue(r['integral_calendar_candidate'])
        self.assertFalse(r['matching_calendar_candidate'])
        self.assertFalse(r['curve_calendar_candidate'])

    def test_short_event_curve_tail_overlap_separate(self):
        r = self.at(windows=[dict(event_id='TAIL', start=stamp('2024-06-14'), end=stamp('2024-06-15'))])
        self.assertTrue(r['integral_calendar_candidate'])
        self.assertTrue(r['matching_calendar_candidate'])
        self.assertFalse(r['curve_calendar_candidate'])

    def test_cross_start_year_rejected_but_all_twelve_retained(self):
        rows = self.m.calendar_rows(event('2024-01-03','2024-01-05'), [])
        self.assertEqual(len(rows), 12)
        r = next(x for x in rows if x['offset_days']==-7)
        self.assertFalse(r['same_start_year'])
        self.assertIn('different_start_year', json.loads(r['integral_rejection_reasons']))

    def test_cross_year_end_allowed_inside_calendar(self):
        r = self.at(row=event('2024-12-20','2025-01-02'))
        self.assertTrue(r['same_start_year'])
        self.assertTrue(r['matching_calendar_candidate'])

    def test_data_boundary_no_clipping_and_preperiod_separate(self):
        r = self.at(offset=-7,row=event('2022-01-08','2022-01-10'))
        self.assertTrue(r['integral_calendar_candidate'])
        self.assertFalse(r['preperiod_calendar_covered'])
        self.assertFalse(r['matching_calendar_candidate'])
        self.assertEqual(r['preperiod_start_utc'],'2021-12-25T00:00:00Z')
        r = self.at(row=event('2025-12-20','2025-12-31'))
        self.assertFalse(r['integral_calendar_covered'])
        self.assertEqual(r['integral_end_exclusive_utc'],'2026-01-10T00:00:00Z')

    def test_leap_day_exact_length(self):
        r = self.at(row=event('2024-02-22','2024-02-25'))
        self.assertEqual(r['control_start_utc'],'2024-02-29T00:00:00Z')
        self.assertEqual(r['control_end_exclusive_utc'],'2024-03-03T00:00:00Z')

    def test_long_integral_tail_overlap_rejects_curve_use_even_if_curve_window_clear(self):
        r = self.at(row=event('2024-06-01','2024-07-01'),windows=[dict(event_id='TAIL',start=stamp('2024-07-05'),end=stamp('2024-07-06'))])
        self.assertFalse(r['curve_heat_overlap'])
        self.assertFalse(r['integral_calendar_candidate'])
        self.assertFalse(r['curve_calendar_candidate'])

    def test_zero_candidates_retains_rejections(self):
        rows=self.m.calendar_rows(event(),[dict(event_id='ALL',start=stamp('2024-01-01'),end=stamp('2025-01-01'))])
        self.assertEqual(len(rows),12)
        self.assertFalse(any(r['integral_calendar_candidate'] for r in rows))

    def test_invalid_core_and_nonmidnight_boundary_rejected(self):
        with self.assertRaises(ValueError):self.m.calendar_rows(event(end='2024-06-01'),[])
        with self.assertRaises(ValueError):self.m.calendar_rows(event(end='2024-06-03T01:00:00'),[])


class ControlCalendarDriverTests(unittest.TestCase):
    at = ControlCalendarTests.at

    def setUp(self):
        ControlCalendarTests.setUp(self)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.candidate=self.root/'candidate';self.heat=self.root/'heat'
        self.candidate.mkdir();self.heat.mkdir()
        self.manifests={self.candidate:{'status':'completed','outputs':{}},self.heat:{'state':'complete','outputs':{}}}
        (self.candidate/'status.json').write_text(json.dumps({'status':'completed'}))
        self.events=[event(),event('2024-08-01','2024-08-03',event_id='AAA_held',route='held_stop_review'),event('2024-11-01','2024-11-03',event_id='AAA_cold',route='not_weather_candidate',weather_candidate='False')]
        for name,rs in [('event_routing.csv',self.events),('forward_candidates.csv',self.events[:1]),('held_stop_review.csv',self.events[1:2])]:self.csv(self.candidate,name,rs)
        self.csv(self.heat,'analysis_events.csv',self.events)
        self.daily=[]
        for row in self.events:
            s=stamp(row['start_date'])
            for i in range(2):self.daily.append(dict(country_id='AAA',date=datetime.fromtimestamp(s+i*DAY,timezone.utc).date().isoformat(),analysis_event_id=row['event_id'],tmax_hot='False' if i else 'True'))
        self.daily.append(dict(country_id='AAA',date='2021-12-31',analysis_event_id='AAA_context',tmax_hot='True'))
        self.write_daily();self.flush()

    def csv(self,folder,name,rs):
        stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=list(rs[0]));writer.writeheader();writer.writerows(rs)
        (folder/name).write_text(stream.getvalue());self.register(folder,name)

    def register(self,folder,name):
        data=(folder/name).read_bytes();self.manifests[folder]['outputs'][name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}

    def write_daily(self):
        stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=list(self.daily[0]));writer.writeheader();writer.writerows(self.daily)
        (self.heat/'daily_heat_flags.csv.gz').write_bytes(gzip.compress(stream.getvalue().encode()));self.register(self.heat,'daily_heat_flags.csv.gz')

    def flush(self):
        for folder,manifest in self.manifests.items():(folder/'manifest.json').write_text(json.dumps(manifest))

    def run_stage(self):return self.m.run(self.candidate,self.heat,self.root/'output')

    def test_driver_counts_manifest_preserves_held_and_bridge_labels(self):
        r=self.run_stage()
        self.assertEqual(r['candidate_rows'],12)
        self.assertEqual(r['route_counts']['held_stop_review'],1)
        self.assertEqual(r['all_year_heat_processes_including_context'],4)
        self.assertFalse(r['final_sample_eligible'])
        self.assertEqual((self.root/'output/held_stop_review.csv').read_bytes(),(self.candidate/'held_stop_review.csv').read_bytes())
        manifest=json.loads((self.root/'output/manifest.json').read_text())
        for name,entry in manifest['outputs'].items():
            self.assertEqual(hashlib.sha256((self.root/'output'/name).read_bytes()).hexdigest(),entry['sha256'])
        with self.assertRaises(FileExistsError):self.run_stage()

    def test_hash_mismatch_fails(self):
        with (self.heat/'daily_heat_flags.csv.gz').open('ab') as f:f.write(b'corrupt')
        with self.assertRaisesRegex(ValueError,'hash'):self.run_stage()

    def test_incomplete_status_fails(self):
        (self.candidate/'status.json').write_text(json.dumps({'status':'running'}))
        with self.assertRaisesRegex(ValueError,'completed'):self.run_stage()

    def test_releasing_held_forward_fails(self):
        self.csv(self.candidate,'forward_candidates.csv',self.events[:2]);self.flush()
        with self.assertRaisesRegex(ValueError,'routing'):self.run_stage()

    def test_daily_omission_fails(self):
        self.daily=self.daily[1:];self.write_daily();self.flush()
        with self.assertRaisesRegex(ValueError,'catalogue'):self.run_stage()

    def test_2021_recovery_in_2022(self):
        windows=self.m.heat_windows(self.daily,self.events)
        r=self.at(offset=-7,row=event('2022-01-08','2022-01-10'),windows=windows['AAA'])
        self.assertTrue(r['integral_heat_overlap'])
        self.assertIn('AAA_context',json.loads(r['integral_heat_event_ids']))


if __name__=='__main__':unittest.main()
