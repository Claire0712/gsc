import unittest
import pandas as pd
from scripts.heat_catalogue_variants_core import catalogue_country,warm_season

class VariantTests(unittest.TestCase):
    def test_minimum_run_does_not_redefine_hot(self):
        d=pd.date_range('2022-06-01',periods=30)
        f=pd.DataFrame(dict(date=d,country_id='X',tmax_c=[0]*10+[2]*3+[0]*17,tmin_c=0,dewpoint_c=0,q90_tmax_c=1,q90_tmin_c=1))
        self.assertEqual(len(catalogue_country(f,6,min_run=3)[0]),1)
        self.assertEqual(len(catalogue_country(f,6,min_run=6)[0]),0)
        self.assertEqual(len(catalogue_country(f,1,season_months=12)[0]),1)
    def test_six_month_reference_choice(self):
        d=pd.date_range('2018-01-01','2021-12-31')
        f=pd.DataFrame(dict(date=d,tmax_c=[10 if x.month in [10,11,12,1,2,3] else 0 for x in d]))
        self.assertEqual(warm_season(f,months_count=6)['warm_season_start_month'],10)
