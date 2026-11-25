#!/usr/bin/env python3
"""Targeted lightweight checks for release notes, Python README metadata, and v0.4.7 retained evidence."""
import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
V047_EVIDENCE_DIR = Path("benchmarks/v047-upstream-evidence")
V047_SHA256SUMS = V047_EVIDENCE_DIR / "SHA256SUMS"


def current_release_notes_path(root=ROOT):
    """Return the canonical repository-relative path for the current version's release notes."""
    version = runpy.run_path(str(Path(root) / "python/mariamem/_version.py"))
    suffix = f"{version['STAGE']}.{version['SERIAL']}" if version["STAGE"] else version["GIT_TAG"]
    return f"release/NOTES-{suffix}.md"


def check_current_release_notes(root=ROOT):
    """Verify the current version's release notes exist and carry a heading with the canonical tag."""
    root = Path(root).resolve()
    version = runpy.run_path(str(root / "python/mariamem/_version.py"))
    rel = current_release_notes_path(root)
    notes = (root / rel).resolve()
    if not notes.is_relative_to(root) or not notes.is_file():
        raise ValueError(f"current release notes missing: {rel}")
    text = notes.read_text(encoding="utf-8")
    if not re.search(r"^#{1,6}\s+.*" + re.escape(version["GIT_TAG"]) + r"(?:\s|$)", text, re.MULTILINE):
        raise ValueError(f"{rel}: heading does not identify canonical tag {version['GIT_TAG']}")
    return {"notes": rel, "tag": version["GIT_TAG"], "passed": True}


def check_python_readme_sdist(root=ROOT, *, python_executable=sys.executable):
    """Build an isolated sdist from python/ and verify PKG-INFO Markdown description and twine check."""
    root = Path(root).resolve()
    readme = root / "python/README.md"
    if not readme.is_file():
        raise ValueError("python/README.md is missing")
    expected_body = readme.read_text(encoding="utf-8").strip()
    if not expected_body:
        raise ValueError("python/README.md is empty")

    with tempfile.TemporaryDirectory(prefix="mariamem-sdist-check-") as temporary:
        staging = Path(temporary).resolve()
        staged_python = staging / "python"
        shutil.copytree(
            root / "python",
            staged_python,
            ignore=shutil.ignore_patterns("build", "dist", "*.egg-info", "__pycache__", "_native"),
        )
        dist_dir = staging / "dist"
        subprocess.run(
            [str(python_executable), "setup.py", "sdist", "--dist-dir", str(dist_dir)],
            cwd=staged_python,
            check=True,
            capture_output=True,
            text=True,
        )
        sdists = sorted(dist_dir.glob("*.tar.gz"))
        if len(sdists) != 1:
            raise ValueError(f"expected exactly one sdist archive, found {len(sdists)}")
        sdist = sdists[0]

        with tarfile.open(sdist, "r:gz") as archive:
            pkg_infos = [m for m in archive.getmembers() if m.isfile() and m.name.count("/") == 1 and m.name.endswith("/PKG-INFO")]
            if len(pkg_infos) != 1:
                raise ValueError(f"sdist must contain exactly one top-level PKG-INFO, found {len(pkg_infos)}")
            raw = archive.extractfile(pkg_infos[0]).read()
        metadata = BytesParser().parsebytes(raw)
        content_type = metadata.get("Description-Content-Type")
        if content_type != "text/markdown":
            raise ValueError(f"sdist Description-Content-Type is {content_type!r}, expected 'text/markdown'")
        payload = metadata.get_payload().strip()
        if not payload:
            raise ValueError("sdist PKG-INFO long description is empty")
        if payload != expected_body:
            raise ValueError("sdist PKG-INFO long description does not match python/README.md")

        twine = subprocess.run(
            [str(python_executable), "-m", "twine", "check", "--strict", str(sdist)],
            cwd=staging,
            capture_output=True,
            text=True,
        )
        if twine.returncode != 0:
            raise ValueError(f"twine check failed:\n{(twine.stdout + twine.stderr).strip()}")

    return {"sdist": sdist.name, "content_type": content_type, "passed": True}


def check_v047_retained_checksums(root=ROOT):
    """Verify every retained file listed in benchmarks/v047-upstream-evidence/SHA256SUMS."""
    root = Path(root).resolve()
    evidence_dir = (root / V047_EVIDENCE_DIR).resolve()
    sums_path = (root / V047_SHA256SUMS).resolve()
    if not sums_path.is_file():
        raise ValueError(f"retained checksum manifest missing: {V047_SHA256SUMS}")
    lines = [line for line in sums_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"retained checksum manifest is empty: {V047_SHA256SUMS}")
    seen = {}
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise ValueError(f"invalid SHA256SUMS line in {V047_SHA256SUMS}: {line!r}")
        expected_sha, rel = match.groups()
        if rel in seen:
            raise ValueError(f"duplicate SHA256SUMS entry: {rel}")
        target = (evidence_dir / rel).resolve()
        if not target.is_relative_to(evidence_dir) or not target.is_file() or target.is_symlink():
            raise ValueError(f"retained evidence file missing or invalid: {rel}")
        actual_sha = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(f"retained evidence checksum mismatch for {rel}: expected {expected_sha}, got {actual_sha}")
        seen[rel] = actual_sha
    return {"manifest": str(V047_SHA256SUMS), "files": len(seen), "passed": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--release-notes", action="store_true")
    parser.add_argument("--python-readme", action="store_true")
    parser.add_argument("--v047-evidence", action="store_true")
    args = parser.parse_args()
    results = {}
    if args.release_notes:
        results["release_notes"] = check_current_release_notes(args.root)
    if args.python_readme:
        results["python_readme"] = check_python_readme_sdist(args.root)
    if args.v047_evidence:
        results["v047_evidence"] = check_v047_retained_checksums(args.root)
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
