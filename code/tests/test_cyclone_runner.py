import unittest
import tempfile
import csv
import json
from pathlib import Path
from unittest.mock import patch
from scripts import run_cyclone_screen as runner
from shapely.geometry import box


def row(sid='A', utc='2022-01-01T00:00:00Z', lon='0', lat='0', conflict='0'):
    return dict(normalized_sid=sid, normalized_time_utc=utc, normalized_longitude=lon,
                normalized_latitude=lat, conflicting_sid_time=conflict, source_row='1')


class RunnerTests(unittest.TestCase):
    def test_clean_deduplicate_exclude_all_conflicts_keep_missing_wind(self):
        points, audit = runner.clean_tracks([row(), row(), row('B', lon='1'),
                                             row('B', lon='2'), row('C', conflict='1'),
                                             row('D', lat='nan'), row('E', utc='bad')])
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]['sid'], 'A')
        self.assertEqual(audit['duplicate_rows_removed'], 1)
        self.assertEqual(audit['conflict_rows_excluded'], 3)
        self.assertEqual(audit['invalid_rows_excluded'], 2)

    def test_flags_and_windows_country_sid_separate_unknown(self):
        points, _ = runner.clean_tracks([row(), row('B', lon='100')])
        result = runner.screen_country('TST', box(-1, -1, 1, 1), points)
        self.assertEqual(result['counts']['100']['hit'], 1)
        self.assertEqual(result['counts']['100']['false'], 1)
        self.assertEqual(len(result['points']), 1)
        windows = result['windows']
        self.assertEqual(len(windows), 12)
        self.assertEqual(windows[0]['end_utc_seconds']-windows[0]['start_utc_seconds'], 172800)
        self.assertEqual({w['sid'] for w in windows}, {'A'})

    def test_invalid_utc_offset_and_out_of_range_rejected(self):
        points, audit = runner.clean_tracks([row(utc='2022-01-01T00:00:00'), row(lon='181')])
        self.assertEqual(points, [])
        self.assertEqual(audit['invalid_rows_excluded'], 2)

    def test_unresolved_distance_is_kept_separate_from_known_hits(self):
        points, _ = runner.clean_tracks([row()])
        # Inject the documented distance-core boundary result to exercise policy,
        # without relying on platform rounding to manufacture a 1 m edge case.
        with patch.object(runner.BoundaryIndex, 'classify', return_value=dict(
                within=[False, None, True], lower_m=299999.8, upper_m=300000.2, iterations=12)):
            result = runner.screen_country('TST', box(-1,-1,1,1), points)
        self.assertEqual(result['counts']['300'], dict(hit=0, unknown=1, false=0))
        windows300 = [w for w in result['windows'] if w['radius_km']==300]
        self.assertEqual(len(windows300), 2)
        self.assertEqual({w['mode'] for w in windows300}, {'conservative'})
        self.assertEqual(len([w for w in result['windows'] if w['radius_km']==500]), 4)

    def test_end_to_end_provenance_fresh_directory_and_reject_corruption(self):
        import geopandas as gpd
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            aux = root/'analysis/2026-10-07_parallel_prep/auxiliary'
            aux.mkdir(parents=True)
            boundary = root/'data/boundaries/geoBoundariesCGAZ_ADM0.gpkg'
            boundary.parent.mkdir(parents=True)
            gpd.GeoDataFrame({'shapeGroup':['TST']}, geometry=[box(-1,-1,1,1)], crs=4326).to_file(boundary)
            track = aux/'ibtracs_cleaned.csv'
            with track.open('w') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(row()))
                writer.writeheader(); writer.writerow(row())
            (aux/'manifest.json').write_text(json.dumps(dict(state='complete', outputs={track.name:runner.fingerprint(track)})))
            meta = root/'data/metadata'
            meta.mkdir()
            (meta/'ancillary_file_checksums.json').write_text(json.dumps(dict(files=[dict(file='boundaries/'+boundary.name, **runner.fingerprint(boundary))])))
            out = root/'out'
            runner.run(root, out)
            self.assertEqual(json.loads((out/'status.json').read_text())['state'], 'completed')
            for entry in json.loads((out/'manifest.json').read_text())['outputs']:
                self.assertEqual(runner.fingerprint(entry['path']), entry)
            with self.assertRaises(FileExistsError):
                runner.run(root, out)
            with track.open('a') as stream:
                stream.write('\n')
            with self.assertRaisesRegex(ValueError, 'Provenance mismatch'):
                runner.run(root, root/'bad')
            self.assertEqual(json.loads((root/'bad/status.json').read_text())['state'], 'failed')


if __name__ == '__main__':
    unittest.main()
