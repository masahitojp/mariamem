"""Verify pinned WASIX runtime/header source coverage without rebuilding sysroot."""
import hashlib
from pathlib import PurePosixPath
import tarfile

from common import digest


def verify_runtime_sources(root, lock):
    entries = {entry["name"]: entry for entry in lock["inputs"]}
    results = {}
    for pin in lock["runtime_source_submodules_to_collect"]:
        entry = entries[pin["source_input"]]
        revision = pin["commit"]
        if entry.get("revision") != revision:
            raise ValueError(f"runtime source revision mismatch: {pin['path']}")
        if (entry["url"] != f"https://codeload.github.com/{entry['repository']}/tar.gz/{revision}"
                or entry["archive_root"] != entry["repository"].split("/")[-1] + "-" + revision):
            raise ValueError(f"runtime source URL/root mismatch: {pin['path']}")
        archive = root / "build/downloads" / entry["file"]
        if digest(archive) != entry["sha256"]:
            raise ValueError(f"runtime source hash mismatch: {entry['name']}")
        licenses = {}
        source_dirs = set()
        with tarfile.open(archive, "r|gz") as tar:
            for member in tar:
                name = PurePosixPath(member.name)
                if (name.is_absolute() or ".." in name.parts or not name.parts
                        or name.parts[0] != entry["archive_root"]):
                    raise ValueError(f"runtime source archive root/path mismatch: {member.name}")
                relative = name.relative_to(entry["archive_root"]).as_posix()
                if relative in entry["license_files"]:
                    if not member.isfile() or not member.size or relative in licenses:
                        raise ValueError(f"invalid runtime license: {relative}")
                    data = tar.extractfile(member).read()
                    if not data.strip():
                        raise ValueError(f"empty runtime license: {relative}")
                    licenses[relative] = hashlib.sha256(data).hexdigest()
                if member.isfile() and member.size:
                    source_dirs.update(prefix for prefix in entry["source_directories"]
                                       if relative.startswith(prefix + "/"))
                # LLVM has many members; no need to retain the tar index in memory.
                tar.members.clear()
        if set(licenses) != set(entry["license_files"]):
            raise ValueError(f"missing runtime licenses: {entry['name']}")
        if source_dirs != set(entry["source_directories"]):
            raise ValueError(f"missing runtime source directories: {entry['name']}")
        results[pin["path"]] = {
            "revision": revision, "archive": entry["file"], "sha256": entry["sha256"],
            "archive_root": entry["archive_root"], "license_sha256": licenses,
            "source_directories": sorted(source_dirs),
        }
    if len(results) != 3:
        raise ValueError("expected three pinned WASIX source submodules")
    return results
