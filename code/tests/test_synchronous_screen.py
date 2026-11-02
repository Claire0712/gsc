import unittest
import numpy as np
from scripts.synchronous_screen import paired_counts, candidate_flags, align_previous_day, annual_mask


class SynchronousScreenTests(unittest.TestCase):
    def test_annual_mask_exact_integer_gate_and_universe(self):
        times = np.array(['2022-12-31', '2023-01-01'], dtype='datetime64[s]').astype('int64')
        coverage = {('AA', 2022): (4, 5), ('AA', 2023): (3, 5),
                    ('BB', 2022): (5, 5), ('BB', 2023): (5, 5)}
        result = annual_mask(times, ['AA', 'BB'], coverage, {'AA'})
        np.testing.assert_equal(result, [[True, False], [False, False]])

    def test_annual_missing_key_fails_closed(self):
        times = np.array(['2022-01-01'], dtype='datetime64[s]').astype('int64')
        with self.assertRaises(ValueError):
            annual_mask(times, ['AA'], {}, {'AA'})

    def test_annual_duplicate_and_invalid_counts_rejected(self):
        times = np.array(['2022-01-01'], dtype='datetime64[s]').astype('int64')
        for counts in [(6, 5), (-1, 5), (0, 0), (4.0, 5), (True, 5)]:
            with self.assertRaises(ValueError):
                annual_mask(times, ['AA'], {('AA', 2022): counts}, {'AA'})
        with self.assertRaises(ValueError):
            annual_mask(times, ['AA', 'AA'], {('AA', 2022): (5, 5)}, {'AA'})
        with self.assertRaises(ValueError):
            annual_mask(times, ['AA'], {('AA', 2022): (5, 5)}, {'ZZ'})

    def test_alignment_across_year_and_missing_slot(self):
        times = np.array(['2022-12-31T00:00', '2022-12-31T00:10',
                          '2023-01-01T00:00', '2023-01-01T00:20'], dtype='datetime64[s]')
        values = np.array([[10., 20.], [30., 40.], [1., 2.], [3., 4.]])
        eligibility = np.ones_like(values, dtype=bool)
        eligibility[0, 1] = False
        previous, paired, found = align_previous_day(times.astype('int64'), values, eligibility)
        np.testing.assert_equal(previous[2], [10., 20.])
        self.assertTrue(np.isnan(previous[3]).all())
        np.testing.assert_equal(paired[2], [True, False])
        self.assertFalse(paired[3].any())
        np.testing.assert_equal(found, [False, False, True, False])

    def test_alignment_across_quarter(self):
        times = np.array(['2024-03-31T23:50', '2024-04-01T23:50'], dtype='datetime64[s]').astype('int64')
        previous, paired, found = align_previous_day(times, np.array([[8.], [0.]]), np.ones((2, 1), dtype=bool))
        self.assertEqual(previous[1, 0], 8.)
        self.assertTrue(paired[1, 0])

    def test_alignment_rejects_duplicates_and_non_grid(self):
        for times in [np.array([87000, 87000]), np.array([87600, 87000]), np.array([87000, 87601])]:
            with self.assertRaises(ValueError):
                align_previous_day(times, np.ones((2, 1)), np.ones((2, 1), dtype=bool))

    def test_zero_missing_and_strict_drop(self):
        previous = np.array([[10., 0., np.nan, 10., 10.]])
        current = np.array([[0., 2., 1., 8., 7.]])
        result = paired_counts(current, previous, np.ones_like(current, dtype=bool))
        self.assertEqual(result['denominator'].tolist(), [3])
        self.assertEqual(result['numerator'].tolist(), [2])
        self.assertEqual(result['previous_zero'].tolist(), [1])
        self.assertEqual(result['missing_pair'].tolist(), [1])
        self.assertAlmostEqual(result['fraction'][0], 2/3)

    def test_eligibility_and_empty_denominator(self):
        result = paired_counts(np.array([[0., 0.]]), np.array([[10., 0.]]), np.array([[False, True]]))
        self.assertEqual(result['annual_ineligible'].tolist(), [1])
        self.assertEqual(result['denominator'].tolist(), [0])
        self.assertTrue(np.isnan(result['fraction'][0]))

    def test_strict_quantile(self):
        threshold, flags = candidate_flags(np.array([0., .5, 1., np.nan]))
        self.assertAlmostEqual(threshold, .999)
        self.assertEqual(flags.tolist(), [False, False, True, False])
        threshold, flags = candidate_flags(np.array([.5, .5]))
        self.assertEqual(flags.tolist(), [False, False])

    def test_no_valid_ratios(self):
        threshold, flags = candidate_flags(np.array([np.nan]))
        self.assertTrue(np.isnan(threshold))
        self.assertFalse(flags.any())

    def test_invalid_shapes_and_negative_values(self):
        with self.assertRaises(ValueError):
            paired_counts(np.ones((1, 2)), np.ones((2, 1)), np.ones((1, 2), dtype=bool))
        with self.assertRaises(ValueError):
            paired_counts(np.array([[-1.]]), np.ones((1, 1)), np.ones((1, 1), dtype=bool))


if __name__ == '__main__':
    unittest.main()
