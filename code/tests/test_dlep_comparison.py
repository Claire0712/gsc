import unittest
from scripts.dlep_comparison import compare

def row(e,c,x,y):return dict(event_id=e,country_id=c,dhrd_hours=x,dlep_proxy=y)

class ComparisonTests(unittest.TestCase):
    def test_inversion_and_ties_not_independent_tests(self):
        result=compare([row('a','A',1,10),row('b','B',2,5),row('c','B',2,5)])
        self.assertEqual(result['all']['inverted'],2)
        self.assertEqual(result['all']['tied'],1)
        self.assertEqual(result['cross_country']['inverted'],2)
        self.assertEqual(result['same_country']['tied'],1)

    def test_missing_and_zero(self):
        result=compare([row('a','A',0,0),row('b','A',1,5),row('c','B',None,None)])
        self.assertEqual(result['records'],2)
        self.assertEqual(result['all']['concordant'],1)
        self.assertIsNone(result['cross_country']['inverted_fraction_non_tied'])

if __name__=='__main__':unittest.main()
