import unittest
from scripts.modifier_models_v2 import support_columns

class SupportColumns(unittest.TestCase):
    def test_does_not_require_overlap_in_variable_defining_groups(self):
        self.assertEqual(support_columns('pre_connection_dispersion'),[0,1,2,3])
        self.assertEqual(support_columns('internet_share'),[0,1,2,3,4])
