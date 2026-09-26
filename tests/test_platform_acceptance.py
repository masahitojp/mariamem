"""Archive and environment boundaries; never start MariaDB in unit tests."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import platform_acceptance as harness


class PlatformHarness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / 'candidate.tar.gz'
        self.evidence = self.root / 'evidence.json'

    def archive_with(self, members):
        with tarfile.open(self.archive, 'w:gz') as tar:
            for name, content, kind, mode in members:
                info = tarfile.TarInfo(name)
                info.mode, info.type = mode, kind
                if kind == tarfile.REGTYPE:
                    info.size = len(content)
                    tar.addfile(info, io.BytesIO(content))
                else:
                    info.linkname = content.decode()
                    tar.addfile(info)

    def fixture(self, executable=True):
        files = {'wasmer-headless': b'inert runtime', 'mariamem.wasmu': b'inert guest'}
        files['mariamem.wasmu.json'] = json.dumps({'module_sha256': hashlib.sha256(files['mariamem.wasmu']).hexdigest(), 'wasm_sha256': 'a'*64}).encode()
        files['manifest.json'] = json.dumps({'version': 1, 'platform': 'darwin-arm64', 'minimum_macos': 15, 'sha256': {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}}).encode()
        self.archive_with([(harness.BUNDLE+'/'+k, v, tarfile.REGTYPE, 0o755 if k=='wasmer-headless' and executable else 0o644) for k,v in files.items()])

    def run_harness(self, dry=True, expected=None):
        argv = ['harness', '--archive', str(self.archive), '--sha256', expected or harness.digest(self.archive), '--module', '7f4820e', '--evidence', str(self.evidence)]
        if dry:
            argv.append('--dry-run')
        def command(args, **kwargs):
            outputs = {('/usr/bin/sw_vers',): 'ProductVersion: 27.0\nBuildVersion: 26A428',
                       ('/usr/bin/sw_vers','-productVersion'): '27.0',
                       ('/usr/bin/uname','-m'): 'arm64', ('go','version'): 'go version go1.26.8 darwin/arm64'}
            # Any module fetch/build/consumer run in dry-run is a test failure.
            return subprocess.CompletedProcess(args, 0, outputs[tuple(args)], '')
        with patch.object(sys, 'argv', argv), patch.object(harness.subprocess, 'run', command), patch('builtins.print'):
            code = harness.main()
        return code, json.loads(self.evidence.read_text())

    def test_dry_run_never_claims_acceptance(self):
        self.fixture()
        code, e = self.run_harness()
        self.assertEqual(code, 0)
        self.assertEqual(e['result'], 'DRY_RUN')
        self.assertFalse(e['platform_acceptance_passed'])
        self.assertEqual(e['steps']['module_fetch']['status'], 'NOT_RUN')
        self.assertEqual(e['steps']['harness_cleanup']['status'], 'PASS')

    def test_wrong_platform_rejected_before_fetch(self):
        self.fixture()
        code, e = self.run_harness(dry=False)
        self.assertEqual(code, 1)
        self.assertEqual(e['failure']['step'], 'environment')

    def test_checksum_failure_is_identified(self):
        self.fixture()
        code, e = self.run_harness(expected='0'*64)
        self.assertEqual(code, 1)
        self.assertEqual(e['failure']['step'], 'archive_sha256')

    def test_permission_not_silently_repaired(self):
        self.fixture(executable=False)
        code, e = self.run_harness()
        self.assertEqual(code, 1)
        self.assertEqual(e['failure']['step'], 'executable_permission')

    def test_reject_unsafe_archive_members(self):
        for name, kind in [(harness.BUNDLE+'/../escape',tarfile.REGTYPE),
                           ('/absolute',tarfile.REGTYPE),
                           (harness.BUNDLE+'/link',tarfile.SYMTYPE),
                           (harness.BUNDLE+'/hardlink',tarfile.LNKTYPE)]:
            with self.subTest(name=name):
                self.archive_with([(name,b'elsewhere',kind,0o644)])
                with self.assertRaisesRegex(ValueError,'unsafe'):
                    harness.extract(self.archive, self.root/'out')

    def test_artifact_hash_mismatch(self):
        self.fixture()
        native=harness.extract(self.archive,self.root/'out')
        (native/'mariamem.wasmu').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'artifact hash'):
            harness.check_artifacts(native)

    def test_ambient_go_and_native_settings_removed(self):
        with patch.dict(os.environ, {'GOWORK':'ambient', 'GOFLAGS':'-modfile=other', 'MARIAMEM_NATIVE_DIR':'ambient', 'WASMER_DIR':'ambient', 'GH_TOKEN':'secret', 'GITHUB_TOKEN':'secret'}):
            env=harness.isolated_env(self.root)
        self.assertEqual(env['GOWORK'],'off')
        self.assertEqual(env['GOFLAGS'],'-modcacherw')
        self.assertEqual(env['GOMODCACHE'],str(self.root/'modcache'))
        self.assertNotIn('MARIAMEM_NATIVE_DIR',env)
        self.assertNotIn('WASMER_DIR',env)
        self.assertNotIn('GH_TOKEN',env)
        self.assertNotIn('GITHUB_TOKEN',env)

    def test_exact_public_commit_binding(self):
        commit = 'a' * 40
        module = {'Path': harness.MODULE, 'Version': 'v0.0.0-example', 'Sum': 'h1:test',
                  'Origin': {'Hash': commit}}
        harness.verify_resolved_commit(module, commit)
        with self.assertRaisesRegex(ValueError, 'public module commit mismatch'):
            harness.verify_resolved_commit({**module, 'Origin': {'Hash': 'b' * 40}}, commit)
        with self.assertRaisesRegex(ValueError, 'resolved unknown'):
            harness.verify_resolved_commit({**module, 'Origin': {}}, commit)
        with self.assertRaisesRegex(ValueError, 'identity/version/checksum'):
            harness.verify_resolved_commit({**module, 'Path': 'example.com/other'}, commit)

    def test_public_tag_binds_exact_version_and_commit(self):
        commit, tag = 'a' * 40, 'v0.1.0-alpha.4'
        fetched = {'Path': harness.MODULE, 'Version': tag, 'Sum': 'h1:test'}
        remote = {'Path': harness.MODULE, 'Version': tag, 'Origin': {'Hash': commit}}
        harness.bind_remote_origin(fetched, remote, commit, tag)
        with self.assertRaisesRegex(ValueError, 'requested release tag'):
            harness.bind_remote_origin(fetched, remote, commit, 'v0.1.0-alpha.5')

    def test_proxy_identity_bound_to_direct_remote_origin(self):
        commit = 'a' * 40
        fetched = {'Path': harness.MODULE, 'Version': 'v0.0.0-example', 'Sum': 'h1:test'}
        remote = {'Path': harness.MODULE, 'Version': fetched['Version'], 'Origin': {'Hash': commit}}
        bound = harness.bind_remote_origin(fetched, remote, commit)
        self.assertEqual(bound['Sum'], fetched['Sum'])
        self.assertEqual(bound['Origin']['Hash'], commit)
        with self.assertRaisesRegex(ValueError, 'identity/version differs'):
            harness.bind_remote_origin(fetched, {**remote, 'Version': 'v0.0.1'}, commit)
        with self.assertRaisesRegex(ValueError, 'commit mismatch'):
            harness.bind_remote_origin(fetched, {**remote, 'Origin': {'Hash': 'b' * 40}}, commit)

    def test_mocked_external_consumer_orchestration(self):
        self.fixture()
        argv = ['harness', '--archive', str(self.archive), '--sha256', harness.digest(self.archive),
                '--module', '7f4820e', '--evidence', str(self.evidence)]
        spawned = []
        def command(args, **kwargs):
            if args[0] == '/usr/bin/sw_vers':
                text = '15.7.1' if len(args) > 1 else 'ProductVersion: 15.7.1'
            elif args[0] == '/usr/bin/uname':
                text = 'arm64'
            elif args[1] == 'version':
                text = 'go version go1.26.8 darwin/arm64'
            else:
                self.assertEqual(kwargs['env']['GOWORK'], 'off')
                self.assertNotEqual(kwargs['cwd'], Path.cwd())
                text = json.dumps({'Path': harness.MODULE, 'Version': 'v0.0.0-example'}) if args[1] == 'list' else ''
            return subprocess.CompletedProcess(args, 0, text, '')
        def consumer(args, **kwargs):
            native = Path(args[1])
            self.assertTrue((native/'wasmer-headless').exists())
            self.assertEqual(native.name, harness.BUNDLE)
            spawned.append(native)
            events = [{'step': s, 'status': 'PASS'} for s in harness.STEPS[harness.STEPS.index('NativeDir'):-1]]
            proc = Mock()
            proc.stdout = io.StringIO(''.join(json.dumps(e)+'\n' for e in events))
            proc.wait.return_value = proc.poll.return_value = 0
            return proc
        with patch.object(sys, 'argv', argv), patch.object(harness.subprocess, 'run', command), patch.object(harness.subprocess, 'Popen', consumer), patch('builtins.print'):
            code = harness.main()
        e = json.loads(self.evidence.read_text())
        self.assertEqual(code, 0)
        self.assertEqual(e['result'], 'PASS')
        self.assertTrue(e['platform_acceptance_passed'])
        self.assertTrue(all(v['status']=='PASS' for v in e['steps'].values()))
        self.assertFalse(spawned[0].exists())

    def test_expected_commit_rejects_wrong_public_module(self):
        self.fixture()
        expected = 'a' * 40
        argv = ['harness', '--archive', str(self.archive), '--sha256', harness.digest(self.archive),
                '--module', expected, '--expected-commit', expected, '--evidence', str(self.evidence)]
        def command(args, **kwargs):
            if args[0] == '/usr/bin/sw_vers':
                text = '15.7.1' if len(args) > 1 else 'ProductVersion: 15.7.1'
            elif args[0] == '/usr/bin/uname':
                text = 'arm64'
            elif args[1] == 'version':
                text = 'go version go1.26.8 darwin/arm64'
            else:
                text = json.dumps({'Path': harness.MODULE, 'Version': 'v0.0.0-example',
                                   'Sum': 'h1:test', 'Origin': {'Hash': 'b' * 40}}) if args[1] == 'list' else ''
            return subprocess.CompletedProcess(args, 0, text, '')
        with patch.object(sys, 'argv', argv), patch.object(harness.subprocess, 'run', command), patch('builtins.print'):
            code = harness.main()
        evidence = json.loads(self.evidence.read_text())
        self.assertEqual(code, 1)
        self.assertEqual(evidence['failure']['step'], 'module_fetch')
        self.assertIn('public module commit mismatch', evidence['failure']['error'])

    def test_platform_requires_exact_major_and_arch(self):
        self.assertTrue(harness.eligible('15.7.1','arm64'))
        self.assertFalse(harness.eligible('27.0','arm64'))
        for version in ('12.5.1', '13.7.0', '14.7.0'):
            self.assertFalse(harness.eligible(version, 'arm64'))
        self.assertFalse(harness.eligible('15.7.1','x86_64'))


if __name__ == '__main__':
    unittest.main()
