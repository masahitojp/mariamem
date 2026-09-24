"""Deployment checks must reject binaries newer than the candidate target."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from deployment import check_binary, minimum_macos


class Deployment(unittest.TestCase):
    def test_modern_and_unrelated_versions(self):
        output = "Load command 1\n cmd LC_BUILD_VERSION\n minos 12.0\n sdk 27.0\nLoad command 2\n cmd LC_SOURCE_VERSION\n version 99.0\n"
        self.assertEqual(minimum_macos(output), (12, 0, 0))

    def test_legacy(self):
        self.assertEqual(minimum_macos("cmd LC_VERSION_MIN_MACOSX\n version 11.0\n sdk 15.2\n"), (11, 0, 0))

    def test_missing_target_rejected(self):
        with self.assertRaises(ValueError):
            minimum_macos("cmd LC_SOURCE_VERSION\n version 12.0\n")

    def test_newer_binary_rejected(self):
        with patch("deployment.subprocess.check_output", return_value="cmd LC_BUILD_VERSION\n minos 15.1\n"):
            with self.assertRaises(ValueError):
                check_binary(Path("host"), 15)

    def test_older_binary_allowed(self):
        with patch("deployment.subprocess.check_output", return_value="cmd LC_BUILD_VERSION\n minos 11.0\n"):
            self.assertEqual(check_binary(Path("runtime"), 15), "11.0.0")


if __name__ == "__main__":
    unittest.main()
