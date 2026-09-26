#!/usr/bin/env python3
"""Publish only the exact READY candidate; never rebuild, overwrite, or roll back."""
import argparse
import json
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import tempfile

from check_ci_release import check_candidate, require
from common import ROOT, digest


def command(args, root):
    result = subprocess.run(args, cwd=root, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"{args[0]} {args[1]} failed: {result.stderr.strip()[-2000:]}")
    return result.stdout.strip()


def release_exists(repository, tag, root):
    result = subprocess.run(["gh", "api", f"repos/{repository}/releases/tags/{tag}"],
                            cwd=root, text=True, capture_output=True)
    if result.returncode == 0:
        return True
    if "HTTP 404" in result.stderr:
        return False
    raise RuntimeError("cannot check existing release: " + result.stderr.strip())


def prepare(root, commit, notes, ready_path=None):
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "candidate must be a full SHA")
    require(command(["git", "rev-parse", "HEAD"], root) == commit, "checkout is not exact candidate")
    require(not command(["git", "status", "--porcelain", "--untracked-files=no"], root),
            "candidate checkout has tracked changes")
    ready = json.loads((ready_path or root / "build/release/ci-ready.json").read_text())
    checked = check_candidate(commit, root / "build/release/ci-native-acceptance.json", root)
    require(ready == checked and ready.get("result") == "READY", "READY evidence differs from current guard")
    version = runpy.run_path(str(root / "python/mariamem/_version.py"))
    require(ready["source_commit"] == commit and ready["git_tag"] == version["GIT_TAG"]
            and ready["python_version"] == version["PYTHON_VERSION"], "release identity differs")
    require(len(ready["assets"]) == 3, "expected exactly three candidate artifacts")
    expected_names = {"mariamem-native-darwin-arm64.tar.gz",
                      f"mariamem-{version['PYTHON_VERSION']}-py3-none-macosx_15_0_arm64.whl",
                      f"mariamem-{version['PYTHON_VERSION']}-corresponding-source.tar.gz"}
    require(set(ready["assets"]) == expected_names, "unexpected alpha asset names")
    checksums = root / "build/release/SHA256SUMS"
    # JSON sorting may reorder assets; compare records, never tolerate duplicate names.
    entries = [line.split("  ") for line in checksums.read_text().splitlines()]
    require(len(entries) == 3 and {name: sha for sha, name in entries} == ready["assets"],
            "SHA256SUMS differs from READY artifacts")
    if notes is None:
        suffix = f"{version['STAGE']}.{version['SERIAL']}" if version["STAGE"] else version["GIT_TAG"]
        notes = root / "release" / f"NOTES-{suffix}.md"
    notes = notes.resolve()
    require(notes.is_relative_to(root) and notes.is_file(), "release notes must belong to candidate checkout")
    require(not command(["git", "status", "--porcelain", "--", str(notes.relative_to(root))], root),
            "release notes are modified")
    require(command(["git", "ls-files", "--", str(notes.relative_to(root))], root),
            "release notes must be tracked")
    require(re.search(r"^#{1,6}\s+.*" + re.escape(version["GIT_TAG"]) + r"(?:\s|$)",
                      notes.read_text(), re.MULTILINE), "release notes heading does not identify canonical tag")
    wheel_record = json.loads((root / "tests/evidence/alpha-wheel.json").read_text())
    paths = {"mariamem-native-darwin-arm64.tar.gz": root / "build/release/native-candidate/mariamem-native-darwin-arm64.tar.gz",
             Path(wheel_record["wheel"]).name: root / wheel_record["wheel"],
             f"mariamem-{version['PYTHON_VERSION']}-corresponding-source.tar.gz":
             root / f"build/release/mariamem-{version['PYTHON_VERSION']}-source-candidate.tar.gz"}
    for name, path in paths.items():
        require(path.is_file() and digest(path) == ready["assets"][name], "artifact hash differs: " + name)
    staging = root / "build/release/publish"
    staging.mkdir(parents=True, exist_ok=True)
    for name, path in paths.items():
        shutil.copyfile(path, staging / name)
    shutil.copyfile(checksums, staging / "SHA256SUMS")
    hashes = {name: digest(staging / name) for name in [*ready["assets"], "SHA256SUMS"]}
    require(all(hashes[name] == sha for name, sha in ready["assets"].items()), "staged bytes differ")
    return {"version": 1, "source_commit": commit, "git_tag": ready["git_tag"],
            "python_version": ready["python_version"], "assets": hashes,
            "prerelease": version["STAGE"] in {"alpha", "beta", "rc"},
            "native_acceptance_sha256": ready["native_acceptance_sha256"],
            "wheel_acceptance_sha256": ready["wheel_acceptance_sha256"],
            "status": "PREPARED"}, staging, notes


