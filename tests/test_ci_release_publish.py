"""Publication is fail-closed, immutable, and never runs on NOT READY."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ci_release_publish as publisher
from common import digest

SHA = "a" * 40
TAG = "v0.1.0-alpha.3"
REPO = "masahitojp/mariamem"


@pytest.fixture
def candidate(tmp_path, monkeypatch):
    release = tmp_path / "build/release"
    release.mkdir(parents=True)
    native = release / "native-candidate/mariamem-native-darwin-arm64.tar.gz"
    native.parent.mkdir()
    native.write_bytes(b"native")
    wheel = release / "mariamem-0.1.0a3-py3-none-macosx_15_0_arm64.whl"
    wheel.write_bytes(b"wheel")
    source = release / "mariamem-0.1.0a3-source-candidate.tar.gz"
    source.write_bytes(b"source")
    canonical = tmp_path / "python/mariamem/_version.py"
    canonical.parent.mkdir(parents=True)
    canonical.write_text('PYTHON_VERSION="0.1.0a3"\nGIT_TAG="v0.1.0-alpha.3"\nSTAGE="alpha"\nSERIAL=3\n')
    notes = tmp_path / "release/NOTES-alpha.3.md"
    notes.parent.mkdir()
    notes.write_text("# " + TAG)
    wheel_record = tmp_path / "tests/evidence/alpha-wheel.json"
    wheel_record.parent.mkdir(parents=True)
    wheel_record.write_text(json.dumps({"wheel": str(wheel.relative_to(tmp_path))}))
    assets = {native.name: digest(native), wheel.name: digest(wheel),
              "mariamem-0.1.0a3-darwin-arm64-corresponding-source.tar.gz": digest(source)}
    staging = release / "publish"
    staging.mkdir()
    for name, path in ((native.name, native), (wheel.name, wheel), ("mariamem-0.1.0a3-darwin-arm64-corresponding-source.tar.gz", source)):
        (staging / name).write_bytes(path.read_bytes())
    for name in ("mariamem-native-ubuntu24.04-x86_64.tar.gz", "mariamem-0.1.0a3-py3-none-linux_x86_64.whl", "mariamem-0.1.0a3-ubuntu24.04-x86_64-corresponding-source.tar.gz"):
        (staging / name).write_bytes(name.encode())
        assets[name] = digest(staging / name)
    ready = {"version": 2, "platforms": {"darwin-arm64": {}, "ubuntu24.04-x86_64": {}}, "result": "READY", "source_commit": SHA, "git_tag": TAG,
             "python_version": "0.1.0a3", "assets": assets,
             "native_acceptance_sha256": "b" * 64, "wheel_acceptance_sha256": "c" * 64}
    (release / "ci-ready.json").write_text(json.dumps(ready))
    (release / "SHA256SUMS").write_text("".join(f"{sha}  {name}\n" for name, sha in assets.items()))
    monkeypatch.setattr(publisher, "check_aggregate", lambda *args: ready)
    calls = []

    def run(args, root):
        calls.append(args)
        if args[:3] == ["git", "rev-parse", "HEAD"] or args[:2] == ["git", "rev-parse"]:
            return SHA
        if args[:2] == ["git", "ls-files"]:
            return "release/NOTES-alpha.3.md"
        if args[:3] == ["gh", "api", f"repos/{REPO}/commits/{SHA}"]:
            return json.dumps({"sha": SHA})
        if args[:3] == ["gh", "release", "download"]:
            dest = Path(args[args.index("--dir") + 1])
            for path in (release / "publish").iterdir():
                (dest / path.name).write_bytes(path.read_bytes())
        if args[:3] == ["gh", "api", f"repos/{REPO}/releases/tags/{TAG}"]:
            return json.dumps({"tag_name": TAG, "draft": False, "prerelease": True,
                               "assets": [{"name": name} for name in [*assets, "SHA256SUMS"]],
                               "html_url": "https://example.invalid/release"})
        if args[:2] == ["git", "ls-remote"] and len([a for a in calls if a[:2] == ["git", "push"]]):
            return SHA + "\trefs/tags/" + TAG + "^{}"
        return ""

    monkeypatch.setattr(publisher, "command", run)
    monkeypatch.setattr(publisher, "release_exists", lambda *args: False)
    return tmp_path, ready, calls, run


def mutations(calls):
    return [a for a in calls if a[:2] == ["git", "push"]
            or (a[:2] == ["git", "tag"] and "-a" in a)
            or (a[:2] == ["gh", "release"] and a[2] in {"create", "edit", "upload", "delete"})]


def test_dry_run_validates_and_stages_exact_four_assets_without_mutations(candidate):
    root, ready, calls, _ = candidate
    report = publisher.publish(root, SHA, REPO, dry_run=True)
    assert report["status"] == "DRY_RUN"
    assert set(report["assets"]) == {*ready["assets"], "SHA256SUMS"}
    assert not mutations(calls)


def test_publish_exact_tag_assets_prerelease(candidate):
    root, ready, calls, _ = candidate
    report = publisher.publish(root, SHA, REPO)
    assert report["status"] == "PUBLISHED"
    tag = next(a for a in calls if a[:2] == ["git", "tag"] and "-a" in a)
    assert SHA in tag and "--force" not in tag
    create = next(a for a in calls if a[:3] == ["gh", "release", "create"])
    assert "--draft" in create and "--prerelease" in create and "--verify-tag" in create
    assert len([a for a in create if a.startswith(str(root / "build/release/publish"))]) == 7


@pytest.mark.parametrize("failure", ["not-ready", "source", "tag", "hash", "checksum"])
def test_invalid_candidate_never_mutates(candidate, failure):
    root, ready, calls, _ = candidate
    if failure == "not-ready":
        ready["result"] = "NOT READY"
    elif failure == "source":
        ready["source_commit"] = "d" * 40
    elif failure == "tag":
        ready["git_tag"] = "v0.1.0-alpha.4"
    elif failure == "hash":
        (root / "build/release/publish/mariamem-native-darwin-arm64.tar.gz").write_bytes(b"changed")
    else:
        (root / "build/release/SHA256SUMS").write_text("bad\n")
    with pytest.raises((ValueError, KeyError)):
        publisher.publish(root, SHA, REPO)
    assert not mutations(calls)


@pytest.mark.parametrize("existing", ["local-tag", "remote-tag", "release"])
def test_existing_identity_is_never_overwritten(candidate, monkeypatch, existing):
    root, _, calls, original = candidate
    if existing == "release":
        monkeypatch.setattr(publisher, "release_exists", lambda *args: True)
    else:
        def run(args, directory):
            if (existing == "local-tag" and args[:2] == ["git", "tag"]) or (existing == "remote-tag" and args[:2] == ["git", "ls-remote"]):
                calls.append(args)
                return "existing"
            return original(args, directory)
        monkeypatch.setattr(publisher, "command", run)
    with pytest.raises(ValueError, match="already exists"):
        publisher.publish(root, SHA, REPO)
    assert not mutations(calls)


def test_failure_after_tag_never_rolls_back_or_replaces(candidate, monkeypatch):
    root, _, calls, original = candidate
    def run(args, directory):
        if args[:3] == ["gh", "release", "create"]:
            calls.append(args)
            raise RuntimeError("upload failed")
        return original(args, directory)
    monkeypatch.setattr(publisher, "command", run)
    with pytest.raises(RuntimeError, match="upload failed"):
        publisher.publish(root, SHA, REPO)
    assert any(a[:2] == ["git", "push"] for a in calls)
    assert not any("delete" in a or "--force" in a or "--clobber" in a for a in calls)
    evidence = json.loads((root / "build/release/ci-publication.json").read_text())
    assert evidence["status"] == "FAILED" and evidence["stage"] == "draft-upload"


def test_external_ready_record_must_equal_current_guard(candidate):
    root, ready, calls, _ = candidate
    external = root / "external-ready.json"
    changed = dict(ready, native_acceptance_sha256="0" * 64)
    external.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="READY evidence differs"):
        publisher.publish(root, SHA, REPO, ready_path=external)
    assert not mutations(calls)


def test_uploaded_mismatch_stops_before_publishing_draft(candidate, monkeypatch):
    root, _, calls, original = candidate
    def run(args, directory):
        output = original(args, directory)
        if args[:3] == ["gh", "release", "download"]:
            path = Path(args[args.index("--dir") + 1]) / "SHA256SUMS"
            path.write_bytes(b"mismatch")
        return output
    monkeypatch.setattr(publisher, "command", run)
    with pytest.raises(ValueError, match="uploaded artifact hash differs"):
        publisher.publish(root, SHA, REPO)
    assert not any(a[:3] == ["gh", "release", "edit"] for a in calls)
    assert not any("delete" in a or "--clobber" in a for a in calls)


def test_single_platform_ready_cannot_publish(candidate):
    root, ready, calls, _ = candidate
    ready['version'] = 1
    (root / 'build/release/ci-ready.json').write_text(json.dumps(ready))
    with pytest.raises(ValueError, match='aggregate platform READY'):
        publisher.publish(root, SHA, REPO)
    assert not mutations(calls)


def test_stable_publication_is_not_prerelease(candidate, monkeypatch):
    root, ready, calls, original = candidate
    tag = "v0.1.0"
    ready.update(git_tag=tag, python_version="0.1.0")
    staging = root / "build/release/publish"
    for name in list(ready["assets"]):
        renamed = name.replace("0.1.0a3", "0.1.0")
        if renamed != name:
            (staging / name).rename(staging / renamed)
            ready["assets"][renamed] = ready["assets"].pop(name)
    (root / "build/release/ci-ready.json").write_text(json.dumps(ready))
    (root / "build/release/SHA256SUMS").write_text("".join(f"{sha}  {name}\n" for name, sha in ready["assets"].items()))
    (root / "python/mariamem/_version.py").write_text('PYTHON_VERSION="0.1.0"\nGIT_TAG="v0.1.0"\nSTAGE=""\nSERIAL=0\n')
    (root / "release/NOTES-v0.1.0.md").write_text("# mariamem " + tag)

    def run(args, directory):
        if args[:2] == ["git", "ls-files"]:
            calls.append(args)
            return "release/NOTES-v0.1.0.md"
        if args[:3] == ["gh", "api", f"repos/{REPO}/releases/tags/{tag}"]:
            calls.append(args)
            return json.dumps({"tag_name": tag, "draft": False, "prerelease": False,
                               "assets": [{"name": name} for name in [*ready["assets"], "SHA256SUMS"]],
                               "html_url": "https://example.invalid/release"})
        if args[:2] == ["git", "ls-remote"] and any(a[:2] == ["git", "push"] for a in calls):
            calls.append(args)
            return SHA + "\trefs/tags/" + tag + "^{}"
        return original(args, directory)

    monkeypatch.setattr(publisher, "command", run)
    publisher.publish(root, SHA, REPO)
    create = next(a for a in calls if a[:3] == ["gh", "release", "create"])
    assert tag in create and "--prerelease" not in create
    assert str(root / "release/NOTES-v0.1.0.md") in create
