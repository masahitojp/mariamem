"""Deterministic observer accounting; never substitutes for native acceptance."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'benchmarks/spikes/issue65-p1-settings'
spec = importlib.util.spec_from_file_location('issue129_observer', HERE / 'observe.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


def rows(duration='1234567890'):
    return [dict(case=observer.TEST + '/' + duration, phase=phase, route=route,
                 timeout_ns=duration, startup_ns='90000000017', shutdown_ns='20000000019',
                 epoch={'start': 1, 'fork': 2, 'live': 3, 'reset': 4}[phase],
                 slot=0, generation=1, live_generation=1 if phase == 'reset' else 0)
            for phase, route in sorted(observer.PHASE_ROUTES)]


def log(records, passed=True):
    return '\n'.join('    fixture.go:10: C3_SETTINGS ' + json.dumps(r) for r in records) + (
        '\n--- PASS: ' if passed else '\n--- FAIL: ') + observer.TEST + ' (1.00s)\n'


class SettingsObserverTests(unittest.TestCase):
    def test_complete_observations(self):
        for duration in observer.DURATIONS:
            self.assertEqual(observer.observations(log(rows(duration)), duration), rows(duration))

    def test_missing_duplicate_and_failed_observations_rejected(self):
        for records in [rows()[:-1], rows() + rows()[:1], rows()[:5] + rows()[:1]]:
            with self.subTest(records=records), self.assertRaises(ValueError):
                observer.observations(log(records), observer.DURATIONS[0])
        with self.assertRaises(ValueError):
            observer.observations(log(rows(), passed=False), observer.DURATIONS[0])
        with self.assertRaises(ValueError):
            observer.observations(log(rows()) + '\n--- SKIP: hidden', observer.DURATIONS[0])

    def test_wrong_values_and_runtime_identity_rejected(self):
        mutations = [('timeout_ns', '5000000000'), ('startup_ns', '120000000000'),
                     ('shutdown_ns', '30000000000'), ('case', 'wrong'),
                     ('slot', 16), ('generation', 0), ('epoch', 0), ('live_generation', 99)]
        for field, value in mutations:
            records = copy.deepcopy(rows())
            records[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                observer.observations(log(records), observer.DURATIONS[0])
        records = rows()
        for record in records:
            record['epoch'] = 1
        with self.assertRaises(ValueError):
            observer.observations(log(records), observer.DURATIONS[0])

    def test_control_needs_real_guest_assertion_after_exact_start(self):
        for duration in observer.DURATIONS:
            start = [r for r in rows(duration) if r['phase'] == 'start']
            output = log(start, passed=False) + f'exact guest timeout phase=fork route=tcp: got 5000000000 want {duration}'
            self.assertTrue(observer.control_detected(SimpleNamespace(returncode=1, stdout=output), duration))
            for bad in [output.replace('5000000000', '5000000001'), output + '\n[build failed]',
                        output + '\npanic: test timed out', output.replace('phase=fork', 'phase=start'),
                        output.replace('--- FAIL:', '--- PASS:')]:
                self.assertFalse(observer.control_detected(SimpleNamespace(returncode=1, stdout=bad), duration))
            self.assertFalse(observer.control_detected(SimpleNamespace(returncode=0, stdout=output), duration))
            self.assertFalse(observer.control_detected(SimpleNamespace(returncode=1, stdout='compile error'), duration))

    def test_overlay_additive_and_control_keeps_start(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            product = directory / 'product'
            backend = product / 'internal/nativewire/backend.go'
            backend.parent.mkdir(parents=True)
            original = (ROOT / 'internal/nativewire/backend.go').read_bytes()
            backend.write_bytes(original)
            positive = json.loads(observer.overlay(product, directory).read_text())['Replace']
            self.assertEqual(len(positive), 3)
            for path, fixture in positive.items():
                self.assertFalse(Path(path).exists())
                self.assertTrue(Path(fixture).is_file())
            negative = json.loads(observer.overlay(product, directory, control=True).read_text())['Replace']
            self.assertEqual(len(negative), 4)
            mutated = Path(negative[str(backend)]).read_text()
            self.assertIn('len(cfg.Restore) != 0', mutated)
            self.assertIn('5000*time.Millisecond', mutated)
            self.assertEqual(backend.read_bytes(), original)
            observer_file = product / 'c3_settings_test.go'
            observer_file.write_text('unique caller content')
            with self.assertRaises(ValueError):
                observer.overlay(product, directory)
            self.assertEqual(observer_file.read_text(), 'unique caller content')

    def test_mutation_preimage_is_exact(self):
        for source in ['', 'limit: limit, limit: limit,']:
            with self.assertRaises(ValueError):
                observer.fixed5000(source)


class IntegratedReceiptTests(unittest.TestCase):
    def receipts(self):
        base = dict(contract='issue65-public-unqualified', host_source_commit='a' * 40,
                    guest_sha256='b' * 64, guest_origin_source_commit='c' * 40,
                    runtime_installer_source_commit='c' * 40, source_inventory={'old': 'oldhash'})
        derived = dict(base, contract='issue130-public-lifetime-UNEXECUTED',
                       source_inventory={'old': 'newhash', 'fixture': 'fixturehash'},
                       input_source_inventory=base['source_inventory'],
                       input_receipt_sha256='d' * 64, observer_source_commit='e' * 40,
                       runtime_executed=False)
        return base, derived

    def test_derived_receipt_preserves_original_producer_and_observer(self):
        base, derived = self.receipts()
        original = copy.deepcopy((base, derived))
        chain = observer.receipt_chain(derived, base['host_source_commit'], base['guest_sha256'],
                                       derived['source_inventory'], base=base, base_sha='d' * 64)
        self.assertEqual(chain['lifetime_observer_source_commit'], 'e' * 40)
        self.assertEqual(chain['base_source_receipt_sha256'], 'd' * 64)
        self.assertEqual((base, derived), original)
        observer.receipt_chain(base, base['host_source_commit'], base['guest_sha256'], base['source_inventory'])

    def test_spoofed_or_missing_receipt_chain_rejected(self):
        base, derived = self.receipts()
        for field, value in [('host_source_commit', 'f' * 40), ('guest_sha256', 'f' * 64),
                             ('guest_origin_source_commit', 'f' * 40),
                             ('runtime_installer_source_commit', 'f' * 40),
                             ('input_source_inventory', {}), ('input_receipt_sha256', 'f' * 64),
                             ('runtime_executed', True), ('observer_source_commit', 'missing'),
                             ('contract', 'issue65-public-unqualified')]:
            bad = dict(derived, **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                observer.receipt_chain(bad, base['host_source_commit'], base['guest_sha256'],
                                       derived['source_inventory'], base=base, base_sha='d' * 64)
        with self.assertRaises(ValueError):
            observer.receipt_chain(derived, base['host_source_commit'], base['guest_sha256'],
                                   derived['source_inventory'])
        with self.assertRaises(ValueError):
            observer.receipt_chain(derived, base['host_source_commit'], base['guest_sha256'],
                                   {}, base=base, base_sha='d' * 64)

    def test_settings_overlay_and_control_keep_lifetime_source(self):
        path = ROOT / 'benchmarks/spikes/issue130-public-lifetime/overlay.py'
        spec = importlib.util.spec_from_file_location('integrated_lifetime', path)
        lifetime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lifetime)
        names = ('internal/nativewire/backend.go', 'internal/nativewire/relay.go',
                 'internal/nativewire/capture.go', 'internal/host/factory.go')
        source = {name: (ROOT / name).read_bytes() for name in names}
        combined = lifetime.overlay(source)  # in memory only; no product staged
        self.assertFalse(set(observer.FIXTURES) & set(combined))
        self.assertFalse(set(observer.UNITS) & set(combined))
        backend = combined['internal/nativewire/backend.go'].decode()
        mutated = observer.fixed5000(backend)
        self.assertIn('ConfigureIssue130', mutated)
        self.assertIn('ForceIdleState', mutated)
        self.assertEqual(mutated.replace(
            'limit: func() uint64 { if len(cfg.Restore) != 0 { return uint64(5000*time.Millisecond) }; return limit }(),',
            'limit: limit,', 1), backend)
        for name in names:
            self.assertEqual(source[name], (ROOT / name).read_bytes())


if __name__ == '__main__':
    unittest.main()
