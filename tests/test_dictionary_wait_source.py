"""Guard source migration and exact build identity, without claiming guest execution."""
import copy
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import prepare_guest

spec = importlib.util.spec_from_file_location('dictionary_source', ROOT/'scripts/check_dictionary_wait_source.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class DictionarySourceTests(unittest.TestCase):
    def test_accepted_exact_delta(self):
        self.assertEqual(guard.source(ROOT)['dictionary_delta_sha256'], guard.DELTA_SHA)

    def test_source_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('guest/source.patch', 'guest/versions/12.3.3/legacy-full.json'):
                p = root/name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes((ROOT/name).read_bytes())
            patch = root/'guest/source.patch'
            original = patch.read_bytes()
            guard.source(root)
            for old, new in [(b'+\t\ttpool::tpool_wait_begin();', b'+\t\t/* omitted */'),
                             (b'+\t\ttpool::tpool_wait_end();', b'+\t\t/* omitted */'),
                             (b'+\tif (!latch.wr_lock_try()) {', b'+\tif (true) {')]:
                self.assertEqual(original.count(old), 1)
                patch.write_bytes(original.replace(old, new))
                with self.assertRaises(ValueError):
                    guard.source(root)
            patch.write_bytes(b'X'+original[1:])
            with self.assertRaisesRegex(ValueError, 'base'):
                guard.source(root)
            patch.write_bytes(original)
            experimental = root/'guest/experimental.patch'
            experimental.write_text('duplicate')
            with self.assertRaisesRegex(ValueError, 'experimental'):
                guard.source(root)
            experimental.unlink()
            p = root/'guest/versions/12.3.3/legacy-full.json'
            profile = json.loads(p.read_text())
            profile['files']['guest/source.patch']['sha256'] = '0'*64
            p.write_text(json.dumps(profile))
            with self.assertRaisesRegex(ValueError, 'pin'):
                guard.source(root)

    def test_prepared_body_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/guard.FILE
            p.parent.mkdir(parents=True)
            p.write_text('wrong body')
            with self.assertRaisesRegex(ValueError, 'prepared'):
                guard.prepared(Path(tmp))

    def test_preparation_records_actual_dictionary_bytes(self):
        # Exercise the real manifest producer, not a hand-written accepted receipt.
        # Archive/tooling stubs avoid downloading or compiling MariaDB here.
        for selected in (False, True):
            with self.subTest(selected=selected), tempfile.TemporaryDirectory() as tmp:
                root, build = Path(tmp)/'root', Path(tmp)/'build'
                (root/'guest').mkdir(parents=True)
                (root/'release').mkdir()
                lock = {'pristine_files': {}, 'inputs': [
                    {'name': name, 'file': name+'.tar', 'url': 'https://example.invalid/'+name}
                    for name in ('pcre2', 'libfmt')]}
                (root/'release/inputs.lock.json').write_text(json.dumps(lock))
                for name in ('wire_core.inc', 'resident.inc', 'snapshot_fs.inc',
                             'startup_timing.inc', 'init_diagnostics.inc',
                             'prepared_auth_keys.inc', 'routine_bootstrap.inc',
                             'prepared_api.inc', 'init_diagnostics.h', 'source.patch'):
                    (root/'guest'/name).write_text('fixture input\n')
                archive = root/'archive'
                archive.write_bytes(b'fixture archive')
                guest_input = {'source_input': 'mariadb', 'recipe_files_sha256': {}, 'patches': []}
                body = b'actual prepared dictionary bytes\n'

                def extract(_archive, target):
                    tree = target/'unpacked'
                    tree.mkdir(parents=True)
                    if target.name == 'mariadb':
                        for name, data in {
                            guard.FILE: body, 'auth.h': b'auth', 'routine.h': b'routine',
                            'wasm/CMakeLists.txt': b'  TARGET_LINK_OPTIONS(lite4mariadb-wasix PRIVATE\n',
                            'cmake/pcre.cmake': lock['inputs'][0]['url'].encode(),
                            'cmake/libfmt.cmake': lock['inputs'][1]['url'].encode(),
                        }.items():
                            path = tree/name
                            path.parent.mkdir(parents=True, exist_ok=True)
                            path.write_bytes(data)
                        (tree/'extra/wolfssl').mkdir(parents=True)
                        (tree/'include').mkdir()

                with patch.object(prepare_guest, 'extract', side_effect=extract), \
                     patch.object(prepare_guest, 'descriptor', return_value=guest_input), \
                     patch.object(prepare_guest, 'apply_series', return_value=[]), \
                     patch.object(prepare_guest.subprocess, 'run'), \
                     patch.object(prepare_guest, 'instrument', return_value=[]), \
                     patch.object(prepare_guest, 'prepare_auth_source', return_value=[]), \
                     patch.object(prepare_guest, 'write_header', return_value='auth.h'), \
                     patch.object(prepare_guest, 'prepare_routine_schema', return_value={'header': 'routine.h'}):
                    manifest = prepare_guest.prepare(
                        root, lock, build, lambda _name: archive, features=[],
                        selected=guest_input if selected else None)
                expected = hashlib.sha256(body).hexdigest()
                self.assertEqual(manifest['modified_files'].get(guard.FILE), expected)
                saved = json.loads((build/'prepared-source.json').read_text())
                self.assertEqual(saved['modified_files'][guard.FILE], expected)

    def test_build_record_mutations(self):
        commit = 'a'*40
        record = dict(source_commit=commit, source_identity={'commit': commit},
                      contract='development-unqualified-v1', result='UNQUALIFIED',
                      guest_sha256=guard.GUEST,
                      repetitions=[dict(guest_sha256=guard.GUEST, linked_sha256=guard.LINKED)],
                      prepared_source={'overlays': {}, 'modified_files': {guard.FILE: guard.PREPARED_SHA}})
        guard.validate_record(record, commit)
        changes = [lambda r: r.update(source_commit='b'*40),
                   lambda r: r['source_identity'].update(commit='b'*40),
                   lambda r: r.update(result='PASS'),
                   lambda r: r.update(contract='generated-go-v1'),
                   lambda r: r.update(guest_sha256='0'*64),
                   lambda r: r['repetitions'][0].update(linked_sha256='0'*64),
                   lambda r: r['repetitions'].append(r['repetitions'][0]),
                   lambda r: r['prepared_source'].update(experimental_patch={'file': 'guest/experimental.patch'}),
                   lambda r: r['prepared_source']['overlays'].update({'experimental.patch': '0'*64}),
                   lambda r: r['prepared_source']['modified_files'].update({guard.FILE: '0'*64}),
                   lambda r: r['prepared_source']['modified_files'].pop(guard.FILE)]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                broken = copy.deepcopy(record)
                change(broken)
                with self.assertRaises(ValueError):
                    guard.validate_record(broken, commit)

    def test_builder_and_normal_source_owner(self):
        self.assertIn('tests/test_dictionary_wait_source.py', (ROOT/'scripts/verify.py').read_text())
        builder = (ROOT/'scripts/build_generated_guest.py').read_text()
        self.assertLess(builder.index("'--prepared-source', ROOT/'build/source'"), builder.index("shutil.move(str(ROOT/'build/source')"))
        self.assertIn("if not development:\n            observed_run([sys.executable, ROOT/'scripts/check_dictionary_wait_source.py'", builder)
        workflow = (ROOT/'.github/workflows/dict-wait-experiment.yml').read_text()
        for value in ('workflow_dispatch:', 'test ! -e guest/experimental.patch',
                      '--development-output /dict-product/guest',
                      'scripts/check_dictionary_wait_source.py --guest-dir',
                      '-s tests -p test_dictionary_wait_source.py'):
            self.assertIn(value, workflow)
        for forbidden in ('  push:', 'continue-on-error:', 'operation: release'):
            self.assertNotIn(forbidden, workflow)


if __name__ == '__main__':
    unittest.main()
