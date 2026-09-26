#!/usr/bin/env python3
"""Check a frozen CI candidate against external acceptance evidence; never publish."""
import argparse
import json
from pathlib import Path
import re
import runpy
import tarfile
import zipfile

from ci_guest_source import verify_ci_guest_source
from common import ROOT, digest
from check_public import check as check_public
from check_version import check_release_docs
from package_native import payload, verify_archive
from native_target import DARWIN, UBUNTU, target_metadata, manifest_target
from linux_runtime_notices import verify as verify_linux_notices
from platform_acceptance import STEPS
from runtime_notices import verify as verify_runtime_notices


NATIVE = "mariamem-native-darwin-arm64.tar.gz"
NATIVE_FILES = ("wasmer-headless", "mariamem.wasmu", "mariamem.wasmu.json")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_native_acceptance(acceptance, commit, native_hash, native_manifest, guest):
    require(acceptance.get("mode") == "acceptance" and acceptance.get("result") == "PASS"
            and acceptance.get("platform_acceptance_passed") is True,
            "clean platform acceptance did not pass")
    target = manifest_target(native_manifest)
    expected_native = target["bundle_name"] + ".tar.gz"
    archive_record = acceptance["archive"]
    require(archive_record.get("filename") == expected_native
            and archive_record.get("expected_sha256") == native_hash
            and archive_record.get("sha256") == native_hash,
            "clean acceptance refers to another native archive")
    environment = acceptance["environment"]
    if target["platform"] == DARWIN:
        require(environment.get("architecture") == "arm64" and environment.get("product_version", "").startswith("15."), "clean acceptance did not run on macOS 15 arm64")
    else:
        require(environment.get("system") == "Linux" and environment.get("architecture") == "x86_64"
                and environment.get("distribution") == "ubuntu" and environment.get("version_id") == "24.04"
                and acceptance.get("target") == UBUNTU, "clean acceptance did not run on Ubuntu 24.04 x86_64")
    require(acceptance.get("module_requested") == "github.com/masahitojp/mariamem@" + commit,
            "clean acceptance used another Go module commit")
    require(acceptance.get("expected_source_commit") == commit,
            "clean acceptance did not verify the exact source commit")
    resolved = acceptance.get("module_resolved", {})
    require(resolved.get("Path") == "github.com/masahitojp/mariamem"
            and resolved.get("Origin", {}).get("Hash") == commit,
            "clean acceptance resolved another public Go module commit")
    require(set(acceptance["steps"]) == set(STEPS)
            and all(step.get("status") == "PASS" for step in acceptance["steps"].values()),
            "clean acceptance has an incomplete step")
    require(acceptance["artifacts"]["guest_wasm_sha256"] == guest["wasm_sha256"],
            "clean acceptance used another guest WASM")
    for name in NATIVE_FILES:
        require(acceptance["artifacts"]["files"][name] == native_manifest["sha256"][name],
                "clean acceptance used another native " + name)


