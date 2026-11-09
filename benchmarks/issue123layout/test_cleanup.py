"""Exercise the actual workflow cleanup block with Go-style read-only directories."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CleanupTest(unittest.TestCase):
    def test_readonly_modules_and_missing_cache(self):
        self.assertNotEqual(os.geteuid(), 0, 'permission regression requires a non-root user')
        text = (ROOT / '.github/workflows/issue123-layout.yml').read_text()
        section = text.split('      - name: Dispose owned scratch and checksum receipts\n', 1)[1]
        block = textwrap.dedent(section.split('        run: |\n', 1)[1].split('\n      - name:', 1)[0])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # actions/setup-python provides `python`; reproduce that alias locally.
            bindir = root / 'bin'
            bindir.mkdir()
            (bindir / 'python').symlink_to(sys.executable)
            owned = root / 'build/issue123-layout'
            module = owned / 'temp/modcache/example.org/module@v1.0.0/subdir'
            module.mkdir(parents=True)
            source = module / 'source.go'
            source.write_text('package fixture\n')
            source.chmod(0o444)
            module.chmod(0o555)
            module.parent.chmod(0o555)
            evidence = owned / 'evidence'
            evidence.mkdir()
            sentinel = evidence / 'result.json'
            sentinel.write_text('{"result":"FAIL","reason":"earlier check"}\n')
            original = sentinel.read_bytes()
            decoy = root / 'unrelated-module-cache'
            decoy.mkdir()
            (decoy / 'keep').write_text('not owned by this workflow')
            old = subprocess.run(['rm', '-rf', str(owned / 'temp')], capture_output=True, text=True)
            self.assertNotEqual(old.returncode, 0)
            self.assertIn('Permission denied', old.stderr)
            env = dict(os.environ, PATH=str(bindir)+os.pathsep+os.environ['PATH'], GOMODCACHE=str(decoy), GOTOOLCHAIN='local', GOENV='off', GOWORK='off',
                       GITHUB_SHA='0f60415f3c8d3dcd8ee43a116f3d773acf38f7bf', PRIOR_JOB_STATUS='failure')
            for _ in range(2):  # Second pass covers missing/previously removed cache.
                result = subprocess.run(['bash', '-e', '-c', block], cwd=root, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse((owned / 'temp').exists())
                self.assertEqual(sentinel.read_bytes(), original)
                self.assertTrue((decoy / 'keep').exists())
                status = json.loads((evidence / 'job-status.json').read_text())
                self.assertEqual(status['status_before_cleanup'], 'failure')
                self.assertTrue(status['temp_removed'])
                self.assertIn('result.json', json.loads((evidence / 'SHA256SUMS.json').read_text()))


if __name__ == '__main__':
    unittest.main()
