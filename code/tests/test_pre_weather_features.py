import unittest
from datetime import date,timedelta
from pathlib import Path

class PreWeatherTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(Path('scripts/pre_weather_features.py').exists(), 'implementation missing')
        from scripts.pre_weather_features import pre_weather_features
        self.compute=pre_weather_features
        self.rows=[dict(country_id='TON',date=(date(2024,2,23)+timedelta(days=i)).isoformat(),
                        tmax_c=20+i,tmin_c=10+i,dewpoint_c=5+i) for i in range(7)]

    def test_only_seven_prior_days(self):
        rows=self.rows+[dict(country_id='TON',date='2024-03-01',tmax_c=999,tmin_c=999,dewpoint_c=999)]
        r=self.compute(rows,'TON','2024-03-01')
        self.assertEqual(r['tmax_mean_c'],23)
        self.assertEqual(r['tmin_mean_c'],13)
        self.assertEqual(r['dewpoint_mean_c'],8)
        self.assertTrue(r['complete'])

    def test_missing_not_filled(self):
        r=self.compute(self.rows[:-1],'TON','2024-03-01')
        self.assertIsNone(r['tmax_mean_c'])
        self.assertEqual(r['dates_present'],6)
        self.assertFalse(r['complete'])

    def test_nonfinite_per_variable(self):
        self.rows[0]['dewpoint_c']=float('nan')
        r=self.compute(self.rows,'TON','2024-03-01')
        self.assertIsNone(r['dewpoint_mean_c'])
        self.assertEqual(r['tmax_mean_c'],23)
        self.assertFalse(r['complete'])

    def test_duplicates_rejected_and_other_country_ignored(self):
        with self.assertRaises(ValueError):self.compute(self.rows+self.rows[:1],'TON','2024-03-01')
        extra=dict(self.rows[0],country_id='FJI',tmax_c=999)
        self.assertEqual(self.compute(self.rows+[extra],'TON','2024-03-01')['tmax_mean_c'],23)

    def test_zero_negative_temperatures_are_valid(self):
        for r in self.rows:r['tmax_c']=0;r['tmin_c']=-5
        r=self.compute(self.rows,'TON','2024-03-01')
        self.assertEqual(r['tmax_mean_c'],0)
        self.assertEqual(r['tmin_mean_c'],-5)

if __name__=='__main__':unittest.main()
