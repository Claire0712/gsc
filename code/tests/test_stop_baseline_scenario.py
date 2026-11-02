import copy
import importlib
import unittest


class StopScenarioTest(unittest.TestCase):
    def selector(self):
        return importlib.import_module('scripts.run_connection_baseline_stop_scenario').select_stop_window

    def test_exact_existing_window_without_mutation(self):
        record = {'windows': {'main': [100, 200], 'unknown_end_plusminus7': [0, 300],
                               'unknown_end_plusminus30': [-100, 400]}}
        before = copy.deepcopy(record)
        for key, value in record['windows'].items():
            self.assertEqual(self.selector()(record, key), tuple(value))
        self.assertEqual(record, before)

    def test_invalid_scenario_or_bounds_rejected(self):
        select = self.selector()
        with self.assertRaises(ValueError):
            select({'windows': {'other': [1, 2]}}, 'other')
        for windows in ({}, {'main': []}, {'main': [1, 1]}, {'main': [2, 1]},
                        {'main': [1.0, 2]}, {'main': [True, 2]}, {'main': [1, 2, 3]}):
            with self.subTest(windows=windows), self.assertRaises(ValueError):
                select({'windows': windows}, 'main')


if __name__ == '__main__':
    unittest.main()
