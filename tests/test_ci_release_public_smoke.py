"""Public smoke checks immutable published identities; no remote writes in tests."""
import json
import os
import shutil
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ci_release_public_smoke as smoke


class PublicSmoke(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.commit, self.tag = 'a' * 40, 'v0.1.0-alpha.4'
        self.names = ['mariamem-native-darwin-arm64.tar.gz',
                      'mariamem-0.1.0a4-py3-none-macosx_15_0_arm64.whl',
                      'mariamem-0.1.0a4-corresponding-source.tar.gz']
        for name in self.names:
            (self.root / name).write_bytes(name.encode())
        self.assets = {n: smoke.digest(self.root / n) for n in self.names}
        (self.root / 'SHA256SUMS').write_text(''.join(h + '  ' + n + '\n' for n, h in self.assets.items()))
        self.assets['SHA256SUMS'] = smoke.digest(self.root / 'SHA256SUMS')

    def consumer(self):
        return {'result': 'PASS', 'module_requested': smoke.MODULE + '@' + self.tag,
                'expected_source_commit': self.commit,
                'module_resolved': {'Version': self.tag, 'Origin': {'Hash': self.commit}},
                'archive': {'sha256': self.assets[self.names[0]]},
                'steps': {s: {'status': 'PASS'} for s in smoke.STEPS}}

    def test_downloaded_bytes_and_checksums(self):
        self.assertEqual(smoke.verify_downloads(self.root, self.assets), self.assets)
        (self.root / self.names[0]).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            smoke.verify_downloads(self.root, self.assets)

    def test_extra_public_asset_rejected(self):
        (self.root / 'other').write_bytes(b'other')
        with self.assertRaisesRegex(ValueError, 'filenames differ'):
            smoke.verify_downloads(self.root, self.assets)

    def test_checksums_must_identify_accepted_bytes(self):
        sums = self.root / 'SHA256SUMS'
        sums.write_text('0' * 64 + '  ' + self.names[0] + '\n')
        self.assets['SHA256SUMS'] = smoke.digest(sums)
        with self.assertRaisesRegex(ValueError, 'differs from accepted'):
            smoke.verify_downloads(self.root, self.assets)

    def test_public_tag_and_native_binding(self):
        evidence = self.consumer()
        smoke.verify_consumer(evidence, self.commit, self.tag, self.assets[self.names[0]])
        evidence['module_resolved']['Origin']['Hash'] = 'b' * 40
        with self.assertRaisesRegex(ValueError, 'another commit'):
            smoke.verify_consumer(evidence, self.commit, self.tag, self.assets[self.names[0]])

    def test_incomplete_smoke_rejected(self):
        evidence = self.consumer()
        evidence['steps']['multi_client']['status'] = 'FAIL'
        with self.assertRaisesRegex(ValueError, 'steps incomplete'):
            smoke.verify_consumer(evidence, self.commit, self.tag, self.assets[self.names[0]])

    def test_public_download_then_isolated_consumer(self):
        publication = self.root / 'publication.json'
        output = self.root / 'out.json'
        publication.write_text(json.dumps({'status': 'PUBLISHED', 'source_commit': self.commit,
                                          'git_tag': self.tag, 'repository': 'owner/repo', 'assets': self.assets}))
        commands = []
        def command(argv, **kwargs):
            commands.append(argv)
            if argv[0] == 'gh':
                directory = Path(argv[argv.index('--dir') + 1])
                self.assertNotEqual(directory.parent, self.root)
                for name in self.assets:
                    shutil.copyfile(self.root / name, directory / name)
            else:
                self.assertNotIn('GH_TOKEN', kwargs['env'])
                self.assertNotIn('GITHUB_TOKEN', kwargs['env'])
                self.assertEqual(argv[argv.index('--module') + 1], self.tag)
                self.assertEqual(argv[argv.index('--expected-commit') + 1], self.commit)
                evidence = Path(argv[argv.index('--evidence') + 1])
                consumer = self.consumer()
                consumer['environment'] = {'product_version': '15.7.1', 'architecture': 'arm64'}
                evidence.write_text(json.dumps(consumer))
                evidence.with_suffix('.log').write_text('consumer log')
            class Result:
                returncode, stdout, stderr = 0, '', ''
            return Result()
        with patch.dict(os.environ, {'GH_TOKEN': 'secret', 'GITHUB_TOKEN': 'secret'}), patch.object(smoke.subprocess, 'run', command):
            report = smoke.smoke(self.root, 'owner/repo', publication, output)
        self.assertEqual(report['result'], 'PASS')
        self.assertEqual(len(commands), 2)
        self.assertEqual(report['downloaded_hashes'], self.assets)
        self.assertEqual(output.with_name('out-consumer.log').read_text(), 'consumer log')
        self.assertFalse(Path(commands[0][commands[0].index('--dir') + 1]).exists())

    def test_download_failure_report_never_mutates_release(self):
        report_path = self.root / 'out.json'
        publication = self.root / 'publication.json'
        publication.write_text(json.dumps({'status': 'PUBLISHED', 'source_commit': self.commit,
                                          'git_tag': self.tag, 'repository': 'owner/repo', 'assets': self.assets}))
        commands = []
        def failed(argv, **kwargs):
            commands.append(argv)
            class Result:
                returncode, stdout, stderr = 1, '', 'download failed'
            return Result()
        with patch.object(smoke.subprocess, 'run', failed):
            report = smoke.smoke(self.root, 'owner/repo', publication, report_path)
        self.assertEqual(report['result'], 'FAIL')
        self.assertEqual(report['stage'], 'published_download')
        self.assertEqual(commands[0][:3], ['gh', 'release', 'download'])
        self.assertEqual(len(commands), 1)
        self.assertTrue(report['nothing_modified'])
        self.assertEqual(json.loads(report_path.read_text())['result'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
