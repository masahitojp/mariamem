"""Tests for targeted lightweight checks (release notes, Python README sdist, v0.4.7 checksums)."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from layout import BENCHMARKS
import check_development_docs as docs


def test_current_release_notes_passes_on_repository():
    result = docs.check_current_release_notes(ROOT)
    assert result["passed"] is True
    assert result["notes"].startswith("release/NOTES-")


def test_current_release_notes_rejects_missing_and_wrong_heading(tmp_path):
    version_dir = tmp_path / "python/mariamem"
    version_dir.mkdir(parents=True)
    shutil.copyfile(ROOT / "python/mariamem/_version.py", version_dir / "_version.py")
    notes_rel = docs.current_release_notes_path(tmp_path)
    with pytest.raises(ValueError, match="missing"):
        docs.check_current_release_notes(tmp_path)
    notes_path = tmp_path / notes_rel
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text("# mariamem v0.0.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="heading does not identify canonical tag"):
        docs.check_current_release_notes(tmp_path)


def test_v047_retained_checksums_pass_and_detect_tampering(tmp_path):
    result = docs.check_v047_retained_checksums(ROOT)
    assert result["passed"] is True
    assert result["files"] == 7

    copied = tmp_path / (BENCHMARKS / "v047-upstream-evidence")
    shutil.copytree(ROOT / (BENCHMARKS / "v047-upstream-evidence"), copied)
    assert docs.check_v047_retained_checksums(tmp_path)["passed"] is True

    (copied / "README.md").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        docs.check_v047_retained_checksums(tmp_path)

    (copied / "README.md").unlink()
    with pytest.raises(ValueError, match="missing or invalid"):
        docs.check_v047_retained_checksums(tmp_path)


def test_python_readme_sdist_rejects_missing_or_empty(tmp_path):
    (tmp_path / "python").mkdir()
    with pytest.raises(ValueError, match="missing"):
        docs.check_python_readme_sdist(tmp_path)
    (tmp_path / "python/README.md").write_text("   \n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        docs.check_python_readme_sdist(tmp_path)


def test_python_readme_sdist_checks_pkg_info_and_twine(tmp_path, monkeypatch):
    shutil.copytree(
        ROOT / "python",
        tmp_path / "python",
        ignore=shutil.ignore_patterns("build", "dist", "*.egg-info", "__pycache__", "_native"),
    )
    readme_text = (tmp_path / "python/README.md").read_text(encoding="utf-8").strip()

    def make_fake_sdist(dist_dir, content_type, body):
        import io, tarfile
        dist_dir.mkdir(parents=True, exist_ok=True)
        archive_path = dist_dir / "mariamem-0.7.0.tar.gz"
        pkg_info = (
            "Metadata-Version: 2.1\n"
            "Name: mariamem\n"
            "Version: 0.7.0\n"
            + (f"Description-Content-Type: {content_type}\n" if content_type is not None else "")
            + "\n"
            + body
            + "\n"
        ).encode("utf-8")
        with tarfile.open(archive_path, "w:gz") as tar:
            info = tarfile.TarInfo("mariamem-0.7.0/PKG-INFO")
            info.size = len(pkg_info)
            tar.addfile(info, io.BytesIO(pkg_info))

    state = {"content_type": "text/markdown", "body": readme_text, "twine_rc": 0}

    def fake_run(argv, cwd=None, check=False, capture_output=False, text=False):
        if "sdist" in argv:
            dist_dir = Path(argv[argv.index("--dist-dir") + 1])
            make_fake_sdist(dist_dir, state["content_type"], state["body"])
            return subprocess.CompletedProcess(argv, 0, "", "")
        if "twine" in argv:
            return subprocess.CompletedProcess(argv, state["twine_rc"], "", "twine error" if state["twine_rc"] else "")
        raise AssertionError(f"unexpected command: {argv}")

    monkeypatch.setattr(docs.subprocess, "run", fake_run)
    assert docs.check_python_readme_sdist(tmp_path)["passed"] is True

    state["content_type"] = "text/plain"
    with pytest.raises(ValueError, match="Description-Content-Type"):
        docs.check_python_readme_sdist(tmp_path)

    state["content_type"] = "text/markdown"
    state["body"] = ""
    with pytest.raises(ValueError, match="empty"):
        docs.check_python_readme_sdist(tmp_path)

    state["body"] = "different body"
    with pytest.raises(ValueError, match="does not match"):
        docs.check_python_readme_sdist(tmp_path)

    state["body"] = readme_text
    state["twine_rc"] = 1
    with pytest.raises(ValueError, match="twine check failed"):
        docs.check_python_readme_sdist(tmp_path)
