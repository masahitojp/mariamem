#!/usr/bin/env python3
"""Package existing artifacts as a local Go native candidate, never a release."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import stat
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
NAME = "mariamem-native-darwin-arm64"
ARTIFACTS = ("wasmer-headless", "mariamem.wasmu", "mariamem.wasmu.json")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def regular(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f"not a regular file: {path.name}")
    return path.read_bytes()


def payload(root, native):
    original = regular(native / "manifest.json")
    manifest = json.loads(original)
    target = json.loads((root / "python/deployment_target.json").read_text())
    if (manifest.get("version") != 1 or manifest.get("platform") != "darwin-arm64"
            or manifest.get("minimum_macos") != target["minimum_macos"]):
        raise ValueError("native manifest does not match the candidate platform")
    files = {}
    for name in ARTIFACTS:
        data = regular(native / name)
        if digest(data) != manifest["sha256"].get(name):
            raise ValueError(f"artifact hash mismatch: {name}")
        files[name] = data
    if not (native / "wasmer-headless").stat().st_mode & 0o111:
        raise ValueError("runtime is not executable")
    sidecar = json.loads(files["mariamem.wasmu.json"])
    wasm_hash = sidecar.get("wasm_sha256", "")
    if (sidecar.get("snapshot_version") != 1
            or sidecar.get("module_sha256") != digest(files["mariamem.wasmu"])
            or len(wasm_hash) != 64 or any(c not in "0123456789abcdef" for c in wasm_hash)):
        raise ValueError("guest artifact metadata mismatch")
    # Preserve the schema and compatibility fields; remove the unused host hash.
    manifest["sha256"] = {name: digest(files[name]) for name in ARTIFACTS}
    manifest["public_release_ready"] = False
    files["manifest.json"] = encoded(manifest)
    for name in ("LICENSE", "NOTICE", "THIRD_PARTY_LICENSES"):
        files[name] = regular(root / name)
    for path in sorted((root / "licenses").iterdir()):
        files["licenses/" + path.name] = regular(path)
    # These are evidence of candidate inputs, not proof of complete source/notices.
    files["CANDIDATE.json"] = encoded({
        "status": "local-evaluation-candidate", "public_release_ready": False,
        "input_native_manifest_sha256": digest(original),
        "inputs_lock_sha256": digest(regular(root / "release/inputs.lock.json")),
        "reviews": json.loads(regular(root / "release/review.json")),
        "note": "Not cleared for public binary distribution. Complete source/notices and platform review remain required."
    })
    return files


def write_archive(path, files):
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as tar:
                for name, data in sorted(files.items()):
                    info = tarfile.TarInfo(NAME + "/" + name)
                    info.size = len(data)
                    info.mode = 0o755 if name == "wasmer-headless" else 0o644
                    info.mtime = info.uid = info.gid = 0
                    tar.addfile(info, io.BytesIO(data))


def verify_archive(path, files):
    expected = {NAME + "/" + name: data for name, data in files.items()}
    with tarfile.open(path, "r:gz") as tar:
        members = tar.getmembers()
        if len(members) != len(expected) or {m.name for m in members} != set(expected):
            raise ValueError("unexpected, missing or duplicate archive entries")
        for member in members:
            mode = 0o755 if member.name == NAME + "/wasmer-headless" else 0o644
            if not member.isfile() or member.mode != mode:
                raise ValueError("invalid archive type/permissions")
            if tar.extractfile(member).read() != expected[member.name]:
                raise ValueError(f"archive content mismatch: {member.name}")
    return {name: digest(data) for name, data in sorted(files.items())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-dir", type=Path, default=ROOT / "python/mariamem/_native")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build/release/native-candidate")
    parser.add_argument("--verify", type=Path, help="verify an existing archive against current inputs")
    args = parser.parse_args()
    files = payload(ROOT, args.native_dir)
    if args.verify:
        verify_archive(args.verify, files)
        print("Candidate archive content/hash/permissions: PASS")
        return
    args.output_dir.mkdir(parents=True, exist_ok=True)
    archive = args.output_dir / (NAME + ".tar.gz")
    with tempfile.TemporaryDirectory(dir=args.output_dir) as directory:
        pending = Path(directory) / archive.name
        write_archive(pending, files)
        hashes = verify_archive(pending, files)
        pending.replace(archive)
    sha = digest(archive.read_bytes())
    (args.output_dir / "SHA256SUMS").write_text(f"{sha}  {archive.name}\n")
    evidence = {"candidate": True, "public_release_ready": False, "file": archive.name,
                "bytes": archive.stat().st_size, "sha256": sha, "files": hashes,
                "archive_checks_passed": True}
    (args.output_dir / "native-candidate.json").write_bytes(encoded(evidence))
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
