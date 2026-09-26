"""Immutable CI retry inputs fail closed without invoking builders or acceptance."""
import io
import json
from pathlib import Path
import sys
import tarfile
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_release_reuse import GitHub, restore_tar, restore_zip
from common import digest


def tar_input(path, name, kind=tarfile.REGTYPE):
    with tarfile.open(path, "w") as archive:
        item = tarfile.TarInfo(name)
        item.type = kind
        item.mode = 0o755
        item.size = 1 if kind == tarfile.REGTYPE else 0
        archive.addfile(item, io.BytesIO(b"x") if item.size else None)


def test_restore_only_ignored_candidate_files(tmp_path):
    source = tmp_path / "input.tar"
    root = tmp_path / "checkout"
    tar_input(source, "build/guest-aot/wasmer-headless")
    restore_tar(source, root)
    assert (root / "build/guest-aot/wasmer-headless").read_bytes() == b"x"
    assert (root / "build/guest-aot/wasmer-headless").stat().st_mode & 0o111
    with pytest.raises(ValueError, match="overwrite"):
        restore_tar(source, root)


@pytest.mark.parametrize("name,kind", [("../escape", tarfile.REGTYPE),
    ("README.md", tarfile.REGTYPE), ("build/guest-aot/link", tarfile.SYMTYPE),
    ("build/guest-aot/device", tarfile.CHRTYPE)])
def test_reject_unsafe_candidate_paths(tmp_path, name, kind):
    source = tmp_path / "input.tar"
    tar_input(source, name, kind)
    with pytest.raises(ValueError):
        restore_tar(source, tmp_path / "checkout")


def test_reject_symlink_parent(tmp_path):
    source = tmp_path / "input.tar"
    tar_input(source, "build/guest-aot/file")
    root = tmp_path / "checkout"
    root.mkdir()
    (root / "build").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        restore_tar(source, root)


def test_evidence_cannot_replace_source_or_build_report(tmp_path):
    archive = tmp_path / "evidence.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("build/source-candidate-check.json", "stale")
        output.writestr("tests/evidence/alpha.json", "{}")
    root = tmp_path / "checkout"
    (root / "build").mkdir(parents=True)
    (root / "build/source-candidate-check.json").write_text("frozen")
    restore_zip(archive, root)
    assert (root / "build/source-candidate-check.json").read_text() == "frozen"
    assert json.loads((root / "tests/evidence/alpha.json").read_text()) == {}
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("release/review.json", "{}")
    with pytest.raises(ValueError, match="unexpected"):
        restore_zip(archive, root)


class FakeGitHub(GitHub):
    def __init__(self, artifact, payload):
        self.record = artifact
        self.payload = payload
    def json(self, path):
        if "/artifacts?" in path:
            return {"artifacts": [self.record] if self.record else []}
        return {"path": ".github/workflows/release-candidate-ready.yml"}
    def request(self, path):
        return io.BytesIO(self.payload)


def artifact_record(tmp_path):
    archive = tmp_path / "payload.zip"
    archive.write_bytes(b"zip bytes")
    return {"name": "release-candidate-" + "a" * 40, "id": 1,
            "expired": False, "digest": "sha256:" + digest(archive)}, archive.read_bytes()


def test_github_digest_authenticates_download(tmp_path):
    record, payload = artifact_record(tmp_path)
    identity = FakeGitHub(record, payload).artifact(12, record["name"], "a" * 40, tmp_path / "download")
    assert identity["zip_sha256"] == record["digest"].split(":")[1]


@pytest.mark.parametrize("change,message", [({"expired": True}, "expired"),
    ({"digest": None}, "no verifiable"), ({"digest": "sha256:" + "0" * 64}, "hash mismatch")])
def test_github_missing_expired_corrupt_fails(tmp_path, change, message):
    record, payload = artifact_record(tmp_path)
    record.update(change)
    with pytest.raises(ValueError, match=message):
        FakeGitHub(record, payload).artifact(12, record["name"], "a" * 40, tmp_path / "download")


def test_github_missing_artifact_fails(tmp_path):
    with pytest.raises(ValueError, match="missing"):
        FakeGitHub(None, b"").artifact(12, "release-candidate-" + "a" * 40, "a" * 40, tmp_path / "download")


