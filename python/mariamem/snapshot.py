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


class Snapshot:
    def __init__(self, path):
        self.path = Path(path).absolute()
        self._options = {}
        self._temporary = None
        self._closed = False
        self.validate()

    @classmethod
    def open(cls, path):
        return cls(path)

    def validate(self):
        if self._closed:
            raise ValueError("Snapshot is closed")
        if not stat.S_ISDIR(self.path.lstat().st_mode):
            raise ValueError("Snapshot root must be a real directory")
        if {p.name for p in self.path.iterdir()} != {"data", "manifest.json"}:
            raise ValueError("Snapshot must contain only data and manifest.json")
        manifest = self.path / "manifest.json"
        if not stat.S_ISREG(manifest.lstat().st_mode):
            raise ValueError("Snapshot manifest must be a regular file")
        data = json.loads(manifest.read_text())
        if data.get("format") != "mariamem-cold-snapshot" or data.get("version") != 1 or data.get("source_storage") != "memory":
            raise ValueError("Unsupported snapshot format")
        build = data.get("wasm_sha256", "")
        if not isinstance(build, str) or len(build) != 64 or any(c not in "0123456789abcdef" for c in build):
            raise ValueError("Invalid WASM build hash")
        if data.get("entries") != inventory(self.path / "data"):
            raise ValueError("Snapshot file manifest mismatch")
        self.manifest = data
        return self

    def fork(self, **options):
        from . import Database
        if self._closed:
            raise ValueError("Snapshot is closed")
        return Database(**{**self._options, **options, "snapshot": self})

    def close(self):
        """Release an owned temporary snapshot; explicit destinations are preserved."""
        if not self._closed:
            self._closed = True
            if self._temporary is not None:
                self._temporary.cleanup()

    def __enter__(self):
        if self._closed:
            raise ValueError("Snapshot is closed")
        return self

    def __exit__(self, *exc):
        self.close()
