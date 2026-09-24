"""Fail-closed checks for the committed runtime notice evidence."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from runtime_notices import ROOT, INVENTORY, BUNDLE, verify, tree_keys


class RuntimeNotices(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.doc = json.loads((ROOT / INVENTORY).read_text())
        paths = [INVENTORY, BUNDLE, 'release/inputs.lock.json', 'release/review.json']
        paths.extend(self.doc['standalone_notices'])
        for name in paths:
            dest = self.root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, dest)

    def save(self):
        (self.root / INVENTORY).write_text(json.dumps(self.doc))

    def test_current_inventory_accepts_explicit_webc_declaration(self):
        result = verify(self.root)
        self.assertTrue(result['complete'])
        self.assertEqual(result['missing_notices'], [])
        webc = next(p for p in result['packages'] if p['name'] == 'webc')
        self.assertEqual(webc['license'], 'MIT')
        self.assertEqual(webc['notices'], [])
        self.assertEqual(webc['declaration_acceptance']['separate_license_file'], 'unavailable upstream')

    def test_changed_version_rejected(self):
        self.doc['packages'][0]['version'] = '0.0.0'
        self.save()
        with self.assertRaisesRegex(ValueError, 'dependency set'):
            verify(self.root)

    def test_missing_license_metadata_rejected(self):
        self.doc['packages'][0].update(license=None, license_file=None)
        self.save()
        with self.assertRaisesRegex(ValueError, 'license metadata'):
            verify(self.root)

    def test_missing_notice_body_rejected(self):
        notice = next(p for p in self.doc['packages'] if p['notices'])['notices'][0]
        notice['length'] = 0
        self.save()
        with self.assertRaisesRegex(ValueError, 'required notice'):
            verify(self.root)

    def test_changed_standalone_license_rejected(self):
        (self.root / 'licenses/Wasmer-Singlepass-BUSL-1.1.txt').write_text('MIT')
        with self.assertRaisesRegex(ValueError, 'standalone notice'):
            verify(self.root)

    def test_runtime_pin_change_rejected(self):
        self.doc['inputs']['wasmer']['sha256'] = '0' * 64
        self.save()
        with self.assertRaisesRegex(ValueError, 'input pin'):
            verify(self.root)

    def test_approval_with_missing_notice_rejected(self):
        self.doc['complete'] = False
        p = self.doc['packages'][0]
        p.update(notices=[], missing_reason='unreviewed notice gap')
        self.doc['missing_notices'] = [p['name']]
        self.save()
        path = self.root / 'release/review.json'
        review = json.loads(path.read_text())
        review['checks']['runtime_notices'].update(passed=True, evidence=INVENTORY)
        path.write_text(json.dumps(review))
        with self.assertRaisesRegex(ValueError, 'approval lacks complete evidence'):
            verify(self.root)

    def test_cannot_claim_complete_with_missing_notice(self):
        self.doc['complete'] = True
        p = self.doc['packages'][0]
        p.update(notices=[], missing_reason='unreviewed notice gap')
        self.doc['missing_notices'] = [p['name']]
        self.save()
        with self.assertRaisesRegex(ValueError, 'completeness contradicts'):
            verify(self.root)

    def test_changed_webc_declaration_rejected(self):
        p = next(p for p in self.doc['packages'] if p['name'] == 'webc')
        p['license'] = 'Apache-2.0'
        self.save()
        with self.assertRaisesRegex(ValueError, 'unreviewed license declaration'):
            verify(self.root)

    def test_unrecorded_declaration_rejected(self):
        p = next(p for p in self.doc['packages'] if p['name'] == 'webc')
        del p['declaration_acceptance']
        self.save()
        with self.assertRaisesRegex(ValueError, 'unaccounted missing notices'):
            verify(self.root)

    def test_tree_deduplicates_without_local_paths(self):
        self.assertEqual(tree_keys('crate v1.2.3\ncrate v1.2.3 (*)\nlocal v0.1.0 (local/path)\n'),
                         [('crate', '1.2.3'), ('local', '0.1.0')])


if __name__ == '__main__':
    unittest.main()
