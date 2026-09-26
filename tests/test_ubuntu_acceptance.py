"""Exact consumer inputs must fail before any runtime execution on mismatch."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from common import digest
from ubuntu_product_acceptance import validate_inputs


class UbuntuAcceptanceInputs(unittest.TestCase):
    def test_exact_inputs_and_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'native.tar.gz'
            wheel = Path(directory) / 'package.whl'
            archive.write_bytes(b'native')
            wheel.write_bytes(b'wheel')
            args = (archive, digest(archive), wheel, digest(wheel), 'a' * 40)
            validate_inputs(*args)
            with self.assertRaisesRegex(ValueError, 'exact source commit'):
                validate_inputs(*args[:-1], 'main')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                validate_inputs(archive, 'b' * 64, wheel, digest(wheel), 'a' * 40)
            wheel.write_bytes(b'mutated')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                validate_inputs(*args)
