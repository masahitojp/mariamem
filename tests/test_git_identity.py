"""Real Git objects: identity checks, no network or runtime builds."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from git_identity import inspect_ref, read_release_pin, ReleasePin, require_commit, verify_release_pin


class GitIdentityTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git('init', '-q')
        (self.root / 'source').write_text('released\n')
        self.git('add', 'source')
        self.git('commit', '-qm', 'released')
        self.commit = self.git('rev-parse', 'HEAD')
        self.git('tag', '-a', 'v0.4.3', '-m', 'published')
        self.tag = self.git('rev-parse', 'refs/tags/v0.4.3')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root),
            '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
            '-c', 'commit.gpgsign=false', '-c', 'tag.gpgsign=false', *args], text=True).strip()

    def test_annotated_tag_inspection_separates_object_from_source(self):
        identity = inspect_ref(self.root, 'v0.4.3')
        self.assertEqual(identity.object_type, 'tag')
        self.assertEqual(identity.object_sha, self.tag)
        self.assertEqual(identity.source_commit, self.commit)
        self.assertNotEqual(identity.object_sha, identity.source_commit)

    def test_exact_commit_gate_rejects_a_full_tag_sha(self):
        self.assertEqual(require_commit(self.root, self.commit).source_commit, self.commit)
        with self.assertRaisesRegex(ValueError, 'expected commit SHA; got tag object'):
            require_commit(self.root, self.tag)

    def test_lightweight_tag_inspects_as_commit_but_name_is_not_exact_sha(self):
        self.git('tag', 'lightweight')
        self.assertEqual(inspect_ref(self.root, 'lightweight').object_type, 'commit')
        with self.assertRaisesRegex(ValueError, 'full 40-character'):
            require_commit(self.root, 'lightweight')

    def test_blob_and_tree_are_not_source_commits(self):
        for ref in ('HEAD^{tree}', 'HEAD:source'):
            with self.subTest(ref=ref), self.assertRaisesRegex(ValueError, 'expected source commit or tag'):
                inspect_ref(self.root, ref)

    def test_release_pin_accepts_exact_annotated_object_and_commit(self):
        pin = ReleasePin('v0.4.3', self.tag, self.commit)
        self.assertEqual(verify_release_pin(self.root, pin).source_commit, self.commit)

    def test_valid_commit_of_another_generation_is_rejected(self):
        (self.root / 'source').write_text('later\n')
        self.git('commit', '-qam', 'later')
        pin = ReleasePin('v0.4.3', self.tag, self.git('rev-parse', 'HEAD'))
        with self.assertRaisesRegex(ValueError, 'pinned release commit'):
            verify_release_pin(self.root, pin)

    def test_correct_target_under_wrong_release_name_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'tag name'):
            verify_release_pin(self.root, ReleasePin('v0.4.4', self.tag, self.commit))

    def test_swapped_and_duplicated_identity_fields_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'must be distinct'):
            ReleasePin('v0.4.3', self.tag, self.tag)
        with self.assertRaisesRegex(ValueError, 'annotated tag object'):
            verify_release_pin(self.root, ReleasePin('v0.4.3', self.commit, self.tag))

    def test_read_release_record_rejects_ambiguous_or_invalid_schema(self):
        path = self.root / 'pin.json'
        good = dict(version=1, release_tag='v0.4.3', tag_object_sha=self.tag, source_commit=self.commit)
        path.write_text(json.dumps(good))
        self.assertEqual(read_release_pin(path), ReleasePin('v0.4.3', self.tag, self.commit))
        for bad in ({**good, 'version':True}, {**good, 'sha':self.tag},
                    {key:value for key,value in good.items() if key!='source_commit'},
                    {**good, 'source_commit':self.commit[:7]}):
            with self.subTest(pin=bad):
                path.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    read_release_pin(path)

    def test_cli_failure_does_not_write_verified_output(self):
        pin = self.root / 'pin.json'
        pin.write_text(json.dumps(dict(version=1, release_tag='v0.4.4',
                                      tag_object_sha=self.tag, source_commit=self.commit)))
        output = self.root / 'verified.json'
        result = subprocess.run([sys.executable, str(SCRIPTS/'git_identity.py'),
            '--root', str(self.root), 'verify-release', '--pin', str(pin), '--output', str(output)],
            text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('tag name', result.stderr)
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
