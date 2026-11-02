import unittest
import numpy as np
from scripts import run_connection_baseline as original


class CycloneSensitivityTests(unittest.TestCase):
    def test_runner_primary_parity(self):
        import importlib
        from tests.test_connection_baseline_runner import BaselineRunnerTests
        f=BaselineRunnerTests();f.setUp();self.addCleanup(f.doCleanups)
        f.m=importlib.import_module('scripts.run_cyclone_sensitivity_baseline')
        report=f.run_stage(cyclone_radius=300,cyclone_hours=24)
        points=f.points()
        self.assertEqual(points['reference_exclusion_bits'][0].tolist(),[0,0,12,2,1,0,0,0])
        self.assertEqual(report['cyclone_radius_km'],300)
        self.assertEqual(report['cyclone_half_width_hours'],24)

    def test_selection_and_calendar(self):
        from scripts.cyclone_baseline_sensitivity import select_windows, coverage_bounds
        rows = [dict(country='MYS', radius_km=r, half_width_hours=h,
                     mode=m, start_utc_seconds=10, end_utc_seconds=20)
                for r in (100,300,500) for h in (24,72)
                for m in ('conservative','known')]
        self.assertEqual(select_windows(rows,'MYS',100,72), ([(10,20)],[(10,20)]))
        self.assertEqual(coverage_bounds(24), (original.CYCLONE_COMPLETE_START,original.CYCLONE_COMPLETE_END))
        a,b=coverage_bounds(72)
        self.assertEqual(a,original.CYCLONE_COMPLETE_START+2*86400)
        self.assertEqual(b,original.CYCLONE_COMPLETE_END-2*86400)
        for r,h in ((200,24),(100,48)):
            with self.assertRaises(ValueError):select_windows(rows,'MYS',r,h)
        with self.assertRaises(ValueError):select_windows(rows,'XXX',100,72)

    def test_masks_close_endpoints_and_mark_coverage(self):
        from scripts.cyclone_baseline_sensitivity import masks, coverage_bounds
        a,b=coverage_bounds(72)
        t=np.array([a-600,a,a+600,a+1200,b-600,b])
        expected=[16,4,12,0,0,16]
        got=masks(t,[],[],[(a,a+600)],[(a,a)],72)
        np.testing.assert_array_equal(got,expected)
        np.testing.assert_array_equal(masks(t,[],[],[(a,a+600)],[(a,a)],72),got)

if __name__=='__main__':unittest.main()
