"""Runtime source coverage checks with small source archives, no sysroot build."""
import copy
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from common import LOCK, digest
from runtime_sources import verify_runtime_sources


class RuntimeSources(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "build/downloads").mkdir(parents=True)
        self.lock = copy.deepcopy(LOCK)
        self.entries = {e["name"]: e for e in self.lock["inputs"]}
        for pin in self.lock["runtime_source_submodules_to_collect"]:
            self.write(self.entries[pin["source_input"]])
        self.llvm = self.entries["llvm-project"]

    def write(self, entry, omit=None, root=None, symlink_license=False):
        path = self.root / "build/downloads" / entry["file"]
        names = entry["license_files"] + [p + "/source.txt" for p in entry["source_directories"]]
        with tarfile.open(path, "w:gz") as tar:
            for name in names:
                if name == omit or name.startswith((omit or "not-present") + "/"):
                    continue
                member = tarfile.TarInfo((root or entry["archive_root"]) + "/" + name)
                data = b"source or license fixture\n"
                if symlink_license and name in entry["license_files"]:
                    member.type = tarfile.SYMTYPE
                    member.linkname = "missing"
                    tar.addfile(member)
                else:
                    member.size = len(data)
                    tar.addfile(member, io.BytesIO(data))
        entry["sha256"] = digest(path)

    def test_all_pins_sources_and_licenses_reported(self):
        result = verify_runtime_sources(self.root, self.lock)
        self.assertEqual(len(result), 3)
        for pin in self.lock["runtime_source_submodules_to_collect"]:
            report = result[pin["path"]]
            entry = self.entries[pin["source_input"]]
            self.assertEqual(report["revision"], pin["commit"])
            self.assertEqual(set(report["license_sha256"]), set(entry["license_files"]))
            self.assertEqual(set(report["source_directories"]), set(entry["source_directories"]))

    def test_revision_mismatch(self):
        self.llvm["revision"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "revision mismatch"):
            verify_runtime_sources(self.root, self.lock)

    def test_wrong_commit_url(self):
        self.llvm["url"] = self.llvm["url"].rsplit("/", 1)[0] + "/main"
        with self.assertRaisesRegex(ValueError, "URL/root mismatch"):
            verify_runtime_sources(self.root, self.lock)

    def test_wrong_archive_revision_root(self):
        self.write(self.llvm, root="llvm-project-wrong-revision")
        with self.assertRaisesRegex(ValueError, "root/path mismatch"):
            verify_runtime_sources(self.root, self.lock)

    def test_missing_license_even_if_archive_hash_matches(self):
        self.write(self.llvm, omit="libunwind/LICENSE.TXT")
        with self.assertRaisesRegex(ValueError, "missing runtime licenses"):
            verify_runtime_sources(self.root, self.lock)

    def test_missing_source_even_if_archive_hash_matches(self):
        self.write(self.llvm, omit="compiler-rt/lib/builtins")
        with self.assertRaisesRegex(ValueError, "missing runtime source directories"):
            verify_runtime_sources(self.root, self.lock)

    def test_hash_corruption(self):
        path = self.root / "build/downloads" / self.llvm["file"]
        path.write_bytes(path.read_bytes() + b"corrupt")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            verify_runtime_sources(self.root, self.lock)

    def test_missing_archive(self):
        (self.root / "build/downloads" / self.llvm["file"]).unlink()
        with self.assertRaises(FileNotFoundError):
            verify_runtime_sources(self.root, self.lock)

    def test_symlink_is_not_license_content(self):
        self.write(self.llvm, symlink_license=True)
        with self.assertRaisesRegex(ValueError, "invalid runtime license"):
            verify_runtime_sources(self.root, self.lock)


if __name__ == "__main__":
    unittest.main()
