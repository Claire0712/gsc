import importlib.util
import pathlib
import tempfile
import unittest

PATH = pathlib.Path(__file__).resolve().parents[1] / 'scripts/compare_precip_support.py'


class SupportTests(unittest.TestCase):
    def load(self):
        self.assertTrue(PATH.exists(), 'support comparison implementation is missing')
        spec = importlib.util.spec_from_file_location('support', PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_strict_uses_missing_population_not_rounded_ratio(self):
        m = self.load()
        rows = [dict(boundary_code='A', assigned_population=100, finite_support_population=100,
                     missing_support_population=1e-15, finite_support_fraction=1),
                dict(boundary_code='B', assigned_population=100, finite_support_population=99.999999999,
                     missing_support_population=0, finite_support_fraction=.99999999999)]
        cw = [dict(joint_status='exact_joint_match', joint_country_id=x, ioda_iso2=x) for x in ['A','B']]
        events = [dict(country_id=x, event_id=x, weather_candidate='True') for x in ['A','B']]
        result = m.compare(rows, cw, events)
        self.assertEqual(result['thresholds']['strict_complete']['boundary_codes'], ['B'])
        self.assertEqual(result['thresholds']['ge_99']['candidate_events_exact_joint'], 2)

    def test_zero_missing_and_exact_mapping(self):
        m = self.load()
        rows = [dict(boundary_code=x, assigned_population=a, finite_support_population=f,
                     missing_support_population=a-f, finite_support_fraction=f/a if a else None)
                for x,a,f in [('A',100,80),('B',100,0),('C',0,0),('D',100,95)]]
        cw = [dict(joint_status='exact_joint_match',joint_country_id='A',ioda_iso2='AA'),
              dict(joint_status='source_not_exact',joint_country_id='D',ioda_iso2='DD')]
        events = [dict(country_id=x,event_id=x,weather_candidate='True') for x in ['A','B','C','D']]
        result=m.compare(rows,cw,events)
        self.assertEqual(result['thresholds']['unrestricted_descriptive']['boundaries'], 2)
        self.assertEqual(result['thresholds']['ge_80']['candidate_events_exact_joint'], 1)
        self.assertEqual(result['thresholds']['ge_90']['exact_joint_entities'], 0)
        self.assertEqual(result['categories']['zero_population']['boundary_codes'], ['C'])
        self.assertEqual(result['categories']['no_support']['boundary_codes'], ['B'])
        with self.assertRaises(ValueError): m.compare(rows,cw+[cw[0]],events)
        with self.assertRaises(ValueError): m.compare(rows+rows[:1],cw,events)
        with self.assertRaises(ValueError): m.compare(rows,cw,events+events[:1])

    def test_population_nonconservation_and_no_overwrite(self):
        m=self.load()
        with self.assertRaises(ValueError):
            m.compare([dict(boundary_code='A',assigned_population=100,finite_support_population=90,
                            missing_support_population=20,finite_support_fraction=.9)],[],[])
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileExistsError): m.create_output(pathlib.Path(temp))


if __name__ == '__main__': unittest.main()
