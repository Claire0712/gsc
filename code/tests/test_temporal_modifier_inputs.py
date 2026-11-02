import unittest
from scripts.temporal_modifier_inputs import attach

class TemporalInputs(unittest.TestCase):
    def fixture(self):
        panel=[dict(event_id='e',country_id='X',signal='bgp')]
        audits=[dict(window_id='heat:e',signal='bgp',country_id='X',raw_pre_normalized_features_available='True',raw_pre_mad_over_median='0.2')]
        cat=[dict(event_id='e',country_id='X',start_date='2023-01-10',warm_season_start_month='12')]
        return panel,audits,cat
    def test_exact_join_and_known_first(self):
        got=attach(*self.fixture())[0]
        self.assertEqual(got['pre_connection_dispersion']['value'],.2)
        self.assertTrue(got['warm_season']['first_warm_season_event'])
    def test_unavailable_feature_is_missing_not_zero(self):
        p,a,c=self.fixture();a[0]['raw_pre_normalized_features_available']='False'
        self.assertIsNone(attach(p,a,c)[0]['pre_connection_dispersion']['value'])
    def test_wrong_country_rejected(self):
        p,a,c=self.fixture();a[0]['country_id']='Y'
        with self.assertRaises(ValueError):attach(p,a,c)
