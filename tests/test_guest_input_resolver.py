"""Reject wrong selections, changed pins and stale preparation receipts before use."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from guest_input_resolver import resolve_inputs, InputError
import guest_preparation_context as context


def encoded(x):
    return (json.dumps(x, sort_keys=True, separators=(',', ':')) + '\n').encode()


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / 'guest/versions/registry.json').read_text())
        self.entry = self.registry['selections']['12.3.3/legacy-full']
        self.name = self.entry['descriptor']['file']
        self.descriptor = json.loads((ROOT / self.name).read_text())
        self.files = {}

    def resolve(self, engine='12.3.3', profile='legacy-full'):
        raw = encoded(self.descriptor)
        self.files[self.name] = raw
        self.entry['descriptor']['sha256'] = hashlib.sha256(raw).hexdigest()
        def read(name):
            return self.files[name] if name in self.files else (ROOT / name).read_bytes()
        return resolve_inputs(encoded(self.registry), engine, profile, read)

    def test_unchanged_resolution_is_deterministic(self):
        self.assertEqual(self.resolve(), self.resolve())

    def test_wrong_engine_profile_and_no_fallback(self):
        for engine, profile in [('13.3', 'legacy-full'), ('12.3.3', 'native-text')]:
            with self.subTest(engine=engine, profile=profile), self.assertRaises(InputError):
                self.resolve(engine, profile)

    def test_changed_selection_stage_lock_and_patch_fail(self):
        for field, value in [('engine', '13.0.2'), ('stages', ['patches']),
                             ('preparation_features', ['unknown'])]:
            with self.subTest(field=field):
                saved = copy.deepcopy(self.descriptor)
                self.descriptor[field] = value
                with self.assertRaises(InputError): self.resolve()
                self.descriptor = saved
        lock = self.descriptor['shared_lock']['file']
        self.files[lock] = b'{}'
        with self.assertRaises(InputError): self.resolve()
        self.files.clear()
        patchfile = next(iter(self.descriptor['files'].values()))['file']
        self.files[patchfile] = b'changed'
        with self.assertRaises(InputError): self.resolve()

    def test_unsafe_input_path_and_conflated_tag_fail(self):
        self.descriptor['files']['../escape'] = next(iter(self.descriptor['files'].values()))
        with self.assertRaises(InputError): self.resolve()
        del self.descriptor['files']['../escape']
        guest = self.descriptor['guest_input']
        guest['source_commit'] = guest['tag_object_sha']
        with self.assertRaises(InputError): self.resolve()

    def test_stale_mixed_receipt_and_changed_source_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory) / 'run'
            def prepare(view, lock, target, fetch, *, selected, features):
                (target / 'source').mkdir()
                (target / 'source/proof').write_bytes(b'proof')
                return {'schema':'selected-source-preparation-v1', 'release_eligible':False,
                        'modified_files': {'proof':hashlib.sha256(b'proof').hexdigest()}}
            with patch('prepare_guest.prepare', side_effect=prepare):
                context.prepare_selected(ROOT, '12.3.3', 'legacy-full', work)
            context.verify_receipt(ROOT, '12.3.3', 'legacy-full', work)
            with self.assertRaisesRegex(ValueError, 'stale or mixed'):
                context.verify_receipt(ROOT, '13.0.2', 'legacy-full', work)
            path = work / 'resolved-input.json'
            raw = path.read_bytes()
            path.write_bytes(raw + b' ')
            with self.assertRaisesRegex(ValueError, 'stale or mixed'):
                context.verify_receipt(ROOT, '12.3.3', 'legacy-full', work)
            path.write_bytes(raw)
            (work / 'source/proof').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'source changed'):
                context.verify_receipt(ROOT, '12.3.3', 'legacy-full', work)

if __name__ == '__main__':
    unittest.main()
