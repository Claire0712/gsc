import unittest
from scripts.modifier_inputs import prior

class PriorInputs(unittest.TestCase):
    def test_prior_one_to_three_years_not_current_or_future(self):
        rows=[dict(iso3='X',year=str(y),value=str(y)) for y in [2018,2019,2022,2023]]
        self.assertEqual(prior(rows,'X',2022,'value',False),dict(value=2019.,source_year=2019,lag_years=3,status='lagged_reference_year'))
        self.assertEqual(prior(rows,'Y',2022,'value',False)['status'],'missing_allowed_prior_years')

    def test_invalid_newest_does_not_block_older_valid(self):
        rows=[dict(iso3='X',year='2021',v='101'),dict(iso3='X',year='2020',v='50')]
        self.assertEqual(prior(rows,'X',2022,'v',True)['value'],.5)

    def test_duplicate_country_year_rejected(self):
        with self.assertRaises(ValueError):prior([dict(iso3='X',year='2021',v='1')]*2,'X',2022,'v',True)
