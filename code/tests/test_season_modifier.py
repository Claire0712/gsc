import unittest
from scripts.season_modifier import season_year, first_events

class SeasonModifier(unittest.TestCase):
    def test_cross_year_and_outside_season(self):
        self.assertEqual(season_year('2023-01-10',12),2022)
        self.assertEqual(season_year('2022-12-10',12),2022)
        self.assertIsNone(season_year('2023-03-01',12))
    def test_first_uses_weather_events_not_connection_selection(self):
        rows=[dict(country_id='X',event_id='a',start_date='2022-12-10',warm_season_start_month='12'),dict(country_id='X',event_id='b',start_date='2023-01-10',warm_season_start_month='12')]
        got=first_events(rows)
        self.assertEqual(got['a']['first_warm_season_event'],True)
        self.assertEqual(got['b']['first_warm_season_event'],False)
    def test_left_truncated_season_is_unknown(self):
        r=dict(country_id='X',event_id='a',start_date='2022-01-10',warm_season_start_month='12')
        self.assertIsNone(first_events([r])['a']['first_warm_season_event'])
