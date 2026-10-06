"""Public smoke checks immutable published identities; no remote writes in tests."""
import json
import os
import shutil
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import ci_release_public_smoke as smoke
from test_release_consumer_smoke import accepted, ROOT


class PublicSmoke(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'assets'
        self.root.mkdir()
        self.commit, self.tag = 'a' * 40, 'v0.3.0'
        self.names = ['mariamem-native-darwin-arm64.tar.gz',
                      'mariamem-0.3.0-py3-none-macosx_15_0_arm64.whl',
                      'mariamem-0.3.0-corresponding-source.tar.gz']
        for name in self.names:
            (self.root / name).write_bytes(name.encode())
        self.assets = {n: smoke.digest(self.root / n) for n in self.names}
        (self.root / 'SHA256SUMS').write_text(''.join(h + '  ' + n + '\n' for n, h in self.assets.items()))
        self.assets['SHA256SUMS'] = smoke.digest(self.root / 'SHA256SUMS')
        self.checkout = Path(self.temp.name) / 'checkout'
        (self.checkout / 'release').mkdir(parents=True)
        shutil.copyfile(ROOT / 'release/inputs.lock.json', self.checkout / 'release/inputs.lock.json')

    def consumer(self, target=smoke.DARWIN):
        record = accepted(target)
        native = smoke.target_metadata(target)['bundle_name'] + '.tar.gz'
        wheel = f"mariamem-0.3.0-py3-none-{smoke.target_metadata(target)['wheel_platform']}.whl"
        record.update(mode='published', module_resolved={'Version': self.tag, 'Origin': {'Hash': self.commit}},
                      native_sha256=self.assets[native], wheel_sha256=self.assets[wheel])
        record['go']['receipt']['archive_sha256'] = self.assets[native]
        record['python']['wheel_sha256'] = self.assets[wheel]
        return record

    def verify(self, evidence):
        return smoke.verify_consumer(evidence, self.commit, self.tag, self.assets[self.names[0]],
                                     self.assets[self.names[1]], smoke.digest(self.checkout / 'release/inputs.lock.json'))

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
        self.verify(evidence)
        evidence['module_resolved']['Origin']['Hash'] = 'b' * 40
        with self.assertRaisesRegex(ValueError, 'another commit'):
            self.verify(evidence)

    def test_incomplete_smoke_rejected(self):
        evidence = self.consumer()
        evidence['steps']['go_zero_setup'] = 'FAIL'
        with self.assertRaisesRegex(ValueError, 'steps incomplete'):
            self.verify(evidence)

    def test_public_download_then_isolated_consumer(self):
        publication = self.checkout / 'publication.json'
        output = self.checkout / 'out.json'
        publication.write_text(json.dumps({'status':'PUBLISHED', 'source_commit':self.commit,
                                          'git_tag':self.tag, 'repository':'owner/repo', 'assets':self.assets}))
        commands = []
        def command(argv, **kwargs):
            commands.append(argv)
            directory = Path(argv[argv.index('--dir') + 1])
            for name in self.assets:
                shutil.copyfile(self.root / name, directory / name)
            class Result:
                returncode, stdout, stderr = 0, '', ''
            return Result()
        def consumers(root, commit, archive, wheel, output, **kwargs):
            self.assertEqual(root, self.checkout.resolve())
            self.assertEqual(commit, self.commit)
            self.assertEqual(kwargs, {'mode':'published', 'tag':self.tag})
            self.assertEqual(smoke.digest(archive), self.assets[archive.name])
            self.assertEqual(smoke.digest(wheel), self.assets[wheel.name])
            report = self.consumer()
            output.write_text(json.dumps(report))
            output.with_suffix('.log').write_text('consumer log')
            return report
        with patch.object(smoke.subprocess, 'run', command), patch.object(smoke, 'run_consumers', consumers):
            report = smoke.smoke(self.checkout, 'owner/repo', publication, output)
        self.assertEqual(report['result'], 'PASS')
        self.assertEqual(len(commands), 1)
        self.assertEqual(report['downloaded_hashes'], self.assets)
        self.assertEqual(output.with_name('out-consumer.log').read_text(), 'consumer log')
        self.assertFalse(Path(commands[0][commands[0].index('--dir') + 1]).exists())

    def test_download_failure_report_never_mutates_release(self):
        report_path = self.checkout / 'out.json'
        publication = self.checkout / 'publication.json'
        publication.write_text(json.dumps({'status': 'PUBLISHED', 'source_commit': self.commit,
                                          'git_tag': self.tag, 'repository': 'owner/repo', 'assets': self.assets}))
        commands = []
        def failed(argv, **kwargs):
            commands.append(argv)
            class Result:
                returncode, stdout, stderr = 1, '', 'download failed'
            return Result()
        with patch.object(smoke.subprocess, 'run', failed):
            report = smoke.smoke(self.checkout, 'owner/repo', publication, report_path)
        self.assertEqual(report['result'], 'FAIL')
        self.assertEqual(report['stage'], 'published_download')
        self.assertEqual(commands[0][:3], ['gh', 'release', 'download'])
        self.assertEqual(len(commands), 1)
        self.assertTrue(report['nothing_modified'])
        self.assertEqual(json.loads(report_path.read_text())['result'], 'FAIL')

    def test_ubuntu_smoke_uses_published_native_and_public_tag(self):
        # Build the new six-asset release identity without creating a release.
        self.assets = {}
        for name in smoke.expected_names('0.3.0'):
            (self.root / name).write_bytes(name.encode())
            self.assets[name] = smoke.digest(self.root / name)
        (self.root / 'SHA256SUMS').write_text(''.join(h + '  ' + n + '\n' for n, h in self.assets.items()))
        self.assets['SHA256SUMS'] = smoke.digest(self.root / 'SHA256SUMS')
        publication = self.checkout / 'publication.json'
        publication.write_text(json.dumps({'version': 2, 'status': 'PUBLISHED',
            'python_version': '0.3.0', 'platforms': {p: {} for p in smoke.PLATFORMS},
            'source_commit': self.commit, 'git_tag': self.tag,
            'repository': 'owner/repo', 'assets': self.assets}))
        native = 'mariamem-native-ubuntu24.04-x86_64.tar.gz'
        def command(argv, **kwargs):
            directory = Path(argv[argv.index('--dir') + 1])
            for name in self.assets:
                shutil.copyfile(self.root / name, directory / name)
            class Result:
                returncode, stdout, stderr = 0, '', ''
            return Result()
        def consumers(root, commit, archive, wheel, output, **kwargs):
            self.assertEqual(archive.name, native)
            self.assertEqual(wheel.name, 'mariamem-0.3.0-py3-none-linux_x86_64.whl')
            report = self.consumer(smoke.UBUNTU)
            output.write_text(json.dumps(report))
            return report
        with patch.object(smoke.subprocess, 'run', command), patch.object(smoke, 'run_consumers', consumers):
            result = smoke.smoke(self.checkout, 'owner/repo', publication, self.checkout / 'out.json', smoke.UBUNTU)
        self.assertEqual(result['result'], 'PASS')
        self.assertEqual(result['platform'], smoke.UBUNTU)


if __name__ == '__main__':
    unittest.main()
