import unittest
from scripts.csv_finite import finite_number_text
class FiniteCSVTests(unittest.TestCase):
 def test_missing_nan_and_real_zero_are_distinct(self):
  for text in ('','nan','NaN','inf','-inf'):self.assertFalse(finite_number_text(text),text)
  for text in ('0','0.0','-2.5','3e-4'):self.assertTrue(finite_number_text(text),text)
 def test_unrecognized_missing_code_is_not_silently_accepted(self):
  with self.assertRaises(ValueError):finite_number_text('unknown')
if __name__=='__main__':unittest.main()
