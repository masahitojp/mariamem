"""Fail-closed checks for external CI acceptance evidence."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_ci_release import NATIVE, NATIVE_FILES, verify_native_acceptance
from platform_acceptance import STEPS


COMMIT = "a" * 40
ARCHIVE_HASH = "b" * 64
WASM_HASH = "c" * 64


def accepted():
    files = {name: "d" * 64 for name in NATIVE_FILES}
    evidence = {
        "mode": "acceptance", "result": "PASS", "platform_acceptance_passed": True,
        "archive": {"filename": NATIVE, "expected_sha256": ARCHIVE_HASH,
                    "sha256": ARCHIVE_HASH},
        "environment": {"architecture": "arm64", "product_version": "15.7.7"},
        "module_requested": "github.com/masahitojp/mariamem@" + COMMIT,
        "expected_source_commit": COMMIT,
        "module_resolved": {"Path": "github.com/masahitojp/mariamem",
                            "Origin": {"Hash": COMMIT}},
        "steps": {name: {"status": "PASS"} for name in STEPS},
        "artifacts": {"guest_wasm_sha256": WASM_HASH, "files": files},
    }
    return evidence, {"platform":"darwin-arm64", "minimum_macos":15, "sha256": files}, {"wasm_sha256": WASM_HASH}


def test_exact_candidate_acceptance():
    evidence, manifest, guest = accepted()
    verify_native_acceptance(evidence, COMMIT, ARCHIVE_HASH, manifest, guest)


@pytest.mark.parametrize("path,value,message", [
    (("archive", "sha256"), "e" * 64, "another native archive"),
    (("module_resolved", "Origin", "Hash"), "e" * 40, "another public Go module"),
    (("steps", "Snapshot", "status"), "NOT_RUN", "incomplete step"),
    (("artifacts", "guest_wasm_sha256"), "e" * 64, "another guest WASM"),
    (("environment", "architecture"), "x86_64", "macOS 15 arm64"),
])
def test_reject_stale_or_incomplete_acceptance(path, value, message):
    evidence, manifest, guest = accepted()
    changed = copy.deepcopy(evidence)
    part = changed
    for key in path[:-1]:
        part = part[key]
    part[path[-1]] = value
    with pytest.raises(ValueError, match=message):
        verify_native_acceptance(changed, COMMIT, ARCHIVE_HASH, manifest, guest)


def ubuntu_accepted():
    evidence, manifest, guest = accepted()
    manifest.update(platform="ubuntu24.04-x86_64", distribution="ubuntu", version_id="24.04", architecture="x86_64")
    del manifest["minimum_macos"]
    evidence["target"] = "ubuntu24.04-x86_64"
    evidence["archive"]["filename"] = "mariamem-native-ubuntu24.04-x86_64.tar.gz"
    evidence["environment"] = {"system": "Linux", "architecture": "x86_64", "distribution": "ubuntu", "version_id": "24.04"}
    return evidence, manifest, guest


def test_exact_ubuntu_candidate_acceptance():
    evidence, manifest, guest = ubuntu_accepted()
    verify_native_acceptance(evidence, COMMIT, ARCHIVE_HASH, manifest, guest)


@pytest.mark.parametrize("path,value,message", [
    (("archive", "sha256"), "e" * 64, "another native archive"),
    (("environment", "distribution"), "debian", "Ubuntu 24.04 x86_64"),
    (("environment", "version_id"), "22.04", "Ubuntu 24.04 x86_64"),
    (("environment", "architecture"), "aarch64", "Ubuntu 24.04 x86_64"),
    (("module_resolved", "Origin", "Hash"), "e" * 40, "another public Go module"),
    (("artifacts", "files", "wasmer-headless"), "e" * 64, "another native wasmer-headless"),
])
def test_rejects_wrong_ubuntu_acceptance(path, value, message):
    evidence, manifest, guest = ubuntu_accepted()
    evidence = copy.deepcopy(evidence)
    part = evidence
    for key in path[:-1]:
        part = part[key]
    part[path[-1]] = value
    with pytest.raises(ValueError, match=message):
        verify_native_acceptance(evidence, COMMIT, ARCHIVE_HASH, manifest, guest)
