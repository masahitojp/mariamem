"""Immutable artifact transport remains fail-closed after Wasmer retirement."""
import io
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_release_reuse import GitHub, safe_name
from common import digest

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


@pytest.mark.parametrize("name", ["../escape", "/absolute", "", "a\\b"])
def test_artifact_paths_reject_unsafe_names(name):
    with pytest.raises(ValueError): safe_name(name)