def check_candidate(commit, acceptance_path, root=ROOT):
    root = Path(root).resolve()
    version = runpy.run_path(str(root / "python/mariamem/_version.py"))
    python_version, git_tag = version["PYTHON_VERSION"], version["GIT_TAG"]
    source_candidate = f"mariamem-{python_version}-source-candidate.tar.gz"
    corresponding_source = f"mariamem-{python_version}-corresponding-source.tar.gz"
    lock = json.loads((root / "release/inputs.lock.json").read_text())
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "candidate must be a full Git SHA")
    check_release_docs(root)
    public = check_public(root)
    build = root / "build"
    source_record = json.loads((build / "release/source-manifest.json").read_text())
    source = build / "release" / source_candidate
    require(source_record.get("file") == source_candidate, "source candidate filename/version differs")
    require(source.is_file() and digest(source) == source_record.get("sha256"),
            "corresponding-source candidate hash differs")
    require(source_record["manifest"]["files"] == public["files"],
            "corresponding source differs from exact candidate checkout")
    source_check = json.loads((build / "source-candidate-check.json").read_text())
    require(source_check.get("passed") is True and source_check.get("source_candidate_sha256") == digest(source),
            "offline corresponding-source verification missing or stale")
    guest = verify_ci_guest_source(root, lock, build, source_record["manifest"].get("build_records"))
    require(guest == source_record["manifest"]["guest_source_provenance"],
            "guest source provenance differs from source archive")
    require(guest == source_check["guest_source_provenance"],
            "offline source verification differs from candidate")
    require(guest["source_commit"] == commit, "guest was built from another commit")

    aot_manifest = json.loads((build / "guest-aot/manifest.json").read_text())
    target = manifest_target(aot_manifest, root)
    native_name = target["bundle_name"] + ".tar.gz"
    notices = verify_runtime_notices(root) if target["platform"] == DARWIN else verify_linux_notices(root)
    require(notices["complete"] and not notices["missing_notices"], "runtime notices incomplete")
    require(digest(build / "guest-aot/wasmer-headless") == notices["runtime_sha256"],
            "candidate Wasmer binary differs from reviewed runtime notices")

    native = build / "release/native-candidate" / native_name
    expected_native = payload(root, build / "guest-aot", package_version=python_version)
    verify_archive(native, expected_native)
    native_hash = digest(native)
    native_record = json.loads((native.parent / "native-candidate.json").read_text())
    require(native_record.get("sha256") == native_hash and native_record.get("archive_checks_passed") is True,
            "native candidate build record differs")
    with tarfile.open(native, "r:gz") as archive:
        prefix = target["bundle_name"] + "/"
        native_manifest = json.load(archive.extractfile(prefix + "manifest.json"))
        native_files = {name: archive.extractfile(prefix + name).read() for name in NATIVE_FILES}
    require(native_manifest.get("package_version") == python_version,
            "native package version differs")
    require(native_manifest.get("public_release_ready") is False,
            "native candidate must not embed post-build release approval")
    require(native_manifest["sha256"]["mariamem.wasmu"] == guest["aot_sha256"],
            "native candidate guest differs from reviewed AOT")

    wheel_record = json.loads((root / "tests/evidence/alpha-wheel.json").read_text())
    wheel = root / wheel_record["wheel"]
    require(wheel.name == f"mariamem-{python_version}-py3-none-{target['wheel_platform']}.whl", "wheel filename/target differs")
    require(wheel.is_file() and digest(wheel) == wheel_record.get("sha256"),
            "Python wheel hash differs from build evidence")
    require(wheel_record.get("archive_checks_passed") is True, "Python wheel archive checks missing")
    require(wheel_record["manifest"].get("package_version") == python_version,
            "Python wheel build version differs")
    require(wheel_record["manifest"].get("public_release_ready") is False,
            "Python candidate must not embed post-build release approval")
    with zipfile.ZipFile(wheel) as archive:
        require(f"Tag: py3-none-{target['wheel_platform']}" in archive.read(f"mariamem-{python_version}.dist-info/WHEEL").decode(), "wheel platform tag differs")
        metadata = archive.read(f"mariamem-{python_version}.dist-info/METADATA").decode()
        require(f"\nVersion: {python_version}\n" in "\n" + metadata,
                "wheel metadata version differs")
        wheel_manifests = [entry for entry in archive.namelist()
                           if entry.endswith("/mariamem/_native/manifest.json")]
        require(len(wheel_manifests) == 1
                and json.loads(archive.read(wheel_manifests[0])) == wheel_record["manifest"],
                "packaged wheel manifest differs from build evidence")
        for name in NATIVE_FILES:
            matches = [entry for entry in archive.namelist()
                       if entry.endswith("/mariamem/_native/" + name)]
            require(len(matches) == 1 and archive.read(matches[0]) == native_files[name],
                    "wheel and native candidate contain different " + name)
    wheel_acceptance = json.loads((root / "tests/evidence/alpha.json").read_text())
    require(wheel_acceptance.get("passed") is True
            and wheel_acceptance.get("wheel_sha256") == digest(wheel)
            and wheel_acceptance.get("installed_files_match_wheel") is True
            and wheel_acceptance.get("consumer_outside_repository") is True
            and wheel_acceptance.get("native_overrides") is False,
            "installed-wheel acceptance missing or stale")
    require({run.get("name") for run in wheel_acceptance.get("runs", [])}
            == {"serial", "parallel", "migration", "failure-cleanup"},
            "installed-wheel acceptance suite is incomplete")

    acceptance = json.loads(acceptance_path.read_text())
    verify_native_acceptance(acceptance, commit, native_hash, native_manifest, guest)

    assets = {native_name: native_hash, wheel.name: digest(wheel),
              corresponding_source: digest(source)}
    return {"version": 1, "result": "READY", "source_commit": commit, "git_tag": git_tag,
            "python_version": python_version, "assets": assets,
            "guest_source_provenance": guest, "native_acceptance_sha256": digest(acceptance_path),
            "wheel_acceptance_sha256": digest(root / "tests/evidence/alpha.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--native-acceptance", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT, help="exact candidate source checkout")
    args = parser.parse_args()
    try:
        result = check_candidate(args.candidate_sha, args.native_acceptance, args.root)
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError, zipfile.BadZipFile) as error:
        print("Release candidate: NOT READY\n- " + str(error))
        return 1
    output = args.root.resolve() / "build/release/ci-ready.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    checksums = args.root.resolve() / "build/release/SHA256SUMS"
    checksums.write_text("".join(f"{sha}  {name}\n" for name, sha in result["assets"].items()))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
