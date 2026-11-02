import datetime as dt
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
HAS_CFTIME = importlib.util.find_spec('cftime') is not None
if HAS_CFTIME:
    from audit_cmip6_content import decode_times, validate_year, validate_title


@unittest.skipUnless(HAS_CFTIME, 'Run CF time checks in the server qa_env with cftime installed')
class CFTimeTests(unittest.TestCase):
    def test_padded_and_unpadded_reference_dates_are_equivalent(self):
        a = decode_times([0, 1.5], 'days since 1850-1-1', 'proleptic_gregorian')
        b = decode_times([0, 1.5], 'days since 1850-01-01', 'proleptic_gregorian')
        self.assertEqual(list(a), list(b))
        self.assertEqual(a[1], dt.datetime(1850, 1, 2, 12))

    def test_leap_day_is_preserved(self):
        dates = decode_times([0, 1, 2], 'days since 2024-2-28', 'proleptic_gregorian')
        self.assertEqual([d.date() for d in dates], [dt.date(2024, 2, 28), dt.date(2024, 2, 29), dt.date(2024, 3, 1)])

    def test_invalid_origin_is_rejected(self):
        with self.assertRaises(ValueError):
            decode_times([0], 'days since 1850-13-1', 'proleptic_gregorian')

    def test_bcc_native_noleap_year_including_gregorian_leap_year(self):
        for year, offset in [(1991, 5840), (1992, 6205)]:
            first, last = validate_year([offset + .5 + i for i in range(365)],
                                        'days since 1975-01-01', '365_day', year)
            self.assertEqual((first.year, first.month, first.day), (year, 1, 1))
            self.assertEqual((last.year, last.month, last.day), (year, 12, 31))

    def test_missing_gregorian_leap_day_is_rejected(self):
        with self.assertRaises(AssertionError):
            validate_year(list(range(365)), 'days since 1992-01-01', 'standard', 1992)

    def test_extra_noleap_day_is_rejected(self):
        with self.assertRaises(AssertionError):
            validate_year(list(range(366)), 'days since 1992-01-01', '365_day', 1992)

    def test_360_day_calendar_keeps_december_30_endpoint(self):
        _, last = validate_year(list(range(360)), 'days since 1992-01-01', '360_day', 1992)
        self.assertEqual((last.month, last.day), (12, 30))

    def test_official_uppercase_canesm5_title(self):
        validate_title('CANESM5, r1i1p1f1, historical, global downscaled CMIP6 climate projection data',
                       dict(model='CanESM5', member='r1i1p1f1', experiment='historical'))

    def test_similar_model_wrong_member_and_wrong_scenario_are_rejected(self):
        task = dict(model='CanESM5', member='r1i1p1f1', experiment='ssp245')
        for title in ['CanESM5-other, r1i1p1f1, ssp245',
                      'CanESM5, r2i1p1f1, ssp245',
                      'CanESM5, r1i1p1f1, ssp585',
                      'CanESM5, r1i1p1f1, ssp245-other']:
            with self.subTest(title=title), self.assertRaises(AssertionError):
                validate_title(title, task)


if __name__ == '__main__':
    unittest.main()
