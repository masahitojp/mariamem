"""Identity mutation controls: every selected binary and source must match."""
import copy
import json
import struct
import unittest

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

    def test_source_identity_rejects_other_commit_tag_and_abbreviation(self):
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


if __name__ == '__main__':
    unittest.main()
