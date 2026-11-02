import unittest

class SelectionTest(unittest.TestCase):
    def test_explicit_signal_and_complete_matched_only(self):
        from scripts.country_sensitivity import select_rows
        a=dict(signal='bgp',matched_integral=True,metrics={'full_window_complete':True},full_observed_unconfounded=True)
        b=dict(a,signal='ping-slash24');c=dict(a,matched_integral=False)
        self.assertEqual(select_rows([a,b,c],'bgp'),[a])
        with self.assertRaises(ValueError):select_rows([a],'unknown')
        with self.assertRaises(ValueError):select_rows([dict(a,full_observed_unconfounded=False)],'bgp')
        with self.assertRaises(ValueError):select_rows([a],'merit-nt')

if __name__=='__main__':unittest.main()
