"""Guest provenance consistency tests with small inert source fixtures."""
import copy
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from common import ROOT, LOCK, digest
from verify_guest_provenance import EVIDENCE, MAJOR, inventory_digest, read_inventory, verify_evidence, verify_inventory


class Provenance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "release").mkdir()
        (self.root / "release/review.json").write_text(json.dumps({
            "checks": {"guest_source": {"passed": True, "evidence": EVIDENCE}}}))
        (self.root / "build/downloads").mkdir(parents=True)
        self.lock = copy.deepcopy(LOCK)
        self.evidence = json.loads((ROOT / EVIDENCE).read_text())
        for entry in self.lock["inputs"]:
            if entry["name"] not in self.evidence["source_archives"]:
                continue
            recorded = self.evidence["source_archives"][entry["name"]]
            archive = self.root / "build/downloads" / entry["file"]
            self.archive(archive, recorded.get("revision", "unused"))
            entry["sha256"] = recorded["sha256"] = digest(archive)
        self.records = {"guest-build.json": copy.deepcopy(self.evidence["guest_build"]),
                        "prepared-source.json": {"modified_files": copy.deepcopy(self.evidence["modified_guest_files"])}}
        self.save()

    def archive(self, path, revision):
        with tarfile.open(path, "w:gz", format=tarfile.PAX_FORMAT, pax_headers={"comment": revision}) as tar:
            member = tarfile.TarInfo("fixture/source.c")
            member.size = 1
            tar.addfile(member, io.BytesIO(b"x"))

    def save(self):
        (self.root / EVIDENCE).write_text(json.dumps(self.evidence))

    def verify(self):
        return verify_evidence(self.root, self.lock, self.records)

    def test_source_and_exact_artifact_binding(self):
        result = self.verify()
        self.assertEqual(result["module_sha256"], self.evidence["guest_build"]["module_sha256"])
        self.assertEqual(result["sha256"], digest(self.root / EVIDENCE))

    def test_reject_unreviewed_guest(self):
        self.records["guest-build.json"]["module_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "reviewed artifact"):
            self.verify()

    def test_reject_approval_without_evidence_reference(self):
        (self.root / "release/review.json").write_text(json.dumps({
            "checks": {"guest_source": {"passed": True, "evidence": None}}}))
        with self.assertRaisesRegex(ValueError, "reference provenance"):
            self.verify()

    def test_reject_unreviewed_source_overlay(self):
        self.records["prepared-source.json"]["modified_files"]["wasm/resident.inc"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source inputs"):
            self.verify()

    def test_reject_wrong_source_commit_even_if_archive_hash_updated(self):
        entry = next(e for e in self.lock["inputs"] if e["name"] == "wasix-libc")
        archive = self.root / "build/downloads" / entry["file"]
        self.archive(archive, "0" * 40)
        entry["sha256"] = self.evidence["source_archives"]["wasix-libc"]["sha256"] = digest(archive)
        self.save()
        with self.assertRaisesRegex(ValueError, "PAX commit"):
            self.verify()

    def test_reject_nonzero_comparison(self):
        self.evidence["sysroot"]["comparison"]["changed"] = 1
        self.save()
        with self.assertRaisesRegex(ValueError, "comparison did not pass"):
            self.verify()

    def test_not_binary_release_approval(self):
        self.evidence["binary_release_ready"] = True
        self.save()
        with self.assertRaisesRegex(ValueError, "scope"):
            self.verify()

    def test_inventory_includes_symlink_target(self):
        inventory = {"lib/wasm32-wasi/" + name: ["file", "a" * 64] for name in MAJOR}
        inventory["include/link"] = ["symlink", "header.h"]
        e = copy.deepcopy(self.evidence)
        e["sysroot"]["major_library_sha256"] = {name: "a" * 64 for name in MAJOR}
        e["sysroot"]["comparison"].update(entries=len(inventory), inventory_sha256=inventory_digest(inventory))
        verify_inventory(inventory, e)
        inventory["include/link"][1] = "different.h"
        with self.assertRaisesRegex(ValueError, "inventory mismatch"):
            verify_inventory(inventory, e)

    def test_archive_inventory(self):
        archive = self.root / "sysroot.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            member = tarfile.TarInfo("prefix/lib/file")
            member.size = 1
            tar.addfile(member, io.BytesIO(b"x"))
            link = tarfile.TarInfo("prefix/lib/link")
            link.type = tarfile.SYMTYPE
            link.linkname = "file"
            tar.addfile(link)
        inventory = read_inventory(archive, "prefix/")
        self.assertEqual(set(inventory), {"lib/file", "lib/link"})
        self.assertEqual(inventory["lib/link"], ["symlink", "file"])


if __name__ == "__main__":
    unittest.main()
