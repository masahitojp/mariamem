#!/usr/bin/env python3
"""Restore exact CI candidate/evidence inputs; never build or run acceptance."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import shutil
import stat
import tarfile
import tempfile
import urllib.request
import zipfile

from common import ROOT, digest
from ci_guest_source import verify_ci_guest_source
from check_ci_release import NATIVE, verify_native_acceptance
from release_version import SOURCE_CANDIDATE

WORKFLOW = ".github/workflows/release-candidate-ready.yml"
EVIDENCE_FILES = {
    "build/release/ci-native-acceptance.json", "build/release/ci-native-acceptance.log",
    "build/release/ci-ready.json", "build/release/SHA256SUMS",
    "tests/evidence/alpha.json", "build/source-candidate-check.json",
    "build/release/ci-reuse.json", "build/release/ci-guard.log", "build/release/ci-restore.log",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def safe_name(name):
    path = PurePosixPath(name)
    require(not path.is_absolute() and ".." not in path.parts and "\\" not in name,
            "unsafe archive path: " + name)
    require(str(path) not in (".", ""), "empty archive path")
    return str(path)


def candidate_path(name, directory=False, source_filename=SOURCE_CANDIDATE):
    name = safe_name(name)
    prefixes = ("build/guest-wasm", "build/guest-aot")
    files = {"build/release/native-candidate/" + NATIVE,
             "build/release/native-candidate/native-candidate.json",
             "build/release/" + source_filename,
             "build/release/source-manifest.json", "build/source-candidate-check.json",
             "tests/evidence/alpha-wheel.json"}
    allowed = name in files or any(name == p or name.startswith(p + "/") for p in prefixes)
    allowed = allowed or (name.startswith("build/") and name.endswith(".whl")
                          and "/../" not in name)
    if directory:
        allowed = allowed or name in {"build", "build/release", "build/release/native-candidate",
                                      "tests", "tests/evidence"}
    require(allowed, "unexpected candidate path: " + name)
    return name


def restore_tar(path, destination, source_filename=SOURCE_CANDIDATE):
    with tarfile.open(path, "r:") as archive:
        seen = set()
        members = archive.getmembers()
        for member in members:
            name = candidate_path(member.name, member.isdir(), source_filename)
            require(name not in seen, "duplicate candidate entry: " + name)
            seen.add(name)
            require(member.isfile() or member.isdir(), "special/link candidate entry: " + name)
        for member in members:
            target = destination / safe_name(member.name)
            require(not target.is_symlink() and not any(p.is_symlink() for p in target.parents),
                    "destination contains symlink: " + member.name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                require(not target.exists(), "refusing to overwrite candidate file: " + member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(member.mode & 0o777)


def restore_zip(path, destination, candidate=False):
    with zipfile.ZipFile(path) as archive:
        seen = set()
        for entry in archive.infolist():
            name = safe_name(entry.filename.rstrip("/"))
            require(name not in seen, "duplicate ZIP entry: " + name)
            seen.add(name)
            mode = entry.external_attr >> 16
            require(not stat.S_ISLNK(mode) and (stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR)),
                    "special/link ZIP entry: " + name)
            if entry.is_dir():
                require(not candidate and any(p.startswith(name + "/") for p in EVIDENCE_FILES),
                        "unexpected ZIP directory: " + name)
            else:
                require(name == "candidate-handoff.tar" if candidate else name in EVIDENCE_FILES,
                        "unexpected ZIP entry: " + name)
        for entry in archive.infolist():
            if not candidate and entry.filename not in ("build/release/ci-native-acceptance.json",
                                                        "build/release/ci-native-acceptance.log",
                                                        "tests/evidence/alpha.json"):
                continue
            target = destination / safe_name(entry.filename.rstrip("/"))
            require(not target.is_symlink() and not any(p.is_symlink() for p in target.parents),
                    "destination contains symlink")
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                require(not target.exists(), "refusing to overwrite evidence file: " + entry.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None:
            redirected.remove_header("Authorization")
        return redirected


class GitHub:
    def __init__(self, repository, token):
        require(re.fullmatch(r"[\w.-]+/[\w.-]+", repository), "invalid GitHub repository")
        self.base = "https://api.github.com/repos/" + repository
        self.headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            self.headers["Authorization"] = "Bearer " + token
        self.opener = urllib.request.build_opener(SafeRedirect())

    def request(self, path):
        return self.opener.open(urllib.request.Request(self.base + path, headers=self.headers), timeout=120)

    def json(self, path):
        with self.request(path) as response:
            return json.load(response)

    def artifact(self, run, name, commit, destination):
        info = self.json(f"/actions/runs/{run}")
        require(info.get("path", "").split("@", 1)[0] == WORKFLOW,
                "reuse run is not the canonical Release CI workflow")
        # Retried runs may execute the newer workflow while checking out an older candidate.
        # Candidate provenance below binds the source; workflow head_sha alone cannot.
        entries = []
        page = 1
        while True:
            found = self.json(f"/actions/runs/{run}/artifacts?per_page=100&page={page}")["artifacts"]
            entries.extend(found)
            if len(found) < 100:
                break
            page += 1
        matches = [a for a in entries if a["name"] == name]
        require(len(matches) == 1, "required reusable artifact missing or ambiguous: " + name)
        artifact = matches[0]
        require(not artifact.get("expired"), "reusable artifact expired: " + name)
        expected = artifact.get("digest", "")
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", expected or ""),
                "GitHub artifact has no verifiable SHA256 digest: " + name)
        with self.request(f"/actions/artifacts/{artifact['id']}/zip") as source, destination.open("wb") as output:
            shutil.copyfileobj(source, output)
        require(digest(destination) == expected.split(":", 1)[1], "GitHub artifact ZIP hash mismatch: " + name)
        return {"run_id": run, "artifact_id": artifact["id"], "name": name, "zip_sha256": digest(destination)}


def verify_candidate(root, commit, source_filename=SOURCE_CANDIDATE):
    lock = json.loads((root / "release/inputs.lock.json").read_text())
    source_record = json.loads((root / "build/release/source-manifest.json").read_text())
    guest = verify_ci_guest_source(root, lock, root / "build", source_record["manifest"]["build_records"])
    require(guest["source_commit"] == commit, "reused candidate source SHA differs")
    require(guest == source_record["manifest"]["guest_source_provenance"], "source provenance differs")
    native_record = json.loads((root / "build/release/native-candidate/native-candidate.json").read_text())
    wheel_record = json.loads((root / "tests/evidence/alpha-wheel.json").read_text())
    wheel_path = candidate_path(wheel_record["wheel"])
    records = [((root / "build/release/native-candidate" / NATIVE), native_record["sha256"]),
               (root / wheel_path, wheel_record["sha256"]),
               (root / "build/release" / source_filename, source_record["sha256"])]
    require(source_record["file"] == source_filename, "source filename/version differs")
    for path, expected in records:
        require(path.is_file() and digest(path) == expected, "reused candidate hash differs: " + path.name)
    return {path.name: expected for path, expected in records}, guest


def verify_evidence(root, commit, hashes, guest):
    native = root / "build/release/native-candidate" / NATIVE
    with tarfile.open(native, "r:gz") as archive:
        manifest = json.load(archive.extractfile("mariamem-native-darwin-arm64/manifest.json"))
    acceptance = json.loads((root / "build/release/ci-native-acceptance.json").read_text())
    verify_native_acceptance(acceptance, commit, hashes[NATIVE], manifest, guest)
    wheel_record = json.loads((root / "tests/evidence/alpha-wheel.json").read_text())
    evidence = json.loads((root / "tests/evidence/alpha.json").read_text())
    require(evidence.get("passed") is True and evidence.get("wheel_sha256") == wheel_record["sha256"]
            and evidence.get("installed_files_match_wheel") is True
            and evidence.get("consumer_outside_repository") is True
            and evidence.get("native_overrides") is False,
            "reused installed-wheel acceptance missing, failed, or mismatched")
    require({r.get("name") for r in evidence.get("runs", [])}
            == {"serial", "parallel", "migration", "failure-cleanup"}, "reused wheel acceptance incomplete")
    return {name: digest(root / name) for name in
            ("build/release/ci-native-acceptance.json", "tests/evidence/alpha.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("full", "acceptance-only", "guard-only"), required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--handoff", type=Path)
    parser.add_argument("--handoff-sha256")
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--candidate-run", type=int)
    parser.add_argument("--evidence-run", type=int)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", "masahitojp/mariamem"))
    args = parser.parse_args()
    try:
        require(re.fullmatch(r"[0-9a-f]{40}", args.candidate_sha), "candidate SHA must be full lowercase Git SHA")
        root = args.root.resolve()
        version = runpy.run_path(str(root / "python/mariamem/_version.py"))["PYTHON_VERSION"]
        source_filename = f"mariamem-{version}-source-candidate.tar.gz"
        require(args.mode == "full" or (args.candidate_run is not None and args.candidate_run > 0), "candidate-run is required for reuse")
        require(args.evidence_run is None or args.evidence_run > 0, "invalid evidence run ID")
        api = GitHub(args.repository, os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
        with tempfile.TemporaryDirectory(prefix="mariamem-ci-reuse-") as temporary:
            staging = Path(temporary)
            if args.mode == "full":
                require(args.handoff is not None and re.fullmatch(r"[0-9a-f]{64}", args.handoff_sha256 or ""),
                        "full mode requires handoff and SHA256")
                handoff = args.handoff
                require(digest(handoff) == args.handoff_sha256, "candidate handoff hash mismatch")
                candidate_identity = {"handoff_sha256": args.handoff_sha256}
            else:
                candidate_identity = api.artifact(args.candidate_run, "release-candidate-" + args.candidate_sha,
                                                  args.candidate_sha, staging / "candidate.zip")
                restore_zip(staging / "candidate.zip", staging, candidate=True)
                handoff = staging / "candidate-handoff.tar"
            handoff_hash = digest(handoff)
            restore_tar(handoff, root, source_filename)
            hashes, guest = verify_candidate(root, args.candidate_sha, source_filename)
            result = {"version": 1, "mode": args.mode, "source_commit": args.candidate_sha,
                      "candidate_artifact": candidate_identity, "handoff_sha256": handoff_hash,
                      "assets": hashes, "guest_source_provenance": guest}
            if args.mode == "guard-only":
                evidence_run = args.evidence_run or args.candidate_run
                result["evidence_artifact"] = api.artifact(evidence_run, "release-evidence-" + args.candidate_sha,
                                                          args.candidate_sha, staging / "evidence.zip")
                restore_zip(staging / "evidence.zip", root)
                result["evidence_sha256"] = verify_evidence(root, args.candidate_sha, hashes, guest)
            output = root / "build/release/ci-reuse.json"
            output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            print(json.dumps(result, indent=2, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError, zipfile.BadZipFile) as error:
        print(f"CI reuse FAILED ({args.mode}, candidate {args.candidate_sha}): {error}\n"
              "Restore valid exact artifacts/evidence or request a full run; no rebuild fallback was performed.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
