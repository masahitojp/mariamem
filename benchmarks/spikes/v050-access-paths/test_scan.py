"""Negative input controls for the source-byte inventory, not runtime tests."""
import importlib.util
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("access_scan", Path(__file__).with_name("scan.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


class SourceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        for i in range(101):
            (self.source / f"f{i}.cc").write_text(f"int f{i};\n")
        self.archive = self.root / "source.tar.gz"
        with tarfile.open(self.archive, "w:gz") as t:
            t.add(self.source, arcname="fixed-source")
        self.pin = {"sha256": scan.digest(self.archive.read_bytes())}

    def test_pristine_and_registered_patch(self):
        self.assertEqual(scan.verify_archive(self.archive, self.source, self.pin), 101)
        p = self.source / "f1.cc"
        p.write_text("int patched;\n")
        with self.assertRaises(AssertionError):
            scan.verify_archive(self.archive, self.source, self.pin)
        self.assertEqual(scan.verify_archive(self.archive, self.source, self.pin,
                                            {"f1.cc": scan.digest(p.read_bytes())}), 101)

    def test_changed_archive_rejected(self):
        self.archive.write_bytes(self.archive.read_bytes() + b"unregistered")
        with self.assertRaises(AssertionError):
            scan.verify_archive(self.archive, self.source, self.pin)

    def test_unknown_source_rejected(self):
        (self.source / "extra.cc").write_text("int extra;\n")
        with self.assertRaisesRegex(AssertionError, "unregistered source"):
            scan.verify_archive(self.archive, self.source, self.pin)

    def test_writer_families_are_disjoint(self):
        entries = [fn for values in scan.FAMILIES.values() for fn in values]
        self.assertEqual(len(entries), 65)
        self.assertEqual(len(set(entries)), 65)


if __name__ == "__main__":
    unittest.main()
