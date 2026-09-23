"""Checks for the publication boundary and source archive extraction."""
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_public
from common import extract


class PublicationBoundary(unittest.TestCase):
    def test_benchmark_sources_included_but_results_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "benchmarks/results").mkdir(parents=True)
            (root / "benchmarks/ready_to_query.py").write_text("# source\n")
            (root / "benchmarks/results/raw.json").write_text('{"local": true}')
            with patch.object(check_public, "ROOT", root):
                self.assertEqual(list(check_public.check()["files"]), ["benchmarks/ready_to_query.py"])

    def test_ignored_build_is_not_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("public")
            (root / "build").mkdir()
            (root / "build/private.log").write_text("local")
            with patch.object(check_public, "ROOT", root):
                self.assertEqual(list(check_public.check()["files"]), ["README.md"])

    def test_unknown_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("example")
            with patch.object(check_public, "ROOT", root), self.assertRaises(ValueError):
                check_public.check()

    def test_personal_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("/" + "Users" + "/example/private")
            with patch.object(check_public, "ROOT", root), self.assertRaises(ValueError):
                check_public.check()

    def test_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").symlink_to("../outside")
            with patch.object(check_public, "ROOT", root), self.assertRaises(ValueError):
                check_public.check()


class ExtractionBoundary(unittest.TestCase):
    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "input.tar"
            with tarfile.open(archive, "w") as tar:
                info = tarfile.TarInfo("../outside")
                info.size = 1
                tar.addfile(info, io.BytesIO(b"x"))
            with self.assertRaises(ValueError):
                extract(archive, root / "source")
            self.assertFalse((root / "outside").exists())

    def test_link_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "input.tar"
            with tarfile.open(archive, "w") as tar:
                info = tarfile.TarInfo("link")
                info.type = tarfile.SYMTYPE
                info.linkname = "../outside"
                tar.addfile(info)
            with self.assertRaises(ValueError):
                extract(archive, root / "source")


if __name__ == "__main__":
    unittest.main()
