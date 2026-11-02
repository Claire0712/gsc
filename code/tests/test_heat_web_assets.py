import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/prepare_heat_web_assets.py'


class AssetTests(unittest.TestCase):
    def module(self):
        self.assertTrue(SCRIPT.exists(), 'Map exporter not implemented')
        spec = importlib.util.spec_from_file_location('assets', SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_exact_country_ids_and_property_allowlist(self):
        mod = self.module()
        raw = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties':
            {'shapeGroup': 'CHN', 'shapeName': 'China', 'secret': 'not-public'},
            'geometry': {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [0, 1], [0, 0]]]}}]}
        out = mod.sanitize_map(raw, {'CHN'})
        self.assertEqual(out['features'][0]['properties'], {'country_id': 'CHN', 'country_name': 'China'})

    def test_duplicate_or_unmatched_ids_fail(self):
        mod = self.module()
        feature = {'type': 'Feature', 'properties': {'shapeGroup': 'CHN', 'shapeName': 'China'}, 'geometry': {}}
        with self.assertRaises(ValueError):
            mod.sanitize_map({'features': [feature, feature]}, {'CHN'})
        with self.assertRaises(ValueError):
            mod.sanitize_map({'features': [feature]}, {'USA'})


if __name__ == '__main__':
    unittest.main()
