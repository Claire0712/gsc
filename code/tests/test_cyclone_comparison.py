import unittest

class CycloneComparisonTest(unittest.TestCase):
    def test_requires_identical_explicit_baseline_parameters(self):
        from scripts.run_cyclone_comparison import validate_scenario
        s={'cyclone_radius_km':500,'cyclone_half_width_hours':72,
           'cyclone_complete_bounds':[1515024000,1766966400]}
        validate_scenario(s,500,72)
        for changed in ({},dict(s,cyclone_radius_km=100),
                        dict(s,cyclone_half_width_hours=24),
                        dict(s,cyclone_complete_bounds=[0,1])):
            with self.assertRaises(ValueError):validate_scenario(changed,500,72)

if __name__=='__main__':unittest.main()
