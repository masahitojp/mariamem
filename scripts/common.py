"""Pinned inputs and checked archive extraction shared by release tools."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "release/inputs.lock.json").read_text())


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def fetch(name):
    entry = next(p for p in LOCK["inputs"] if p["name"] == name)
    path = ROOT / "build/downloads" / entry["file"]
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix(path.suffix + ".partial")
        try:
            with urllib.request.urlopen(entry["url"], timeout=120) as response, temporary.open("wb") as out:
                import shutil
                shutil.copyfileobj(response, out)
            if digest(temporary) != entry["sha256"]:
                raise ValueError(f"download hash mismatch: {name}")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    if digest(path) != entry["sha256"]:
        raise ValueError(f"input hash mismatch: {path}")
    return path


def extract(archive, destination):
    """Extract pinned tar inputs; reject path escapes and special files."""
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive) as source:
        members = source.getmembers()
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise ValueError(f"unsafe member: {member.name}")
            if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                raise ValueError(f"special member: {member.name}")
            if member.issym() or member.islnk():
                link = Path(member.linkname)
                base = destination / member.name if member.islnk() else (destination / member.name).parent
                target = (destination / link if member.islnk() else base / link).resolve()
                if link.is_absolute() or not target.is_relative_to(destination):
                    raise ValueError(f"unsafe link: {member.name}")
        # Validate each resolved destination as previous entries may create symlinks.
        for member in members:
            if not (destination / member.name).resolve().is_relative_to(destination):
                raise ValueError(f"escaped destination: {member.name}")
            source.extract(member, destination)
