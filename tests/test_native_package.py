"""Candidate-only packaging checks using tiny inert artifact fixtures."""
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import package_native as pkg


class NativePackage(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.native = self.root / "native"
        for name in ("native", "licenses", "release", "python"):
            (self.root / name).mkdir()
        for name in ("LICENSE", "NOTICE", "THIRD_PARTY_LICENSES", "licenses/example.txt"):
            (self.root / name).write_text(name)
        (self.root / "release/inputs.lock.json").write_text('{}')
        (self.root / "release/review.json").write_text('{"checks":{"guest_source":{"passed":false}}}')
        (self.root / "python/deployment_target.json").write_text('{"minimum_macos":15}')
        (self.native / "wasmer-headless").write_bytes(b"inert runtime")
        (self.native / "wasmer-headless").chmod(0o755)
        (self.native / "mariamem.wasmu").write_bytes(b"inert guest")
        (self.native / "mariamem.wasmu.json").write_bytes(pkg.encoded({
            "snapshot_version": 1, "wasm_sha256": "a" * 64,
            "module_sha256": pkg.digest(b"inert guest")}))
        self.manifest = {"version": 1, "platform": "darwin-arm64", "minimum_macos": 15,
                         "public_release_ready": True,
                         "sha256": {n: pkg.digest((self.native / n).read_bytes()) for n in pkg.ARTIFACTS}}
        self.manifest["sha256"]["mariamem-host"] = "unused"
        self.save_manifest()

    def save_manifest(self):
        (self.native / "manifest.json").write_bytes(pkg.encoded(self.manifest))

    def test_reproducible_archive_and_extracted_permissions(self):
        files = pkg.payload(self.root, self.native)
        a, b = self.root / "a.tar.gz", self.root / "b.tar.gz"
        pkg.write_archive(a, files)
        pkg.write_archive(b, files)
        self.assertEqual(a.read_bytes(), b.read_bytes())
        pkg.verify_archive(a, files)
        manifest = json.loads(files["manifest.json"])
        self.assertFalse(manifest["public_release_ready"])
        self.assertEqual(set(manifest["sha256"]), set(pkg.ARTIFACTS))
        with tarfile.open(a) as tar:
            # Only extract after exact allowlist/type/content verification above.
            tar.extractall(self.root / "extracted")
        extracted = self.root / "extracted" / pkg.NAME
        self.assertEqual((extracted / "wasmer-headless").stat().st_mode & 0o777, 0o755)
        self.assertFalse((extracted / "mariamem-host").exists())
        self.assertEqual((extracted / "NOTICE").read_bytes(), files["NOTICE"])
        self.assertFalse(json.loads(files["CANDIDATE.json"])["reviews"]["checks"]["guest_source"]["passed"])

    def test_raise_supported_floor_without_binary_changes(self):
        self.manifest['minimum_macos'] = 12
        self.save_manifest()
        files = pkg.payload(self.root, self.native)
        self.assertEqual(json.loads(files['manifest.json'])['minimum_macos'], 15)
        self.assertEqual(files['wasmer-headless'], b'inert runtime')
        self.assertEqual(files['mariamem.wasmu'], b'inert guest')

    def test_cannot_lower_input_minimum(self):
        self.manifest['minimum_macos'] = 16
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'candidate platform'):
            pkg.payload(self.root, self.native)

    def test_reject_corrupt_input(self):
        (self.native / "mariamem.wasmu").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            pkg.payload(self.root, self.native)

    def test_reject_bad_sidecar_even_with_matching_manifest_hash(self):
        name = "mariamem.wasmu.json"
        (self.native / name).write_bytes(b'{}')
        self.manifest["sha256"][name] = pkg.digest(b'{}')
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "metadata mismatch"):
            pkg.payload(self.root, self.native)

    def test_reject_nonexecutable_runtime(self):
        (self.native / "wasmer-headless").chmod(0o644)
        with self.assertRaisesRegex(ValueError, "not executable"):
            pkg.payload(self.root, self.native)

    def test_reject_symlink_input(self):
        (self.native / "mariamem.wasmu").unlink()
        (self.native / "mariamem.wasmu").symlink_to(self.root / "LICENSE")
        with self.assertRaisesRegex(ValueError, "regular file"):
            pkg.payload(self.root, self.native)

    def test_reject_changed_archive_content_and_permissions(self):
        files = pkg.payload(self.root, self.native)
        archive = self.root / "bad.tar.gz"
        changed = dict(files, NOTICE=b"changed")
        pkg.write_archive(archive, changed)
        with self.assertRaisesRegex(ValueError, "content mismatch"):
            pkg.verify_archive(archive, files)
        pkg.write_archive(archive, files)
        with tarfile.open(archive) as tar:
            entries = [(m, tar.extractfile(m).read()) for m in tar.getmembers()]
        import io
        with tarfile.open(archive, "w:gz") as tar:
            for m, data in entries:
                m.mode = 0o644
                tar.addfile(m, io.BytesIO(data))
        with self.assertRaisesRegex(ValueError, "permissions"):
            pkg.verify_archive(archive, files)


if __name__ == "__main__":
    unittest.main()
