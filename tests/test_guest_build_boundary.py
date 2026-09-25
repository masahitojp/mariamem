"""Cheap checks for the immutable Linux WASM to macOS AOT handoff."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from common import ROOT, digest
from compile_guest_aot import verify_handoff
from install_guest_toolchain import inventory


class GuestHandoff(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.wasm = self.directory / "mariamem.wasm"
        self.wasm.write_bytes(b"\0asm\1\0\0\0payload")
        prepared = {"inputs_lock_sha256": digest(ROOT / "release/inputs.lock.json"),
                    "overlays": {}, "modified_files": {}}
        toolchain = {"version": 1, "wasixcc_archive_sha256": "a" * 64}
        (self.directory / "prepared-source.json").write_text(json.dumps(prepared, indent=2) + "\n")
        (self.directory / "toolchain.json").write_text(json.dumps(toolchain, indent=2, sort_keys=True) + "\n")
        self.record = {
            "version": 1, "linux_architecture": "x86_64", "target": "wasm32/WASIX",
            "wasm_file": self.wasm.name, "wasm_sha256": digest(self.wasm),
            "wasm_bytes": self.wasm.stat().st_size,
            "inputs_lock_sha256": digest(ROOT / "release/inputs.lock.json"),
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "prepared_source_sha256": digest(self.directory / "prepared-source.json"),
            "prepared_source": prepared,
            "toolchain_provenance_sha256": digest(self.directory / "toolchain.json"),
            "toolchain": toolchain,
        }
        self.save()

    def save(self):
        (self.directory / "provenance.json").write_text(json.dumps(self.record, indent=2, sort_keys=True) + "\n")
        (self.directory / "SHA256SUMS").write_text(f"{self.record['wasm_sha256']}  mariamem.wasm\n")

    def test_valid_exact_handoff(self):
        wasm, _, record = verify_handoff(self.directory)
        self.assertEqual(wasm, self.wasm)
        self.assertEqual(record["wasm_sha256"], digest(self.wasm))

    def test_reject_changed_wasm(self):
        self.wasm.write_bytes(self.wasm.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "WASM SHA256/size"):
            verify_handoff(self.directory)

    def test_reject_changed_checksum(self):
        (self.directory / "SHA256SUMS").write_text("0" * 64 + "  mariamem.wasm\n")
        with self.assertRaisesRegex(ValueError, "checksum record"):
            verify_handoff(self.directory)

    def test_reject_changed_source_and_toolchain_records(self):
        for name, expected_error in (("prepared-source.json", "prepared source"),
                                     ("toolchain.json", "toolchain record")):
            with self.subTest(name=name):
                path = self.directory / name
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                with self.assertRaisesRegex(ValueError, expected_error):
                    verify_handoff(self.directory)
                path.write_bytes(original)

    def test_reject_wrong_source_commit(self):
        self.record["source_commit"] = "0" * 40
        self.save()
        with self.assertRaisesRegex(ValueError, "source commit"):
            verify_handoff(self.directory)


class ToolchainInventory(unittest.TestCase):
    def test_file_and_symlink_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "lib").mkdir()
            (root / "lib/libc.a").write_bytes(b"first")
            (root / "lib/current").symlink_to("libc.a")
            before = inventory(root)
            self.assertEqual(before["entries"], 2)
            (root / "lib/libc.a").write_bytes(b"second")
            self.assertNotEqual(before, inventory(root))


if __name__ == "__main__":
    unittest.main()
