"""Fail closed when a reused reference loses its source or content binding."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import uca_copy_reference as reference


class ReferenceTests(unittest.TestCase):
    def fixture(self, root, *, source=reference.SOURCE, checksums=True):
        archive = Path(root)/'reference.zip'
        native = b'{"semantic": "fixture"}\n'
        digest = hashlib.sha256(native).hexdigest()
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('source.json', json.dumps({'source_commit': source}))
            z.writestr('native.json', native)
            z.writestr('SHA256SUMS.json', json.dumps({'native.json': digest if checksums else 'wrong'}))
        return archive, native, digest

    def test_exact_reference(self):
        with tempfile.TemporaryDirectory() as root:
            archive, native, digest = self.fixture(root)
            with patch.multiple(reference, ZIP_SHA256=hashlib.sha256(archive.read_bytes()).hexdigest(), NATIVE_SHA256=digest):
                self.assertEqual(reference.verified_reference(archive), native)

    def test_wrong_zip(self):
        with tempfile.TemporaryDirectory() as root:
            archive, _, _ = self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'ZIP checksum'):
                reference.verified_reference(archive)

    def test_wrong_source(self):
        with tempfile.TemporaryDirectory() as root:
            archive, _, digest = self.fixture(root, source='0'*40)
            with patch.multiple(reference, ZIP_SHA256=hashlib.sha256(archive.read_bytes()).hexdigest(), NATIVE_SHA256=digest):
                with self.assertRaisesRegex(ValueError, 'source mismatch'):
                    reference.verified_reference(archive)

    def test_wrong_native_or_manifest(self):
        for manifest in (False, True):
            with self.subTest(manifest=manifest), tempfile.TemporaryDirectory() as root:
                archive, _, digest = self.fixture(root, checksums=not manifest)
                with patch.multiple(reference, ZIP_SHA256=hashlib.sha256(archive.read_bytes()).hexdigest(), NATIVE_SHA256=digest if manifest else 'wrong'):
                    with self.assertRaisesRegex(ValueError, 'native reference checksum'):
                        reference.verified_reference(archive)
