import unittest
import numpy as np
import pandas as pd
from scripts.seven_year_reference import reference_inputs, target_events
from scripts.heat_catalogue_variants_core import attach_thresholds

class SevenYearTests(unittest.TestCase):
 def frame(self):
  dates=pd.date_range('2018-01-01','2025-12-31');x=np.array(dates.year-2018,dtype=float)
  return pd.DataFrame(dict(date=dates,tmax_c=x,tmin_c=x-5,country_id='X',dewpoint_c=0.))
 def test_excluded_target_cannot_change_threshold_or_season(self):
  f=self.frame();q,s=reference_inputs(f,2023);f.loc[f.date.dt.year==2023,['tmax_c','tmin_c']]=1e8
  q2,s2=reference_inputs(f,2023);pd.testing.assert_frame_equal(q,q2);self.assertEqual(s,s2)
  self.assertEqual(q.tmax_reference_years.min(),7);self.assertEqual(q.tmax_reference_n.min(),217)
  self.assertTrue((q.q90_tmax_c==7).all())
  f.loc[f.date.dt.year==2019,'tmax_c']=1e8;q3,_=reference_inputs(f,2023);self.assertTrue((q3.q90_tmax_c>1e6).all())
 def test_missing_year_is_unavailable_and_zero_is_valid(self):
  f=self.frame();f[['tmax_c','tmin_c']]=0.;q,s=reference_inputs(f,2022);self.assertTrue((q.q90_tmax_c==0).all());self.assertEqual(s['warm_season_start_month'],1)
  f.loc[f.date.dt.year==2018,'tmax_c']=np.nan;q,_=reference_inputs(f,2022)
  self.assertTrue(q.q90_tmax_c.isna().all());self.assertTrue((q.tmax_reference_years==6).all())
 def test_ninety_percent_pooled_boundary(self):
  f=self.frame();f[['tmax_c','tmin_c']]=0.
  missing=(f.date.dt.year==2018)&(((f.date.dt.month==1)&(f.date.dt.day<=16))|((f.date.dt.month==12)&f.date.dt.day.between(17,21)))
  self.assertEqual(int(missing.sum()),21);f.loc[missing,'tmax_c']=np.nan
  q,_=reference_inputs(f,2022);self.assertEqual(q.iloc[0].tmax_reference_n,196);self.assertEqual(q.iloc[0].q90_tmax_c,0.)
  f.loc[f.date==pd.Timestamp('2018-12-22'),'tmax_c']=np.nan;q,_=reference_inputs(f,2022)
  self.assertEqual(q.iloc[0].tmax_reference_n,195);self.assertTrue(np.isnan(q.iloc[0].q90_tmax_c))
 def test_leap_and_selection(self):
  f=self.frame();q,_=reference_inputs(f,2024);q.loc[q.calendar_day==58,'q90_tmax_c']=2;q.loc[q.calendar_day==59,'q90_tmax_c']=4
  d=attach_thresholds(f,q);self.assertEqual(d.loc[d.date==pd.Timestamp('2024-02-29'),'q90_tmax_c'].iloc[0],3)
  e=pd.DataFrame(dict(start_date=['2021-12-31','2022-01-01','2022-12-31','2023-01-01']))
  self.assertEqual(len(target_events(e,2022)),2)

class AuditManifestSchema(unittest.TestCase):
 def test_mapping_provenance_gets_verified_before_missing_table(self):
  import tempfile,json,hashlib
  from pathlib import Path
  from types import SimpleNamespace
  from scripts.audit_seven_year_reference_20261101 import audit
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);inp=p/'input.txt';inp.write_text('existing input')
   (p/'status.json').write_text('{"status":"completed"}')
   (p/'manifest.json').write_text(json.dumps(dict(inputs={str(inp):dict(sha256=hashlib.sha256(inp.read_bytes()).hexdigest())},outputs={})))
   with self.assertRaises(FileNotFoundError):audit(SimpleNamespace(output=p,daily=p/'unused'))

if __name__=='__main__':unittest.main()
