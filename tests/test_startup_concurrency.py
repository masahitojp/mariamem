"""Reject a lost startup remedy, omitted work, or changed recovery lock order."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import startup_concurrency as cap


class StartupConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)
        for name, region in cap.REGIONS.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(region)

    def test_normal_regions_and_readonly_hashes(self):
        result = cap.validate(self.source)
        self.assertEqual(result, cap.validate(self.source))
        self.assertEqual(set(result['files_sha256']), set(cap.REGIONS))

    def test_restricted_or_missing_operation_reset_or_lock_rejected(self):
        for name, region in cap.REGIONS.items():
            mutations = [
                region.replace('set_concurrency()', 'set_concurrency(srv_n_read_io_threads)', 1),
                region.replace('set_concurrency()', 'set_concurrency(16)', 1),
                region.rsplit('srv_thread_pool->set_concurrency();', 1)[0],
                region + '\nsrv_thread_pool->set_concurrency();',
                region.replace('buf_load();', '').replace('recv_sys.apply(true);', ''),
            ]
            if 'mysql_mutex_lock' in region:
                mutations.append(region.replace('mysql_mutex_lock', 'mysql_mutex_unlock', 1))
            for mutation in mutations:
                with self.subTest(name=name, mutation=mutation):
                    (self.source / name).write_text(mutation)
                    with self.assertRaises(ValueError):
                        cap.validate(self.source)
            (self.source / name).write_text(region)


if __name__ == '__main__':
    unittest.main()
