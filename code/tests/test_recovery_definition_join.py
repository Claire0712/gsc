import unittest

class DefinitionJoinTests(unittest.TestCase):
    def test_exact_identity_no_silent_fill_or_duplicate(self):
        from scripts.recovery_definition_join import combine
        row=dict(event_id='E',signal='bgp',country_id='AAA',source_point_file='p.npz',metrics={'old':1},dose=2)
        replacement=dict(row,metrics={'new':1})
        self.assertEqual(combine([row],[replacement])[0]['metrics'],{'new':1})
        self.assertEqual(combine([row],[replacement])[0]['dose'],2)
        for bad in ([],[replacement,replacement],[dict(replacement,country_id='BBB')],
                    [dict(replacement,source_point_file='other.npz')]):
            with self.assertRaises(ValueError):combine([row],bad)

if __name__=='__main__':unittest.main()
