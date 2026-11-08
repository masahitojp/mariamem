"""Read-only exact-candidate preflight; no artifact authentication or staging."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = '8c8b5f1c09765c9fb51c2b640ed2fc32d759fbe3'
GUEST = '873c9daf38f6e7f5005dbdbdf8e920b396fe5591ab74bfedcad37b436c50d3dc'
BINDING = 'benchmarks/spikes/issue127-bootstrap/binding/identity.json'


class PublicRebindingPreflight(unittest.TestCase):
    def test_corrected_guest_evidence_is_not_fresh_c2_acceptance(self):
        guest = json.loads((ROOT / 'benchmarks/spikes/issue127-bootstrap/evidence/guest.json').read_text())
        self.assertEqual(guest['source_commit'], ORIGIN)
        self.assertEqual(guest['source_identity']['commit'], ORIGIN)
        self.assertEqual(guest['guest_sha256'], GUEST)
        self.assertIs(guest['fresh_canonical_builder_success'], False)
        self.assertIn('incremental', guest['build_method'])
        self.assertEqual(subprocess.check_output(['git', 'cat-file', '-t', ORIGIN], cwd=ROOT, text=True).strip(), 'commit')
        # The source patch authenticated by the historical producer remains exact.
        raw = subprocess.check_output(['git', 'show', ORIGIN + ':guest/experimental.patch'], cwd=ROOT)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), guest['source_identity']['files_sha256']['guest/experimental.patch'])
        self.assertEqual(raw, (ROOT / 'guest/experimental.patch').read_bytes())

    def test_new_binding_is_explicit_and_old_c2_mode_stays_fixed(self):
        raw = (ROOT / BINDING).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), '35fb98fda9d89c0a6010b32f6be63446d2684b73d69837322fd905e3aeb478f0')
        binding = json.loads(raw)
        self.assertEqual(binding['guest_sha256'], GUEST)
        self.assertEqual(binding['ABI_offsets'], {'start_args.pthread': 16, 'pthread.map_base': 40, 'pthread.map_size': 44})
        self.assertEqual([v['function'] for v in binding['functions'].values() if v['role'] == 'entry'], ['Fn520'])
        tree = ast.parse((ROOT / 'benchmarks/spikes/issue65-p1-public/assemble.py').read_text())
        pins = {n.targets[0].id: n.value.value for n in tree.body if isinstance(n, ast.Assign)
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id in {'ORIGIN', 'GUEST'}}
        self.assertEqual(pins['ORIGIN'], 'be244a0bdb510a22417241c2aa2f76a9093aac1b')
        self.assertEqual(pins['GUEST'], binding['previous_experimental_guest_sha256'])
        self.assertNotEqual(pins['GUEST'], GUEST)
        lifetime = (ROOT / 'benchmarks/spikes/issue130-public-lifetime/overlay.py').read_bytes()
        self.assertEqual(lifetime, subprocess.check_output(['git', 'show', '846e1811:benchmarks/spikes/issue130-public-lifetime/overlay.py'], cwd=ROOT))

    def test_integrated_origin_cannot_be_silently_used_as_guest_origin(self):
        changed = set(subprocess.check_output(['git', 'diff', '--name-only', ORIGIN, 'HEAD'], cwd=ROOT, text=True).splitlines())
        allowed = {'scripts/dev_guest.py', 'scripts/generate_runtime.py', 'scripts/regenerate_release_guest.py'}
        blocked = {n for n in changed if n not in allowed and not n.startswith(('docs/', 'tests/'))}
        # Match the existing verifier's narrow cross-commit policy; do not widen it.
        self.assertTrue(blocked)
        self.assertTrue(any(n.startswith('benchmarks/') for n in blocked))
        for name in ('scripts/dev_guest.py', 'scripts/generate_runtime.py'):
            self.assertEqual((ROOT / name).read_bytes(), subprocess.check_output(['git', 'show', ORIGIN + ':' + name], cwd=ROOT))
        for name in ('backend.go', 'relay.go', 'capture.go'):
            path = 'internal/nativewire/' + name
            self.assertEqual((ROOT / path).read_bytes(), subprocess.check_output(['git', 'show', 'a5ee1ed9:' + path], cwd=ROOT))


if __name__ == '__main__':
    unittest.main()
