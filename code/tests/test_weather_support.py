import unittest
from scripts.weather_support import group_complete

class WeatherSupport(unittest.TestCase):
    def test_missing_control_day_excludes_entire_group(self):
        rows=[dict(country_id='X',date='2024-01-01'),dict(country_id='X',date='2024-01-02')]
        lookup={('X','2024-01-01'):dict(u10_m_s=0,v10_m_s=0,u10_m_s_population_fraction=1,v10_m_s_population_fraction=1)}
        self.assertFalse(group_complete(rows,lookup,('u10_m_s','v10_m_s'),0))
    def test_real_zero_valid_fraction_cutoff_is_separate(self):
        lookup={('X','2024-01-01'):dict(u10_m_s=0,v10_m_s=0,u10_m_s_population_fraction=.9,v10_m_s_population_fraction=.9)}
        rows=[dict(country_id='X',date='2024-01-01')]
        self.assertTrue(group_complete(rows,lookup,('u10_m_s','v10_m_s'),0))
        self.assertFalse(group_complete(rows,lookup,('u10_m_s','v10_m_s'),.95))