def candidate_fixture(tmp_path, monkeypatch):
    import ci_release_reuse as reuse
    root = tmp_path / "candidate"
    files = {"release/inputs.lock.json": {},
             "build/release/source-manifest.json": {
                 "file": reuse.SOURCE_CANDIDATE, "sha256": "",
                 "manifest": {"build_records": {}, "guest_source_provenance": {"source_commit": "a" * 40}}},
             "build/release/native-candidate/native-candidate.json": {"sha256": ""},
             "tests/evidence/alpha-wheel.json": {"wheel": "build/dist/test.whl", "sha256": ""}}
    binaries = ["build/release/" + reuse.SOURCE_CANDIDATE,
                "build/release/native-candidate/" + reuse.NATIVE, "build/dist/test.whl"]
    for name in binaries:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
    for record, binary in zip(list(files)[1:], binaries):
        files[record]["sha256"] = digest(root / binary)
    for name, value in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    monkeypatch.setattr(reuse, "verify_ci_guest_source", lambda *args: {"source_commit": "a" * 40})
    return root, reuse


def test_candidate_provenance_rejects_requested_source_mismatch(tmp_path, monkeypatch):
    root, reuse = candidate_fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="source SHA differs"):
        reuse.verify_candidate(root, "b" * 40)


def test_candidate_recomputes_all_release_hashes(tmp_path, monkeypatch):
    root, reuse = candidate_fixture(tmp_path, monkeypatch)
    hashes, guest = reuse.verify_candidate(root, "a" * 40)
    assert len(hashes) == 3
    (root / "build/dist/test.whl").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="hash differs"):
        reuse.verify_candidate(root, "a" * 40)


def test_failed_previous_guard_logs_do_not_poison_reusable_acceptance(tmp_path):
    archive = tmp_path / "evidence.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("build/release/ci-guard.log", "NOT READY")
        output.writestr("build/release/ci-ready.json", '{"result":"stale"}')
        output.writestr("build/release/SHA256SUMS", "old hashes")
        output.writestr("build/release/ci-native-acceptance.json", '{"result":"PASS"}')
        output.writestr("tests/evidence/alpha.json", '{"passed":true}')
    root = tmp_path / "candidate"
    restore_zip(archive, root)
    assert not (root / "build/release/ci-guard.log").exists()
    assert not (root / "build/release/ci-ready.json").exists()
    assert not (root / "build/release/SHA256SUMS").exists()
    assert json.loads((root / "build/release/ci-native-acceptance.json").read_text())["result"] == "PASS"



def test_main_canonicalizes_macos_temporary_directory_alias(tmp_path, monkeypatch):
    import ci_release_reuse as reuse
    from contextlib import nullcontext
    root = tmp_path / "candidate"
    (root / "python/mariamem").mkdir(parents=True)
    (root / "python/mariamem/_version.py").write_text("PYTHON_VERSION = '0.1.0a3'\n")
    (root / "build/release").mkdir(parents=True)
    real = tmp_path / "temporary"
    real.mkdir()
    alias = tmp_path / "temporary-alias"
    alias.symlink_to(real, target_is_directory=True)
    handoff = tmp_path / "handoff.tar"
    tar_input(handoff, "build/source-candidate-check.json")
    def artifact(self, run, name, commit, destination):
        with zipfile.ZipFile(destination, "w") as zipped:
            zipped.write(handoff, "candidate-handoff.tar")
        return {"run_id": run}
    monkeypatch.setattr(reuse.GitHub, "artifact", artifact)
    monkeypatch.setattr(reuse.tempfile, "TemporaryDirectory", lambda **kw: nullcontext(str(alias)))
    monkeypatch.setattr(reuse, "verify_candidate", lambda *args: ({}, {"source_commit": "a" * 40}))
    monkeypatch.setattr(sys, "argv", ["reuse", "--mode", "acceptance-only", "--root", str(root),
                                    "--candidate-sha", "a" * 40, "--candidate-run", "123"])
    assert reuse.main() == 0
    assert (root / "build/release/ci-reuse.json").exists()
