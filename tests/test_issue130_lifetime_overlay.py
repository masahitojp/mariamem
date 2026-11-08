"""Source-only validation; never executes or claims native guest acceptance."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'benchmarks/spikes/issue130-public-lifetime'
spec = importlib.util.spec_from_file_location('issue130_overlay', HERE / 'overlay.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LifetimeOverlayTests(unittest.TestCase):
    def inputs(self):
        return {name: (ROOT / name).read_bytes() for name in (
            'internal/nativewire/backend.go', 'internal/nativewire/relay.go',
            'internal/nativewire/capture.go', 'internal/host/factory.go')}

    def test_overlay_is_additive_and_keeps_all_existing_test_bytes(self):
        files = self.inputs()
        files['existing_test.go'] = b'original assertions remain exact'
        original = dict(files)
        result = module.overlay(files)
        self.assertEqual(files, original)
        self.assertEqual(result['existing_test.go'], files['existing_test.go'])
        self.assertIn(b'func(h *Issue130Hooks) { r.issue130 = h }', result['internal/nativewire/backend.go'])
        self.assertIn(b'life.BeforeWorkerComplete = h.WorkerComplete', result['internal/host/factory.go'])
        relay = result['internal/nativewire/relay.go'].decode()
        self.assertLess(relay.index('h.RelayDone('), relay.index('r := s.root'))
        self.assertIn(b'stored.OwnRoot(image, r.issue130Build(r.build))', result['internal/nativewire/capture.go'])
        self.assertIn(b'func TestIssue130PublicSeparateJoins', result['issue130_native_test.go'])

    def test_changed_or_duplicate_anchors_fail_closed(self):
        for path in ('internal/nativewire/backend.go', 'internal/nativewire/relay.go', 'internal/nativewire/capture.go'):
            for raw in (b'changed source', self.inputs()[path] * 2):
                with self.subTest(path=path, duplicate=raw != b'changed source'):
                    files = self.inputs()
                    files[path] = raw
                    with self.assertRaises(ValueError):
                        module.overlay(files)

    def test_existing_fixture_is_not_silently_replaced(self):
        files = self.inputs()
        files['issue130_native_test.go'] = b'existing assertions'
        with self.assertRaises(ValueError):
            module.overlay(files)

    def test_reapplication_fails_instead_of_stacking_hooks(self):
        with self.assertRaises(ValueError):
            module.overlay(module.overlay(self.inputs()))


if __name__ == '__main__':
    unittest.main()
