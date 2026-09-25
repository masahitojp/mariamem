"""The release's ecosystem spellings come from one semantic version."""

from pathlib import Path
import sys
import unittest
import runpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import release_version as version


class ReleaseVersion(unittest.TestCase):
    def test_current_forms(self):
        components = runpy.run_path(str(version.ROOT / "python/mariamem/_version.py"))
        base = f"{components['MAJOR']}.{components['MINOR']}.{components['PATCH']}"
        self.assertEqual(version.GIT_TAG,
                         f"v{base}-{components['STAGE']}.{components['SERIAL']}")
        self.assertEqual(version.PYTHON_VERSION, components["PYTHON_VERSION"])
        self.assertEqual(version.SOURCE_CANDIDATE,
                         f"mariamem-{version.PYTHON_VERSION}-source-candidate.tar.gz")
        self.assertEqual(version.CORRESPONDING_SOURCE,
                         f"mariamem-{version.PYTHON_VERSION}-corresponding-source.tar.gz")

    def test_mismatched_proposed_tag_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            version.require_tag(version.GIT_TAG + "-wrong")


if __name__ == "__main__":
    unittest.main()
