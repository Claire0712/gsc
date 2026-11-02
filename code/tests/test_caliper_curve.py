import unittest
from scripts import run_caliper_curve as runner

class CaliperTest(unittest.TestCase):
    def test_frozen_files(self):
        for scale, name in [(0.5,'daily_0.5.csv'),(1,'daily_1.csv'),(2,'daily_2.csv')]:
            self.assertEqual(runner.daily_filename(scale),name)
    def test_reject_unplanned(self):
        for value in [0,0.75,3,float('nan')]:
            with self.assertRaises(ValueError): runner.daily_filename(value)

if __name__ == '__main__': unittest.main()
