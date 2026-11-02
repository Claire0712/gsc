import importlib.util
from pathlib import Path
import unittest

import numpy as np


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/connection_baseline.py'
DAY = 86400
TARGET = int(np.datetime64('2024-01-01T00:00:00', 's').astype(np.int64))
OFFSETS = np.array([-28, -21, -14, -7, 0, 7, 14, 21, 28])


class ConnectionBaselineTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'connection baseline implementation missing')
        spec = importlib.util.spec_from_file_location('connection_baseline', SCRIPT)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.times = TARGET + OFFSETS * DAY
        self.values = np.array([10., 20., 30., 40., 99., 50., 60., 70., 80.])
        self.excluded = np.zeros(9, dtype=bool)
        self.annual = np.ones(9, dtype=bool)

    def run_baseline(self, **changes):
        args = dict(timestamps=self.times, values=self.values,
                    reference_excluded=self.excluded, annual_eligible=self.annual,
                    target_timestamps=np.array([TARGET], dtype=np.int64))
        args.update(changes)
        return self.m.retrospective_baseline(**args)

    def test_exact_eight_weekly_references_and_median(self):
        r = self.run_baseline()
        self.assertEqual(r['baseline'][0], 45.)
        self.assertEqual(r['reference_count'][0], 8)
        self.assertEqual(r['before_count'][0], 4)
        self.assertEqual(r['after_count'][0], 4)
        self.assertTrue(r['baseline_available'][0])

    def test_zero_references_count_and_positive_median(self):
        self.values[:] = [0, 0, 0, 0, 99, 10, 10, 10, 10]
        r = self.run_baseline()
        self.assertEqual(r['reference_count'][0], 8)
        self.assertEqual(r['baseline'][0], 5.)

    def test_zero_median_is_missing_not_zero_baseline(self):
        self.values[:] = 0
        r = self.run_baseline()
        self.assertEqual(r['reference_count'][0], 8)
        self.assertEqual(r['reference_median'][0], 0)
        self.assertFalse(r['baseline_available'][0])
        self.assertTrue(np.isnan(r['baseline'][0]))
        self.assertTrue(r['target_valid'][0])

    def test_negative_nan_infinity_and_invalid_mask_are_not_references(self):
        self.values[:3] = [-1, np.nan, np.inf]
        valid = np.ones(9, dtype=bool)
        valid[3] = False
        r = self.run_baseline(valid=valid)
        self.assertEqual(r['reference_count'][0], 4)
        self.assertEqual(r['before_count'][0], 0)
        self.assertFalse(r['baseline_available'][0])

    def test_four_with_both_sides_pass_three_fail(self):
        self.excluded[[0, 1, 2, 8]] = True
        r = self.run_baseline()
        self.assertEqual(r['reference_count'][0], 4)
        self.assertEqual(r['baseline'][0], 55.)
        self.excluded[7] = True
        self.assertFalse(self.run_baseline()['baseline_available'][0])

    def test_one_sided_four_fails(self):
        self.excluded[5:] = True
        self.assertFalse(self.run_baseline()['baseline_available'][0])

    def test_cross_year_gate_applies_to_reference_year_not_target_year(self):
        self.annual[:4] = False
        r = self.run_baseline()
        self.assertEqual(r['reference_count'][0], 4)
        self.assertFalse(r['baseline_available'][0])
        self.assertTrue(r['target_annual_eligible'][0])

    def test_target_missing_keeps_reference_diagnostics(self):
        self.values[4] = np.nan
        r = self.run_baseline()
        self.assertEqual(r['baseline'][0], 45.)
        self.assertTrue(r['target_present'][0])
        self.assertFalse(r['target_finite'][0])
        self.assertFalse(r['target_valid'][0])
        self.assertFalse(r['analysis_available'][0])

    def test_target_negative_finite_but_invalid(self):
        self.values[4] = -1
        r = self.run_baseline()
        self.assertTrue(r['target_finite'][0])
        self.assertFalse(r['target_valid'][0])

    def test_target_annual_gate_separate_from_baseline(self):
        self.annual[4] = False
        r = self.run_baseline()
        self.assertTrue(r['baseline_available'][0])
        self.assertTrue(r['target_valid'][0])
        self.assertFalse(r['analysis_available'][0])

    def test_exclusion_is_reference_only_target_heat_not_removed(self):
        self.excluded[4] = True
        self.assertTrue(self.run_baseline()['analysis_available'][0])

    def test_sparse_grid_does_not_fill_missing_reference_or_target(self):
        keep = np.arange(9) != 4
        r = self.run_baseline(timestamps=self.times[keep], values=self.values[keep],
                              reference_excluded=self.excluded[keep], annual_eligible=self.annual[keep])
        self.assertFalse(r['target_present'][0])
        self.assertEqual(r['baseline'][0], 45.)
        r = self.run_baseline(target_timestamps=np.array([TARGET + 600]))
        self.assertEqual(r['reference_count'][0], 0)
        self.assertTrue(np.isnan(r['baseline'][0]))

    def test_target_default_preserves_all_input_slots(self):
        r = self.run_baseline(target_timestamps=None)
        np.testing.assert_array_equal(r['target_timestamps'], self.times)
        self.assertEqual(len(r['baseline']), 9)

    def test_rejects_duplicate_unsorted_float_and_offphase_timestamps(self):
        for times in [np.repeat(TARGET, 9), self.times[::-1], self.times.astype(float), self.times + 1]:
            with self.subTest(times=times), self.assertRaises(ValueError):
                self.run_baseline(timestamps=times)

    def test_rejects_wrong_shapes_and_nonboolean_masks(self):
        for change in [dict(values=self.values[:, None]), dict(reference_excluded=np.zeros(9)),
                       dict(annual_eligible=np.ones(8, dtype=bool)), dict(valid=np.ones(9)),
                       dict(target_timestamps=np.array([TARGET, TARGET]))]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.run_baseline(**change)

    def test_empty_input_and_targets(self):
        r = self.run_baseline(timestamps=np.array([], dtype=np.int64), values=np.array([]),
                              reference_excluded=np.array([], dtype=bool), annual_eligible=np.array([], dtype=bool))
        self.assertFalse(r['baseline_available'][0])
        self.assertFalse(r['target_present'][0])
        r = self.run_baseline(target_timestamps=np.array([], dtype=np.int64))
        self.assertEqual(r['baseline'].size, 0)

    def test_median_of_large_finite_values_does_not_overflow(self):
        self.values[:] = np.finfo(float).max
        self.assertEqual(self.run_baseline()['baseline'][0], np.finfo(float).max)

    def test_past_only_is_separate_four_reference_sensitivity(self):
        r = self.m.past_only_28day_baseline(self.times, self.values,
                    reference_excluded=self.excluded, annual_eligible=self.annual,
                    target_timestamps=np.array([TARGET]))
        self.assertEqual(r['baseline'][0], 25.)
        self.assertEqual(r['reference_count'][0], 4)
        self.assertEqual(r['after_count'][0], 0)
        self.assertEqual(r['method'], 'past_only_28day_sensitivity')
        self.excluded[0] = True
        r = self.m.past_only_28day_baseline(self.times, self.values,
                    reference_excluded=self.excluded, annual_eligible=self.annual,
                    target_timestamps=np.array([TARGET]))
        self.assertFalse(r['baseline_available'][0])


if __name__ == '__main__':
    unittest.main()
