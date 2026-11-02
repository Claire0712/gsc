import unittest
from scripts.dlep import internet, build

class DlepTests(unittest.TestCase):
    def test_current_then_recent_past_no_future(self):
        rows=[dict(iso3='AAA',year=str(y),**{'IT.NET.USER.ZS':v}) for y,v in [(2020,'50'),(2022,''),(2023,'80')]]
        self.assertEqual(internet(rows,'AAA',2022)['source_year'],2020)
        self.assertEqual(internet(rows,'AAA',2023)['value'],.8)
        self.assertIsNone(internet(rows,'AAA',2027)['value'])

    def test_zero_is_valid_but_missing_is_not_zero(self):
        rows=[dict(iso3='AAA',year='2022',**{'IT.NET.USER.ZS':'0'})]
        self.assertEqual(internet(rows,'AAA',2022)['value'],0)
        self.assertIsNone(internet(rows,'BBB',2022)['value'])

    def test_duplicate_country_year_rejected(self):
        r=dict(iso3='AAA',year='2022',**{'IT.NET.USER.ZS':'40'})
        with self.assertRaises(ValueError):internet([r,r],'AAA',2022)

    def test_formula_and_clean_qualification(self):
        event=dict(event_id='e',country_id='AAA',signal='ping-slash24',year_month='2022-01',
                   matched_integral=False,full_observed_unconfounded=True,metrics={'dhrd_hours':2})
        social=[dict(iso3='AAA',year='2022',**{'IT.NET.USER.ZS':'25'})]
        a=build([event],{'AAA':100},social)[0]
        self.assertEqual(a['dlep_proxy'],50)
        self.assertEqual(a['internet']['lag_years'],0)
        event['full_observed_unconfounded']=False
        self.assertIsNone(build([event],{'AAA':100},social)[0]['dlep_proxy'])
        event['full_observed_unconfounded']=True
        self.assertIsNone(build([event],{},social)[0]['dlep_proxy'])

if __name__=='__main__':unittest.main()
