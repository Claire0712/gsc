import unittest
from pathlib import Path
from datetime import datetime, timezone, date, timedelta

class DriverTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(Path('scripts/run_pre_weather.py').exists(), 'implementation missing')
        from scripts.run_pre_weather import prepare
        self.prepare=prepare
        self.window=dict(window_id='heat:x',parent_event_id='x',role='heat',country_id='TON',ioda_iso2='TO',start=str(int(datetime(2024,3,1,tzinfo=timezone.utc).timestamp())),end='1709424000',signal='bgp')
        self.weather=[dict(country_id='TON',date=(date(2024,2,23)+timedelta(days=i)).isoformat(),tmax_c=20+i,tmin_c=10+i,dewpoint_c=5+i) for i in range(7)]
    def test_deduplicated_signals(self):
        result=self.prepare([self.window,dict(self.window,signal='ping-slash24')],self.weather)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['tmax_mean_c'],23)
    def test_conflicting_identity(self):
        with self.assertRaises(ValueError):self.prepare([self.window,dict(self.window,country_id='FJI')],self.weather)
    def test_unknown_country(self):
        with self.assertRaises(ValueError):self.prepare([dict(self.window,country_id='FJI')],self.weather)
    def test_midnight(self):
        with self.assertRaises(ValueError):self.prepare([dict(self.window,start=str(int(self.window['start'])+1))],self.weather)
    def test_missing_date_retained(self):
        result=self.prepare([self.window],self.weather[:-1])
        self.assertIsNone(result[0]['tmax_mean_c'])
        self.assertFalse(result[0]['complete'])
    def test_duplicate_weather_rejected(self):
        with self.assertRaises(ValueError):self.prepare([self.window],self.weather+self.weather[:1])
