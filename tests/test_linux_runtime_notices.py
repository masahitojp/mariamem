import json
import shutil
import unittest
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import runtime_notices as common
import linux_runtime_notices as linux


class LinuxRuntimeNotices(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        base = json.loads((common.ROOT / common.INVENTORY).read_text())
        paths = [common.INVENTORY, common.BUNDLE, 'release/inputs.lock.json', 'release/review.json']
        paths.extend(base['standalone_notices'])
        for name in paths:
            dest = self.root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(common.ROOT / name, dest)
        for name in (linux.INVENTORY, linux.BUNDLE):
            dest = self.root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(linux.ROOT / name, dest)
        self.linux_doc = json.loads((self.root / linux.INVENTORY).read_text())

    def change_linux(self):
        (self.root / linux.INVENTORY).write_text(json.dumps(self.linux_doc))

    def test_linux_complete(self):
        self.assertTrue(linux.verify(self.root)['complete'])
        self.assertEqual(len(self.linux_doc['additional_packages']), 5)

    def test_linux_wrong_runtime(self):
        self.linux_doc['runtime_archive_sha256'] = '0' * 64
        self.change_linux()
        with self.assertRaisesRegex(ValueError, 'pin/target'):
            linux.verify(self.root)

    def test_linux_missing_dependency(self):
        self.linux_doc['additional_packages'].pop()
        self.change_linux()
        with self.assertRaisesRegex(ValueError, 'coverage'):
            linux.verify(self.root)

    def test_linux_changed_notice(self):
        (self.root / linux.BUNDLE).write_text('incomplete')
        with self.assertRaisesRegex(ValueError, 'bundle'):
            linux.verify(self.root)

    def test_linux_wrong_source(self):
        self.linux_doc['wasmer_source_sha256'] = '0' * 64
        self.change_linux()
        with self.assertRaisesRegex(ValueError, 'source pin'):
            linux.verify(self.root)
