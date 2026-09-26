"""Narrow native-platform build and archive identities."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import native_target as target
from test_native_package import NativePackage
import package_native as pkg


class NativeTarget(unittest.TestCase):
    def test_supported_ubuntu_only(self):
        with patch.object(target.platform, "system", return_value="Linux"), \
             patch.object(target.platform, "machine", return_value="x86_64"), \
             patch.object(target.platform, "freedesktop_os_release", create=True,
                          return_value={"ID": "ubuntu", "VERSION_ID": "24.04"}):
            actual = target.current_target()
            self.assertEqual(actual["wheel_platform"], "linux_x86_64")
            self.assertEqual(actual["runtime_input"], "wasmer-linux-x86_64")
        for distribution, version in (("ubuntu", "22.04"), ("debian", "12")):
            with patch.object(target.platform, "system", return_value="Linux"), \
                 patch.object(target.platform, "machine", return_value="x86_64"), \
                 patch.object(target.platform, "freedesktop_os_release", create=True,
                              return_value={"ID": distribution, "VERSION_ID": version}):
                with self.assertRaisesRegex(ValueError, "Ubuntu 24.04"):
                    target.current_target()

    def test_elf_dependency_inspection(self):
        with patch.object(target.subprocess, "check_output", side_effect=[
                "Machine: Advanced Micro Devices X86-64",
                "(NEEDED) Shared library: [libc.so.6]", "Name: GLIBC_2.39 Name: GLIBC_2.17"]):
            result = target.elf_dependencies(Path("runtime"))
        self.assertEqual(result["needed"], ["libc.so.6"])
        self.assertEqual(result["glibc_versions"], ["2.17", "2.39"])
        self.assertFalse(result["manylinux_verified"])

    def test_newer_glibc_rejected(self):
        with patch.object(target.subprocess, "check_output", side_effect=[
                "Advanced Micro Devices X86-64", "", "GLIBC_2.40"]):
            with self.assertRaisesRegex(ValueError, "above Ubuntu"):
                target.elf_dependencies(Path("runtime"))


class UbuntuNativePackage(NativePackage):
    def setUp(self):
        super().setUp()
        self.manifest.pop("minimum_macos")
        self.manifest.update(target.platform_fields(target.target_metadata(target.UBUNTU)))
        self.save_manifest()

    # The inherited corruption checks exercise both platform payloads.
    def test_reproducible_archive_and_extracted_permissions(self):
        files = pkg.payload(self.root, self.native)
        first, second = self.root / "first.tar.gz", self.root / "second.tar.gz"
        pkg.write_archive(first, files)
        pkg.write_archive(second, files)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        pkg.verify_archive(first, files)
        self.assertEqual(pkg.archive_name(files), "mariamem-native-ubuntu24.04-x86_64")
        self.assertNotIn("minimum_macos", json.loads(files["manifest.json"]))

    def test_raise_supported_floor_without_binary_changes(self):
        self.manifest["version_id"] = "22.04"
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "candidate platform"):
            pkg.payload(self.root, self.native)

    def test_cannot_lower_input_minimum(self):
        self.manifest["platform"] = "linux-x86_64"
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "unsupported native target"):
            pkg.payload(self.root, self.native)
