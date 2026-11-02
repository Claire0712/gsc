import unittest
from pathlib import Path

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(Path('scripts/stop_window_review.py').exists(),'implementation missing')
        from scripts.stop_window_review import review
        self.review=review
        self.w=dict(window_id='heat:e',country_id='TON',start=20*86400,end=22*86400)
        self.r=dict(source_row='1',country_id='TON',end_unknown=True,scope_uncertain=True,windows={k:[23*86400-d*86400,24*86400+d*86400] for k,d in [('main',0),('unknown_end_plusminus7',7),('unknown_end_plusminus30',30)]},reasons=[])
    def test_main_and_sensitivity(self):
        r=self.review([self.w],[self.r])[0]
        self.assertEqual(r['overlaps']['integral']['main'],['1'])
        self.assertEqual(r['overlaps']['preperiod']['main'],[])
        self.assertEqual(r['overlaps']['preperiod']['unknown_end_plusminus7'],['1'])
    def test_right_open(self):
        self.r['windows']={k:[25*86400,26*86400] for k in self.r['windows']}
        self.assertEqual(self.review([self.w],[self.r])[0]['overlaps']['integral']['main'],[])
    def test_unlocated_not_excluded(self):
        self.r['windows']={};self.r['reasons']=['missing_start']
        r=self.review([self.w],[self.r])[0]
        self.assertEqual(r['unlocated_country_records'],['1'])
        self.assertEqual(r['overlaps']['integral']['main'],[])
    def test_other_country(self):
        self.r['country_id']='FJI'
        self.assertEqual(self.review([self.w],[self.r])[0]['overlaps']['integral']['main'],[])
    def test_duplicate_record(self):
        with self.assertRaises(ValueError):self.review([self.w],[self.r,self.r])
    def test_duplicate_window(self):
        with self.assertRaises(ValueError):self.review([self.w,self.w],[self.r])
