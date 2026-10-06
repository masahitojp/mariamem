"""Cold snapshot handles; runtime compatibility is also checked by the Go host."""
import hashlib
import json
from pathlib import Path
import stat


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def inventory(root):
    entries = {}

    def visit(path):
        info = path.lstat()
        name = path.relative_to(root).as_posix()
        if stat.S_ISDIR(info.st_mode):
            entries[name] = {"kind": "directory"}
            for child in path.iterdir():
                visit(child)
        elif stat.S_ISREG(info.st_mode) and path != root:
            entries[name] = {"kind": "file", "bytes": info.st_size, "sha256": digest(path)}
        else:
            raise ValueError(f"Snapshot contains a link or special file: {path}")

    visit(root)
    return entries


from .owned_snapshot import Snapshot
