"""Negative controls for the finite two-build comparison (no guest compiler)."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_lexer_canonical_builds as check


class CanonicalBuildTests(unittest.TestCase):
    def test_distinct_identity_bytes_and_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / 'first', root / 'second'
            for p in [first, second]:
                p.mkdir(); (p / 'linked.wasm').write_bytes(b'linked'); (p / 'guest.json').write_text('{}')
            sha = 'a' * 40
            record = {'source_commit': sha, 'source_identity': {'commit': sha},
                      'prepared_source': {'overlays': {}, 'lexer_prepared': {'valid': True}},
                      'repetitions': [{'guest_sha256': 'guest', 'linked_sha256': 'linked'}],
                      'guest_sha256': 'guest', 'guest_bytes': 10, 'toolchain': {'version': 1}}
            def invoke(records, path=second):
                with patch.object(check, 'source_identity', return_value={'commit': sha}), \
                     patch.object(check, 'verify_guest', side_effect=records), \
                     patch.object(check, 'verify_record'), \
                     patch.object(check, 'EXPECTED_GUEST', 'guest'), \
                     patch.object(check, 'EXPECTED_LINKED', hashlib.sha256(b'linked').hexdigest()), \
                     patch.dict(os.environ, {'GITHUB_SHA': sha}), \
                     patch.object(sys, 'argv', ['check', '--first', str(first), '--second', str(path), '--output', str(root / 'result.json')]):
                    check.main()
            invoke([record, record])
            result = json.loads((root / 'result.json').read_text())
            self.assertEqual(result['independent_builds'], 2)
            self.assertEqual(result['canonical_runtime_installation'], 'PENDING')
            with self.assertRaisesRegex(ValueError, 'distinct'):
                invoke([record, record], first)
            for mutation in ['source', 'experimental', 'guest', 'toolchain', 'linked']:
                with self.subTest(mutation=mutation):
                    bad = copy.deepcopy(record)
                    if mutation == 'source': bad['source_commit'] = 'b' * 40
                    if mutation == 'experimental': bad['prepared_source']['experimental_patch'] = {'sha': 'bad'}
                    if mutation == 'guest': bad['guest_sha256'] = 'bad'
                    if mutation == 'toolchain': bad['toolchain']['version'] = 2
                    if mutation == 'linked': (second / 'linked.wasm').write_bytes(b'bad')
                    with self.assertRaises(ValueError): invoke([record, bad])
                    (second / 'linked.wasm').write_bytes(b'linked')

    def test_workflow_keeps_independent_regeneration_and_actual_controls(self):
        from workflow_model import manual_platform_commands
        text = manual_platform_commands((ROOT / '.github/workflows/lexer-canonical-input.yml'))
        from workflow_model import load
        def home_values(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == 'HOME':
                        yield item
                    yield from home_values(item)
            elif isinstance(value, list):
                for item in value:
                    yield from home_values(item)
        assert '/root' in set(home_values(load(ROOT/'.github/workflows/lexer-canonical-input.yml')))
        for required in ['test ! -e guest/experimental.patch',
                         'scripts/build_generated_guest.py --repetitions 2',
                         'scripts/regenerate_release_guest.py', 'scripts/check_prepared_build_guards.py',
                         'TestPreparedLexerTablesActualGuest', 'TestWorkerTrapActualGuestNotifiesAndIsolatesPeer',
                         'tests/routine_thread_fixture.py', 'tests/lexer_prepared_acceptance.py',
                         'mysql-connector-python==26.7.0', "-run '^TestCRC32C'"]:
            self.assertIn(required, text)
        self.assertNotIn('  push:', text)
        self.assertNotIn('continue-on-error', text)
        self.assertNotIn('operation: release', text)

        from workflow_model import manual_platform_commands
        candidate = manual_platform_commands((ROOT / '.github/workflows/startup-cap-candidate.yml'))
        for required in [
                         'scripts/build_generated_guest.py --repetitions 2',
                         'test_startup_concurrency.py',
                         'scripts/regenerate_release_guest.py', 'scripts/check_prepared_build_guards.py',
                         'TestPreparedLexerTablesActualGuest', 'TestWorkerTrapActualGuestNotifiesAndIsolatesPeer',
                         'tests/routine_thread_fixture.py', 'tests/lexer_prepared_acceptance.py',
                         'mysql-connector-python==26.7.0', "-run '^TestCRC32C'"]:
            self.assertIn(required, candidate)
        self.assertNotIn('  push:', candidate)
        self.assertNotIn('continue-on-error', candidate)
        self.assertNotIn('operation: release', candidate)


if __name__ == '__main__': unittest.main()
