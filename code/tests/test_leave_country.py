import unittest

class LeaveCountryTest(unittest.TestCase):
    def test_each_country_removed_once_and_rows_not_modified(self):
        from scripts.leave_country import samples
        rows=[{'country_id':'AAA','x':1},{'country_id':'BBB','x':2},{'country_id':'AAA','x':3}]
        self.assertEqual(list(samples(rows)),[('AAA',[rows[1]]),('BBB',[rows[0],rows[2]])])
        self.assertEqual(len(rows),3)
        with self.assertRaises(ValueError):list(samples([{'country_id':''}]))

if __name__=='__main__':unittest.main()
