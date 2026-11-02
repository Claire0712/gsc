import unittest
import numpy as np
import pandas as pd
from scripts.loyo_catalogue_inputs import loyo_inputs


class LoyoInputsTest(unittest.TestCase):
    def fixture(self):
        dates = pd.date_range('2018-01-01', '2021-12-31')
        frame = pd.DataFrame({'date': dates, 'tmax_c': np.where(dates.month <= 3, 20., 0.)})
        # One reference year reverses the warm season, and must be omitted.
        frame.loc[dates.year == 2018, 'tmax_c'] = np.where(dates[dates.year == 2018].month >= 7, 200., 0.)
        q = pd.DataFrame({'calendar_day': range(365), 'q90_tmax_omit_2018_c': 12., 'q90_tmin_omit_2018_c': 4.})
        return q, frame

    def test_omission_changes_season_and_uses_exact_threshold_columns(self):
        q, frame = self.fixture(); before = frame.copy(deep=True)
        thresholds, season = loyo_inputs(q, frame, 2018)
        self.assertEqual(season['warm_season_start_month'], 1)
        self.assertTrue((thresholds.q90_tmax_c == 12.).all())
        self.assertTrue((thresholds.q90_tmin_c == 4.).all())
        pd.testing.assert_frame_equal(frame, before)

    def test_invalid_omit_duplicate_missing_and_nonfinite_rejected(self):
        q, frame = self.fixture()
        for bad, year in [(q, 2022), (pd.concat([q, q.iloc[:1]]), 2018), (q.iloc[:-1], 2018)]:
            with self.assertRaises(ValueError): loyo_inputs(bad, frame, year)
        q.loc[0, 'q90_tmax_omit_2018_c'] = np.nan
        with self.assertRaises(ValueError): loyo_inputs(q, frame, 2018)
