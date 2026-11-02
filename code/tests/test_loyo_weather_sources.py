import unittest
from scripts.loyo_weather_sources import verify_monthly_membership

class MembershipTest(unittest.TestCase):
    def test_exact_hash_and_unique_path_membership_required(self):
        entries={'/tmp/a.csv':{'sha256':'a'}, '/tmp/a.audit.json':{'sha256':'b'}}
        verify_monthly_membership(entries, '/tmp/a.csv', {'sha256':'a','audit_sha256':'b'})
        with self.assertRaises(ValueError):
            verify_monthly_membership(entries, '/tmp/a.csv', {'sha256':'x','audit_sha256':'b'})
        with self.assertRaises(ValueError):
            verify_monthly_membership({}, '/tmp/a.csv', {'sha256':'a','audit_sha256':'b'})
