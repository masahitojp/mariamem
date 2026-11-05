"""Input packaging checks; never builds or starts a guest."""
import copy
import base64
import gzip
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT/'benchmarks/ucapreparedinput'
spec = importlib.util.spec_from_file_location('uca_input', BUNDLE/'check.py')
uca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uca)
def read_blob(path):
    return base64.b64decode(json.loads(path.read_text())['data'])

def write_blob(path, blob):
    path.write_text(json.dumps({'format':'gzip-base64-u16le','data':base64.b64encode(blob).decode()}))

EXPECTED = 'ce55cdcc72e0c0545e4f736d711b420fb3be07c72511e6ff4b142ad767b39274'

class PreparedInputTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name)
        self.bundle = self.path/'bundle'
        shutil.copytree(BUNDLE, self.bundle)
        self.manifest = json.loads((self.bundle/'input.json').read_text())

    def save(self):
        (self.bundle/'input.json').write_text(json.dumps(self.manifest))

    def test_known_input_readonly(self):
        before = {p.name: uca.digest(p.read_bytes()) for p in self.bundle.iterdir() if p.is_file()}
        header, result = uca.validate(self.bundle)
        self.assertEqual(uca.digest(header), EXPECTED)
        self.assertEqual(len(header), 5494313)
        self.assertEqual(result['guest_build'], 'NOT_RUN')
        self.assertEqual(result['source_check'], 'PINS_ONLY_NO_PRISTINE_TREE_SUPPLIED')
        self.assertEqual(before, {p.name: uca.digest(p.read_bytes()) for p in self.bundle.iterdir() if p.is_file()})

    def test_source_archive_layout_levels(self):
        original = copy.deepcopy(self.manifest)
        for key, value in [('mariadb_source_commit','0'*40), ('source_archive_sha256','0'*64), ('schema',True), ('raw_bytes_per_level',918018)]:
            with self.subTest(key=key):
                self.manifest = copy.deepcopy(original)
                self.manifest[key] = value
                self.save()
                with self.assertRaises(ValueError): uca.validate(self.bundle)
        self.manifest = original
        self.manifest['tables'][1]['level'] = 0
        self.save()
        with self.assertRaisesRegex(ValueError, 'level'): uca.validate(self.bundle)

    def test_corruption_and_rehashed_wrong_data(self):
        entry = self.manifest['tables'][0]
        path = self.bundle/entry['file']
        blob = bytearray(read_blob(path)); blob[-1] ^= 1; write_blob(path,blob)
        with self.assertRaisesRegex(ValueError, 'compressed hash'): uca.validate(self.bundle)
        raw = bytearray(gzip.decompress(read_blob(BUNDLE/entry['file']))); raw[0] ^= 1
        blob = gzip.compress(raw, mtime=0); write_blob(path,blob)
        entry['compressed_sha256'] = uca.digest(blob); entry['raw_sha256'] = uca.digest(raw); self.save()
        with self.assertRaisesRegex(ValueError, 'rendered header'): uca.validate(self.bundle)

    def test_bounded_decode_and_framing(self):
        entry = self.manifest['tables'][0]
        cases = [(gzip.compress(b'\0'*(uca.RAW_BYTES+1)), 'expanded'), (read_blob(BUNDLE/entry['file'])[:-5], 'framing')]
        for blob, message in cases:
            with self.subTest(message=message):
                write_blob(self.bundle/entry['file'],blob)
                entry['compressed_sha256'] = uca.digest(blob); self.save()
                with self.assertRaisesRegex(ValueError, message): uca.validate(self.bundle)

    def test_paths_symlinks_duplicate_fields(self):
        entry = self.manifest['tables'][0]; entry['file'] = '../input.json'; self.save()
        with self.assertRaisesRegex(ValueError, 'path'): uca.validate(self.bundle)
        entry['file'] = 'level0.u16le.json'; self.save()
        path = self.bundle/entry['file']; path.unlink(); path.symlink_to(BUNDLE/entry['file'])
        with self.assertRaisesRegex(ValueError, 'symlink'): uca.validate(self.bundle)
        (self.bundle/'input.json').write_text('{"schema":1,"schema":1}')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON'): uca.validate(self.bundle)

    def test_wrong_pristine_source(self):
        source = self.path/'source'
        for name in self.manifest['pristine_files_sha256']:
            path = source/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(b'wrong source')
        with self.assertRaisesRegex(ValueError, 'pristine source mismatch'): uca.validate(self.bundle,source=source)

    def test_cli_fresh_emit_and_readonly_compare(self):
        output = self.path/'prepared.h'
        cmd = [sys.executable,str(BUNDLE/'check.py'),'--bundle',str(self.bundle)]
        subprocess.run(cmd+['--emit-header',str(output)],check=True,stdout=subprocess.PIPE)
        self.assertEqual(uca.digest(output.read_bytes()),EXPECTED)
        subprocess.run(cmd+['--check-header',str(output)],check=True,stdout=subprocess.PIPE)
        self.assertNotEqual(subprocess.run(cmd+['--emit-header',str(output)],capture_output=True).returncode,0)
        output.write_bytes(b'user-owned output')
        self.assertNotEqual(subprocess.run(cmd+['--check-header',str(output)],capture_output=True).returncode,0)
        self.assertEqual(output.read_bytes(),b'user-owned output')


    def test_source_preparation_provenance_and_no_overwrite(self):
        sys.path.insert(0, str(ROOT/'scripts'))
        import uca_prepared
        source = self.path/'source'
        for name in self.manifest['pristine_files_sha256']:
            path = source/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode())
            self.manifest['pristine_files_sha256'][name] = uca.digest(path.read_bytes())
        unicode = source/'mysql-test/std_data/unicode/allkeys1400.txt'
        unicode.parent.mkdir(parents=True)
        unicode.write_bytes(b'unit fixture, not MariaDB semantics')
        self.manifest['unicode_input_sha256'] = uca.digest(unicode.read_bytes())
        self.save()
        # Keep product identity pins, substitute only the owned input directory.
        root = self.path/'root'
        (root/'guest').mkdir(parents=True)
        (root/'release').mkdir()
        shutil.copy2(ROOT/'guest/input.json', root/'guest/input.json')
        shutil.copy2(ROOT/'release/inputs.lock.json', root/'release/inputs.lock.json')
        target = root/uca_prepared.BUNDLE
        target.parent.mkdir(parents=True)
        shutil.copytree(self.bundle, target)
        proof = uca_prepared.prepare(root, source)
        self.assertEqual(proof['source_check'], 'PRISTINE_SOURCE_HASHES_PASS')
        self.assertEqual(proof['header_sha256'], EXPECTED)
        self.assertEqual(len(proof['input_files_sha256']), 5)
        header = source/uca_prepared.HEADER
        self.assertEqual(uca.digest(header.read_bytes()), EXPECTED)
        with self.assertRaises(FileExistsError):
            uca_prepared.prepare(root, source)
        header.unlink()
        (source/'strings/ctype-uca.c').write_bytes(b'changed source')
        with self.assertRaisesRegex(ValueError, 'pristine source mismatch'):
            uca_prepared.prepare(root, source)
        self.assertFalse(header.exists())

if __name__ == '__main__': unittest.main()
