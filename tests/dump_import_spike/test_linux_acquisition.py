"""Identity mutation controls: every selected binary and source must match."""
import copy
import ast
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import linux_acquisition as acquisition
from linux_acquisition import PIN, architecture, validate


class AcquisitionGuards(unittest.TestCase):
    def setUp(self):
        self.pin = json.loads(PIN.read_text())
        self.source = self.pin['basis']['source_commit']
        self.observed = {key: copy.deepcopy(self.pin[key]) for key in
                         ['host', 'image_ref', 'image', 'programs', 'startup_query']}
        self.observed['container_image'] = self.pin['image']['id']
        self.observed['source'] = {'object_type': 'commit', 'object_sha': self.source,
                                   'source_commit': self.source}

    def test_exact_receipt(self):
        validate(self.observed, self.pin, self.source)

    def test_each_program_field_must_match(self):
        for name in self.pin['programs']:
            for field, wrong in [('path', '/tmp/other'), ('version', '12.3.30'),
                                 ('sha256', '0'*64), ('architecture', {'machine': 183})]:
                with self.subTest(program=name, field=field):
                    mutant = copy.deepcopy(self.observed)
                    mutant['programs'][name][field] = wrong
                    with self.assertRaisesRegex(ValueError, name+' identity mismatch'):
                        validate(mutant, self.pin, self.source)

    def test_missing_or_extra_program(self):
        for extra in [False, True]:
            mutant = copy.deepcopy(self.observed)
            if extra:
                mutant['programs']['mysql'] = {}
            else:
                del mutant['programs']['mariadb-dump']
            with self.assertRaisesRegex(ValueError, 'program inventory'):
                validate(mutant, self.pin, self.source)

    def test_validate_rejects_forged_source_receipt_and_abbreviation(self):
        for key, wrong in [('source_commit', '1'*40), ('object_sha', '2'*40), ('object_type', 'tag')]:
            mutant = copy.deepcopy(self.observed)
            mutant['source'][key] = wrong
            with self.subTest(field=key), self.assertRaisesRegex(ValueError, 'source identity'):
                validate(mutant, self.pin, self.source)
        with self.assertRaisesRegex(ValueError, 'full commit SHA'):
            validate(self.observed, self.pin, self.source[:7])

    def test_host_image_and_startup_mismatches(self):
        for field, wrong in [('host', {'system': 'Linux', 'machine': 'aarch64'}),
                             ('image_ref', 'mariadb:12.3'), ('image', {'architecture': 'arm64'}),
                             ('container_image', 'sha256:'+'0'*64), ('startup_query', '12.3.30\tx86_64\n1\n')]:
            mutant = copy.deepcopy(self.observed)
            mutant[field] = wrong
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(mutant, self.pin, self.source)

    def test_each_executable_architecture_is_read_from_elf_header(self):
        header = bytearray(20)
        header[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', header, 18, 62)
        self.assertEqual(architecture(header), self.pin['programs']['mariadbd']['architecture'])
        struct.pack_into('<H', header, 18, 183)
        for name in self.pin['programs']:
            mutant = copy.deepcopy(self.observed)
            mutant['programs'][name]['architecture'] = architecture(header)
            with self.subTest(program=name), self.assertRaises(ValueError):
                validate(mutant, self.pin, self.source)
        for invalid in [b'', b'not ELF', b'\x7fELF\x03\x01'+bytes(14)]:
            with self.assertRaises(ValueError):
                architecture(invalid)


class ActualSourceIdentity(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.git('init', '-q')
        (self.root/'tracked.txt').write_text('initial\n')
        self.git('add', 'tracked.txt')
        self.git('commit', '-qm', 'initial')
        self.commit = self.git('rev-parse', 'HEAD').strip()
        self.patch = patch.object(acquisition, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def git(self, *arguments):
        return subprocess.check_output(['git', '-c', 'user.name=Guard test',
            '-c', 'user.email=guard@example.invalid', '-c', 'commit.gpgsign=false',
            '-c', 'core.hooksPath=/dev/null', *arguments], cwd=self.root, text=True)

    def test_clean_checkout(self):
        self.assertEqual(acquisition.source_identity(self.commit)['source_commit'], self.commit)

    def test_dirty_tracked_tree(self):
        (self.root/'tracked.txt').write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'dirty'):
            acquisition.source_identity(self.commit)

    def test_dirty_untracked_tree(self):
        (self.root/'untracked.txt').write_text('new\n')
        with self.assertRaisesRegex(ValueError, 'dirty'):
            acquisition.source_identity(self.commit)

    def test_head_mismatch(self):
        self.git('commit', '--allow-empty', '-qm', 'other source')
        with self.assertRaisesRegex(ValueError, 'checkout source_commit differs'):
            acquisition.source_identity(self.commit)

    def test_actual_annotated_tag_object(self):
        self.git('tag', '-a', 'guard-test', '-m', 'annotated source tag')
        tag_object_sha = self.git('rev-parse', 'guard-test').strip()
        self.assertNotEqual(tag_object_sha, self.commit)
        with self.assertRaisesRegex(ValueError, 'got tag object'):
            acquisition.source_identity(tag_object_sha)

    def test_abbreviated_source(self):
        with self.assertRaisesRegex(ValueError, 'full 40-character SHA'):
            acquisition.source_identity(self.commit[:7])


class FakeDocker:
    """Subprocess-boundary fixture, not native execution evidence."""
    def __init__(self):
        self.pin = json.loads(PIN.read_text())
        self.binaries = {}
        for name in self.pin['programs']:
            header = bytearray(20)
            header[:6] = b'\x7fELF\x02\x01'
            struct.pack_into('<H', header, 18, 62)
            self.binaries[name] = bytes(header)+name.encode()
            self.pin['programs'][name]['sha256'] = hashlib.sha256(self.binaries[name]).hexdigest()
        self.image = {'Id': self.pin['image']['id'], 'Os': 'linux', 'Architecture': 'amd64',
                      'RepoDigests': [self.pin['image_ref']]}
        self.container = {'Image': self.pin['image']['id']}
        self.startup = self.pin['startup_query'].encode()
        self.login = b'root@localhost\troot@%\n'
        self.metadata = acquisition.ROUTINE_METADATA.encode()
        self.results = b'17\n19\n'
        self.dump = (b'CREATE DEFINER=`root`@`localhost` FUNCTION `probe_function`() RETURNS INT RETURN 19;\n'
                     b'CREATE DEFINER=`root`@`localhost` PROCEDURE `probe_procedure`() SELECT 17;\n')
        self.dump_error = False
        self.schema_exists = False
        self.calls = []

    def command(self, args):
        self.calls.append(args)
        if args[:3] == ['docker', 'image', 'inspect']:
            return json.dumps([self.image]).encode()
        if args[:2] == ['docker', 'inspect']:
            return json.dumps([self.container]).encode()
        if args[:3] != ['docker', 'exec', 'container']:
            raise AssertionError('unexpected command '+repr(args))
        program = args[3]
        if program == 'sh':
            return (self.pin['programs'][args[-1]]['path']+'\n').encode()
        if program == 'cat':
            return self.binaries[Path(args[4]).name]
        if '--version' in args:
            return (self.pin['programs'][program]['version']+'\n').encode()
        if '--help' in args:
            return b'fixture native help\n'
        if program == 'mariadb-dump':
            if self.dump_error:
                raise subprocess.CalledProcessError(2, args, stderr=b'synthetic TCP dump failure')
            return self.dump
        sql = next((x.split('=', 1)[1] for x in args if x.startswith('--execute=')), None)
        if sql is None:
            raise AssertionError('missing SQL command')
        if '--protocol=tcp' not in args:
            return self.startup
        if sql.startswith('SELECT USER()'):
            return self.login
        if sql.startswith('SELECT COUNT(*)'):
            return b'1\n' if self.schema_exists else b'0\n'
        if sql.startswith('CREATE DATABASE'):
            self.schema_exists = True
            return b''
        if 'FROM information_schema.routines' in sql:
            return self.metadata
        if sql.startswith('CALL '):
            return self.results
        if sql.startswith('DROP DATABASE'):
            self.schema_exists = False
            return b''
        raise AssertionError('unexpected SQL '+sql)

    def run(self, args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout=self.command(args), stderr=b'')


class CaptureBoundary(unittest.TestCase):
    def setUp(self):
        self.fake = FakeDocker()
        self.source = self.fake.pin['basis']['source_commit']
        self.identity = {'object_type': 'commit', 'object_sha': self.source, 'source_commit': self.source}
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.output = Path(self.scratch.name)

    def capture(self, identities=None):
        with patch.object(acquisition, 'source_identity', side_effect=identities or [self.identity, self.identity]), \
             patch.object(acquisition.platform, 'system', return_value='Linux'), \
             patch.object(acquisition.platform, 'machine', return_value='x86_64'), \
             patch.object(acquisition.subprocess, 'run', side_effect=self.fake.run):
            return acquisition.capture('container', self.source, self.fake.pin, self.output)

    def test_capture_including_tcp_probe_and_cleanup(self):
        observed = self.capture()
        self.assertEqual(observed['producer_probe']['result'], 'PASS')
        self.assertFalse(self.fake.schema_exists)
        self.assertTrue((self.output/'observed.json').exists())

    def test_capture_rejects_actual_inspect_ref_mutation(self):
        self.fake.image['RepoDigests'] = ['mariadb:12.3']
        with self.assertRaisesRegex(ValueError, 'does not bind pinned manifest'):
            self.capture()
        self.assertFalse(any('--protocol=tcp' in a for a in self.fake.calls))

    def test_capture_rejects_actual_container_image_mutation(self):
        self.fake.container['Image'] = 'sha256:'+'0'*64
        with self.assertRaisesRegex(ValueError, 'container image mismatch'):
            self.capture()
        self.assertFalse(any('--protocol=tcp' in a for a in self.fake.calls))

    def test_capture_rejects_actual_startup_mutation(self):
        self.fake.startup = b'12.3.30\tx86_64\nroot\tlocalhost\n1\n'
        with self.assertRaisesRegex(ValueError, 'startup_query mismatch'):
            self.capture()
        self.assertFalse(any('--protocol=tcp' in a for a in self.fake.calls))

    def test_capture_exec_failure_propagates(self):
        with patch.object(acquisition, 'source_identity', return_value=self.identity), \
             patch.object(acquisition.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['docker', 'exec'])):
            with self.assertRaises(subprocess.CalledProcessError):
                acquisition.capture('container', self.source, self.fake.pin, self.output)

    def test_capture_rechecks_source_after_probe(self):
        changed = dict(self.identity, source_commit='1'*40)
        with self.assertRaisesRegex(ValueError, 'source changed during acquisition'):
            self.capture([self.identity, changed])
        self.assertFalse(self.fake.schema_exists)


class TCPProducerProbe(unittest.TestCase):
    def setUp(self):
        self.fake = FakeDocker()
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.output = Path(self.scratch.name)

    def probe(self):
        return acquisition.producer_probe('container', self.fake.command, self.output)

    def test_tcp_login_and_definer_are_distinct_and_exact_options_match_producer(self):
        report = self.probe()
        self.assertEqual(report['tcp_login'][1], 'root@%')
        self.assertEqual(report['routine_metadata'], acquisition.ROUTINE_METADATA)
        tree = ast.parse(Path(__file__).with_name('producer.py').read_text())
        original = next(ast.literal_eval(n.value) for n in tree.body
                        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'OPTIONS' for t in n.targets))
        self.assertEqual(report['dump_argv'][4:-1], original[:-1])
        self.assertEqual(report['schema_count_after'], '0\n')
        for args in self.fake.calls:
            self.assertIn('--protocol=tcp', args)
            self.assertIn('--host=127.0.0.1', args)
            self.assertIn('--user=root', args)

    def test_wrong_tcp_user_rejected_before_schema_change(self):
        self.fake.login = b'other@localhost\tother@%\n'
        with self.assertRaisesRegex(ValueError, 'authenticate as root'):
            self.probe()
        self.assertFalse(any('--execute=CREATE DATABASE' in x for a in self.fake.calls for x in a))

    def test_existing_schema_is_preserved(self):
        self.fake.schema_exists = True
        with self.assertRaisesRegex(ValueError, 'schema already exists'):
            self.probe()
        self.assertTrue(self.fake.schema_exists)
        self.assertFalse(any(x.startswith('--execute=DROP DATABASE') for a in self.fake.calls for x in a))

    def test_definer_and_security_mutations_reject_and_cleanup(self):
        for before, after in [(b'root@localhost', b'other@localhost'), (b'DEFINER', b'INVOKER')]:
            with self.subTest(mutation=after):
                self.fake.metadata = acquisition.ROUTINE_METADATA.encode().replace(before, after)
                with self.assertRaisesRegex(ValueError, 'DEFINER/SQL SECURITY mismatch'):
                    self.probe()
                self.assertFalse(self.fake.schema_exists)

    def test_bad_routine_result_rejects_and_cleans_up(self):
        self.fake.results = b'17\n20\n'
        with self.assertRaisesRegex(ValueError, 'routine execution mismatch'):
            self.probe()
        self.assertFalse(self.fake.schema_exists)

    def test_dump_connection_failure_propagates_and_cleans_up(self):
        self.fake.dump_error = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.probe()
        self.assertFalse(self.fake.schema_exists)
        self.assertEqual((self.output/'producer-probe.stderr.txt').read_bytes(), b'synthetic TCP dump failure')
        self.assertEqual(json.loads((self.output/'producer-probe.json').read_text())['result'], 'FAIL')

    def test_dump_missing_definer_routine_rejects_and_cleans_up(self):
        self.fake.dump = b'-- no routines\n'
        with self.assertRaisesRegex(ValueError, 'omitted selected definer'):
            self.probe()
        self.assertFalse(self.fake.schema_exists)


if __name__ == '__main__':
    unittest.main()
