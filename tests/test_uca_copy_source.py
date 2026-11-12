"""Fail-closed migration controls; no claim of runtime or SQL coverage."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('uca_copy_source', ROOT/'scripts/check_uca_copy_source.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class UCACopySourceTests(unittest.TestCase):
    def test_accepted_exact_source_and_profile(self):
        self.assertEqual(guard.source(ROOT)['accepted_delta_sha256'], guard.DELTA_PATCH)

    def test_source_and_profile_mutations_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('guest/source.patch', 'guest/versions/12.3.3/legacy-full.json'):
                target = root/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT/name).read_bytes())
            guard.source(root)
            path = root/'guest/source.patch'
            original = path.read_bytes()
            for index in (10, len(original)-10):
                damaged = bytearray(original); damaged[index] ^= 1
                path.write_bytes(damaged)
                with self.assertRaises(ValueError):
                    guard.source(root)
            path.write_bytes(original)
            path = root/'guest/experimental.patch'; path.write_text('duplicate')
            with self.assertRaisesRegex(ValueError, 'experimental'):
                guard.source(root)
            path.unlink()
            path = root/'guest/versions/12.3.3/legacy-full.json'
            data = json.loads(path.read_text()); data['files']['guest/source.patch']['sha256'] = '0'*64
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'source pin'):
                guard.source(root)

    def test_build_record_mutations_rejected(self):
        commit = 'a'*40
        record = dict(source_commit=commit, source_identity={'commit': commit},
                      contract='development-unqualified-v1', result='UNQUALIFIED',
                      guest_sha256=guard.GUEST,
                      repetitions=[dict(guest_sha256=guard.GUEST, linked_sha256=guard.LINKED)],
                      prepared_source={'overlays': {}, 'modified_files': dict(guard.PREPARED)})
        guard.validate_record(record, commit)
        mutations = [
            lambda r: r.update(source_commit='b'*40),
            lambda r: r['source_identity'].update(commit='b'*40),
            lambda r: r.update(result='PASS'),
            lambda r: r.update(contract='generated-go-v1'),
            lambda r: r.update(guest_sha256='0'*64),
            lambda r: r['repetitions'][0].update(linked_sha256='0'*64),
            lambda r: r['prepared_source'].update(experimental_patch={'file':'guest/experimental.patch'}),
            lambda r: r['prepared_source']['overlays'].update({'experimental.patch':'0'*64}),
            lambda r: r['prepared_source']['modified_files'].pop('strings/mariamem_uca_copy_prepared.h'),
            lambda r: r['prepared_source']['modified_files'].update({'strings/ctype-uca.c':'0'*64}),
        ]
        for index, change in enumerate(mutations):
            with self.subTest(mutation=index):
                broken = copy.deepcopy(record); change(broken)
                with self.assertRaises(ValueError):
                    guard.validate_record(broken, commit)

    def test_canonical_gate_is_manual_and_requires_real_platform_controls(self):
        text = (ROOT/'.github/workflows/uca-canonical.yml').read_text()
        for expected in ('  workflow_dispatch:', 'timeout-minutes: 100',
                         'test ! -e guest/experimental.patch',
                         'scripts/build_generated_guest.py --repetitions 2',
                         'runner: [macos-15, ubuntu-24.04]',
                         'scripts/regenerate_release_guest.py',
                         'scripts/check_prepared_build_guards.py',
                         'test_uca_copy_source.py',
                         'TestUCACopyActualGuest|TestPreparedUCATablesActualGuest|TestPreparedLexerTablesActualGuest',
                         'tests/routine_thread_fixture.py',
                         'tests/uca_copy_acceptance.py --native-port',
                         'tests/uca_copy_acceptance.py --host',
                         'tests/test_uca_copy_resnapshot.py',
                         'TestAnalyzeTimerFreshAndFork'):
            self.assertIn(expected, text)
        for forbidden in ('  push:', 'continue-on-error:', 'operation: release'):
            self.assertNotIn(forbidden, text)


if __name__ == '__main__':
    unittest.main()
