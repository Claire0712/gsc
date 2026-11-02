import unittest

class SyncComparisonGateTest(unittest.TestCase):
    def test_exact_universe_required(self):
        from scripts.run_sync_comparison import validate_universe
        validate_universe({'sync_universe':'joint'},'joint')
        for summary,universe in (({},'joint'),({'sync_universe':'all'},'joint'),({'sync_universe':'x'},'x')):
            with self.assertRaises(ValueError):validate_universe(summary,universe)

if __name__=='__main__':unittest.main()
