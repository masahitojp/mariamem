"""Narrow native-platform build and archive identities."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import native_target as target


class NativeTarget(unittest.TestCase):
    def test_supported_ubuntu_only(self):
        with patch.object(target.platform, "system", return_value="Linux"), \
             patch.object(target.platform, "machine", return_value="x86_64"), \
             patch.object(target.platform, "freedesktop_os_release", create=True,
                          return_value={"ID": "ubuntu", "VERSION_ID": "24.04"}):
            actual = target.current_target()
            self.assertEqual(actual["wheel_platform"], "linux_x86_64")
            self.assertEqual(actual["platform"], "ubuntu24.04-x86_64")
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
