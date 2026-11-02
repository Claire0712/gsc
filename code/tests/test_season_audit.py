import unittest
from scripts.season_audit import choose

class SeasonAuditTests(unittest.TestCase):
    def test_cross_year_and_day_weight(self):
        rows=[(2018,m,10 if m in [12,1,2] else 0) for m in range(1,13)]
        self.assertEqual(choose(rows)[0],12)
    def test_ties_earliest_and_missing(self):
        self.assertEqual(choose([(2018,m,2) for m in range(1,13)])[0],1)
        self.assertIsNone(choose([(2018,1,float('nan'))])[0])
