"""Exact historical vectors and rejection controls for the opt-in pure resolver."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/guest-input-resolver'
spec = importlib.util.spec_from_file_location('guest_input_resolver', ROOT / 'scripts/guest_input_resolver.py')
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


class ResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = {p.relative_to(FIXTURES).as_posix(): p.read_bytes()
                        for p in FIXTURES.rglob('*') if p.is_file()}
        cls.selections = tuple(json.loads(cls.original['registry.json'])['selections'])

    def setUp(self):
        self.data = dict(self.original)
        self.registry = json.loads(self.data['registry.json'])

    def run_selection(self, key, reader=None):
        engine, profile = key.split('/')
        return resolver.resolve_inputs(encode(self.registry), engine, profile,
                                       reader or self.data.__getitem__)

    def descriptor(self, key):
        return json.loads(self.data[self.registry['selections'][key]['descriptor']['file']])

    def replace_descriptor(self, key, descriptor):
        reference = self.registry['selections'][key]['descriptor']
        self.data[reference['file']] = encode(descriptor)
        reference['sha256'] = digest(self.data[reference['file']])

    def test_three_pinned_roundtrips(self):
        for key in self.selections:
            with self.subTest(key=key):
                actual = self.run_selection(key)
                expected = json.loads(self.data[key.replace('/', '-') + '.expected.json'])
                self.assertEqual(actual['guest_input'], expected['input'])
                self.assertEqual(actual['effective_lock'], expected['lock'])
                self.assertEqual(actual['origin'], expected['origin'])
                self.assertEqual(actual['historical_prepared_pin']['source_commit'], expected['input']['source_commit'])
                self.assertEqual(actual, self.run_selection(key))

    def test_no_version_switching_mutation(self):
        before = copy.deepcopy(self.registry)
        first = self.run_selection(self.selections[0])
        first['effective_lock']['inputs'].clear()
        for key in reversed(self.selections):
            self.run_selection(key)
        self.assertEqual(self.registry, before)
        self.assertEqual(self.data, self.original)
        self.assertTrue(self.run_selection(self.selections[0])['effective_lock']['inputs'])

    def test_no_ambient_io_or_processes(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('unexpected side effect')
        with patch('builtins.open', forbidden), patch.object(io, 'open', forbidden), \
                patch.object(socket, 'socket', forbidden), patch.object(subprocess, 'Popen', forbidden):
            for key in self.selections:
                self.run_selection(key)

    def test_unknown_selection_without_reads(self):
        for engine, profile in [('13.2.0', 'native-text'), ('12.3.3', 'native-text'),
                                ('13.0.2', 'other'), ('../13.0.2', 'legacy-full')]:
            with self.subTest(engine=engine, profile=profile):
                with self.assertRaisesRegex(resolver.InputError, 'unregistered'):
                    resolver.resolve_inputs(encode(self.registry), engine, profile,
                                            lambda _: self.fail('unknown selection read data'))

    def test_descriptor_checksum(self):
        key = self.selections[0]
        path = self.registry['selections'][key]['descriptor']['file']
        self.data[path] += b' '
        with self.assertRaisesRegex(resolver.InputError, 'digest mismatch'):
            self.run_selection(key)

    def test_mixed_descriptor_selection(self):
        key = '13.0.2/native-text'
        self.replace_descriptor(key, self.descriptor('13.0.2/legacy-full'))
        with self.assertRaisesRegex(resolver.InputError, 'selection mismatch'):
            self.run_selection(key)

    def test_stage_omission_addition_reorder(self):
        key = '13.0.2/native-text'
        for mutation in ('omit', 'add', 'reorder', 'duplicate'):
            with self.subTest(mutation=mutation):
                d = self.descriptor(key)
                original = copy.deepcopy(d)
                if mutation == 'omit': d['stages'].pop()
                if mutation == 'add': d['stages'].append('unexpected-stage')
                if mutation == 'reorder': d['stages'].reverse()
                if mutation == 'duplicate': d['stages'].append(d['stages'][0])
                self.replace_descriptor(key, d)
                with self.assertRaises(resolver.InputError): self.run_selection(key)
                self.replace_descriptor(key, original)

    def test_patch_omission_addition_reorder(self):
        key = '13.0.2/native-text'
        for mutation in ('omit', 'add', 'reorder'):
            with self.subTest(mutation=mutation):
                d = self.descriptor(key)
                original = copy.deepcopy(d)
                if mutation == 'omit': d['guest_input']['patches'].pop()
                if mutation == 'add': d['guest_input']['patches'].append(copy.deepcopy(d['guest_input']['patches'][0]))
                if mutation == 'reorder': d['guest_input']['patches'].reverse()
                self.replace_descriptor(key, d)
                with self.assertRaisesRegex(resolver.InputError, 'registered input mismatch'):
                    self.run_selection(key)
                self.replace_descriptor(key, original)

    def test_patch_and_proof_byte_corruption(self):
        for key in self.selections:
            d = self.descriptor(key)
            for name, reference in d['files'].items():
                with self.subTest(selection=key, file=name):
                    original = self.data[reference['file']]
                    self.data[reference['file']] = original + b' '
                    with self.assertRaisesRegex(resolver.InputError, 'digest mismatch'):
                        self.run_selection(key)
                    self.data[reference['file']] = original

    def test_proof_cannot_be_replaced_by_new_blob_digest(self):
        key = '13.0.2/native-text'
        d = self.descriptor(key)
        ref = d['files']['tests/fixtures/prepared-param-order-functions.json']
        self.data[ref['file']] += b' '
        ref['sha256'] = digest(self.data[ref['file']])
        self.replace_descriptor(key, d)
        with self.assertRaisesRegex(resolver.InputError, 'function proof mismatch'):
            self.run_selection(key)

    def test_missing_proof(self):
        key = '13.0.2/native-text'
        d = self.descriptor(key)
        del d['files']['guest/prepared_source_patch.json']
        self.replace_descriptor(key, d)
        with self.assertRaises(resolver.InputError): self.run_selection(key)

    def test_unsafe_file_reference_before_read(self):
        key = self.selections[0]
        original = copy.deepcopy(self.registry)
        for path in ('/absolute', '../escape', 'a/../escape', 'a//b', './a', 'a\\b', 'C:drive', ''):
            with self.subTest(path=path):
                self.registry = copy.deepcopy(original)
                self.registry['selections'][key]['descriptor']['file'] = path
                with self.assertRaisesRegex(resolver.InputError, 'unsafe path'):
                    self.run_selection(key, lambda _: self.fail('unsafe path reached reader'))

    def test_unsafe_logical_patch_path(self):
        key = self.selections[0]
        d = self.descriptor(key)
        d['files']['../escape'] = next(iter(d['files'].values()))
        self.replace_descriptor(key, d)
        with self.assertRaisesRegex(resolver.InputError, 'unsafe path'): self.run_selection(key)

    def test_lock_engine_mismatch(self):
        key = '13.0.2/native-text'
        d = self.descriptor(key)
        d['engine_entry']['revision'] = '0' * 40
        self.replace_descriptor(key, d)
        with self.assertRaisesRegex(resolver.InputError, 'engine lock identity'): self.run_selection(key)

    def test_lock_order_changed(self):
        key = self.selections[0]
        d = self.descriptor(key)
        d['engine_position'] = 0
        self.replace_descriptor(key, d)
        with self.assertRaisesRegex(resolver.InputError, 'registered lock mismatch'): self.run_selection(key)

    def test_input_engine_and_profile_mismatch(self):
        key = '13.0.2/native-text'
        original = self.descriptor(key)
        for field, value in [('version', '12.3.3'), ('prepared_profile', 'legacy-full')]:
            d = copy.deepcopy(original)
            d['guest_input'][field] = value
            self.replace_descriptor(key, d)
            with self.assertRaises(resolver.InputError): self.run_selection(key)

    def test_duplicate_json_and_unknown_schema(self):
        for raw in (b'{"schema":1,"schema":1}', b'{"schema":2}', b'{"schema":true}', b'{"schema":NaN}', b'not json'):
            with self.subTest(raw=raw), self.assertRaises(resolver.InputError):
                resolver.resolve_inputs(raw, '12.3.3', 'legacy-full', self.data.__getitem__)


if __name__ == '__main__':
    unittest.main()