def publish(root, commit, repository, notes=None, dry_run=False, ready_path=None):
    root = Path(root).resolve()
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is not None,
            "invalid GitHub repository")
    report_path = root / "build/release/ci-publication.json"
    report = {"source_commit": commit, "repository": repository, "status": "FAILED", "stage": "guard"}
    try:
        report, staging, notes = prepare(root, commit, Path(notes) if notes else None, ready_path)
        report.update(repository=repository, stage="remote-preflight")
        tag = report["git_tag"]
        remote = f"https://github.com/{repository}.git"
        require(not command(["git", "tag", "--list", tag], root), "release tag already exists locally")
        require(not command(["git", "ls-remote", "--tags", remote, f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"], root),
                "release tag already exists remotely")
        require(not release_exists(repository, tag, root), "GitHub release already exists")
        exposed = json.loads(command(["gh", "api", f"repos/{repository}/commits/{commit}"], root))
        require(exposed.get("sha") == commit, "exact candidate is not remotely available")
        if dry_run:
            report.update(status="DRY_RUN", stage="complete")
            return report
        report["stage"] = "tag"
        command(["git", "tag", "-a", tag, commit, "-m", f"mariamem {tag}"], root)
        require(command(["git", "rev-parse", tag + "^{commit}"], root) == commit, "local tag target differs")
        # Push only the tag to the explicitly checked repository, never a branch.
        command(["git", "push", remote, f"refs/tags/{tag}:refs/tags/{tag}"], root)
        target = command(["git", "ls-remote", "--tags", remote, f"refs/tags/{tag}^{{}}"], root)
        require(target.split()[:1] == [commit], "published tag target differs")
        report["stage"] = "draft-upload"
        args = ["gh", "release", "create", tag, "--repo", repository, "--verify-tag", "--target", commit,
                "--title", f"mariamem {tag}", "--notes-file", str(notes), "--draft"]
        if report["prerelease"]:
            args.append("--prerelease")
        args.extend(str(staging / name) for name in report["assets"])
        command(args, root)
        report["stage"] = "uploaded-hashes"
        with tempfile.TemporaryDirectory(prefix="mariamem-published-") as temporary:
            command(["gh", "release", "download", tag, "--repo", repository, "--dir", temporary], root)
            require({path.name for path in Path(temporary).iterdir()} == set(report["assets"]),
                    "uploaded asset names differ")
            for name, sha in report["assets"].items():
                require(digest(Path(temporary) / name) == sha, "uploaded artifact hash differs: " + name)
        report["stage"] = "publish"
        command(["gh", "release", "edit", tag, "--repo", repository, "--draft=false"], root)
        release = json.loads(command(["gh", "api", f"repos/{repository}/releases/tags/{tag}"], root))
        require(release.get("tag_name") == tag and release.get("draft") is False
                and release.get("prerelease") == report["prerelease"], "published release metadata differs")
        require({asset["name"] for asset in release["assets"]} == set(report["assets"])
                and len(release["assets"]) == 4, "published asset names differ")
        report.update(status="PUBLISHED", stage="complete", release_url=release["html_url"])
        return report
    except Exception as error:
        report.update(status="FAILED", error=str(error))
        raise
    finally:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--notes", type=Path)
    parser.add_argument("--ready", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    notes = (args.notes if args.notes.is_absolute() else args.root / args.notes) if args.notes else None
    try:
        print(json.dumps(publish(args.root, args.candidate_sha, args.repository, notes, args.dry_run, args.ready), indent=2))
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        print("Publication stopped: " + str(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
