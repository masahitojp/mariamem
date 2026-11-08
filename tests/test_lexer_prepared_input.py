"""Deterministic source input guards; no guest build or runtime."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import lexer_prepared as lexer


class LexerInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for path in [lexer.BUNDLE, 'guest']:
            (self.root / path).mkdir(parents=True)
        shutil.copytree(ROOT / lexer.BUNDLE, self.root / lexer.BUNDLE, dirs_exist_ok=True)
        (self.root / 'scripts').mkdir()
        shutil.copy2(ROOT / 'scripts/lexer_prepared.py', self.root / 'scripts/lexer_prepared.py')
        shutil.copy2(ROOT / 'guest/input.json', self.root / 'guest/input.json')

    def test_header_exact_and_readonly(self):
        header, record = lexer.validate(self.root)
        self.assertEqual(hashlib.sha256(header).hexdigest(), '72b3b0a05ee156835d343ad4f57cdb484b3d891a3cf17b7ff854a3b86c7bf7c9')
        self.assertEqual(header.count(b'case '), 638)
        self.assertEqual(record['numeric_bytes'], 14336)
        self.assertEqual((header, record), lexer.validate(self.root))
        lexer.verify_record(self.root, record)
        with self.assertRaises(ValueError):
            lexer.verify_record(self.root, dict(record, descriptors=637))

    def test_input_wrapper_and_source_mutations_rejected(self):
        for name in ['input.json', 'wrapper.c.inc']:
            path = self.root / lexer.BUNDLE / name
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            with self.assertRaises(ValueError):
                lexer.validate(self.root)
            path.write_bytes(original)
        path = self.root / 'guest/input.json'
        value = json.loads(path.read_text()); value['source_commit'] = '0' * 40
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'source mismatch'):
            lexer.validate(self.root)

    def test_pristine_guard_and_no_overwrite(self):
        source = self.root / 'source'
        (source / 'mysys').mkdir(parents=True)
        (source / 'mysys/charset.c').write_text('wrong source')
        with self.assertRaisesRegex(ValueError, 'pristine source'):
            lexer.prepare(self.root, source)
        self.assertFalse((source / lexer.HEADER).exists())


if __name__ == '__main__':
    unittest.main()
