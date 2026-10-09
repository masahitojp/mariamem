"""Fixed database baselines backed by validated, owned read-only files."""
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import threading


def _manifest(root):
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise ValueError("Snapshot root must be a real directory")
    if {p.name for p in root.iterdir()} != {"data", "manifest.json"}:
        raise ValueError("Snapshot must contain only data and manifest.json")
    manifest = root / "manifest.json"
    if not stat.S_ISREG(manifest.lstat().st_mode):
        raise ValueError("Snapshot manifest must be a regular file")
    data = json.loads(manifest.read_text())
    if not isinstance(data, dict):
        raise ValueError("Snapshot manifest must be an object")
    if data.get("format") != "mariamem-cold-snapshot" or type(data.get("version")) is not int or data["version"] != 1 or data.get("source_storage") != "memory":
        raise ValueError("Unsupported snapshot format")
    entries = data.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("Snapshot inventory must be an object")
    build = data.get("wasm_sha256", "")
    if not isinstance(build, str) or len(build) != 64 or any(c not in "0123456789abcdef" for c in build):
        raise ValueError("Invalid WASM build hash")
    for name, entry in entries.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            raise ValueError("Snapshot inventory has invalid field types")
        if entry.get("kind") == "directory":
            if set(entry) != {"kind"}:
                raise ValueError("Invalid snapshot directory entry")
        elif entry.get("kind") == "file":
            digest = entry.get("sha256", "")
            if (set(entry) != {"kind", "bytes", "sha256"}
                    or type(entry.get("bytes")) is not int or entry["bytes"] < 0
                    or not isinstance(digest, str) or len(digest) != 64
                    or any(c not in "0123456789abcdef" for c in digest)):
                raise ValueError("Invalid snapshot file entry")
        else:
            raise ValueError("Invalid snapshot inventory kind")
    return data


def _host_identity(options):
    from ._artifacts import resolve
    host = resolve(host_binary=options.get("host_binary"))["host_binary"]
    info = json.loads(subprocess.run([host, "--snapshot-info"], check=True,
                                    capture_output=True, text=True, timeout=10).stdout)
    if (not isinstance(info, dict) or type(info.get("snapshot_version")) is not int
            or info["snapshot_version"] != 1):
        raise ValueError("Host snapshot format is incompatible")
    build = info.get("wasm_sha256", "")
    if (not isinstance(build, str) or len(build) != 64
            or any(c not in "0123456789abcdef" for c in build)):
        raise ValueError("Host snapshot build identity is invalid")
    return host, build


def _copy_tree(source, target):
    info = source.lstat()
    if stat.S_ISDIR(info.st_mode):
        target.mkdir(mode=0o700)
        for child in sorted(source.iterdir()):
            _copy_tree(child, target / child.name)
    elif stat.S_ISREG(info.st_mode):
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as src:
            if not stat.S_ISREG(os.fstat(src.fileno()).st_mode):
                raise ValueError("Snapshot input is not regular")
            with target.open("xb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
    else:
        raise ValueError("Snapshot contains a link or special file")


class Snapshot:
    def __init__(self, path, *, host_binary=None):
        """Import an external artifact into an independent owned template."""
        origin = Path(path).absolute()
        expected = _manifest(origin)
        options = {"host_binary": host_binary} if host_binary else {}
        host, build = _host_identity(options)
        if expected.get("wasm_sha256") != build:
            raise ValueError("Snapshot WASM build mismatch")
        temporary = tempfile.TemporaryDirectory(prefix="mariamem-import-")
        root = Path(temporary.name) / "snapshot"
        try:
            root.mkdir(mode=0o700)
            _copy_tree(origin / "data", root / "data")
            self._adopt(root, expected, {"host_binary": host}, temporary)
        except BaseException:
            temporary.cleanup()
            raise

    @classmethod
    def open(cls, path, *, host_binary=None):
        return cls(path, host_binary=host_binary)

    @classmethod
    def _created(cls, root, options, temporary):
        saved = object.__new__(cls)
        try:
            expected = _manifest(root)
            _, build = _host_identity(options)
            if expected.get("wasm_sha256") != build:
                raise ValueError("Snapshot WASM build mismatch")
            saved._adopt(root, expected, options, temporary)
            return saved
        except BaseException:
            temporary.cleanup()
            raise

    def _adopt(self, root, expected, options, temporary):
        files, entries = [], {}
        try:
            def visit(path):
                info = path.lstat()
                name = path.relative_to(root / "data").as_posix()
                if stat.S_ISDIR(info.st_mode):
                    entries[name] = {"kind": "directory"}
                    for child in sorted(path.iterdir()):
                        visit(child)
                elif stat.S_ISREG(info.st_mode) and name != ".":
                    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                    files.append((name, fd, path))
                    opened = os.fstat(fd)
                    if not stat.S_ISREG(opened.st_mode):
                        raise ValueError("Snapshot backing is not regular")
                    entries[name] = {"kind": "file", "bytes": opened.st_size}
                else:
                    raise ValueError("Snapshot contains a link or special file")
            visit(root / "data")
            for _, _, path in files:
                path.unlink()
            shutil.rmtree(root)
            for name, fd, _ in files:
                if os.fstat(fd).st_nlink != 0:
                    raise ValueError("Owned backing retains path aliases")
                h, offset = hashlib.sha256(), 0
                while True:
                    chunk = os.pread(fd, 1024 * 1024, offset)
                    if not chunk:
                        break
                    h.update(chunk)
                    offset += len(chunk)
                entries[name]["sha256"] = h.hexdigest()
            if entries != expected.get("entries"):
                raise ValueError("Snapshot file manifest mismatch")
            self._files = tuple((name, fd, entries[name]["bytes"]) for name, fd, _ in files)
            self._manifest = copy.deepcopy(expected)
            self._options = options.copy()
            self._temporary = temporary
            self._condition = threading.Condition()
            self._borrowers = 0
            self._closed = False
            self._released = False
            self._close_error = None
        except BaseException:
            for _, fd, _ in files:
                os.close(fd)
            raise

    @contextmanager
    def _borrow(self):
        with self._condition:
            if self._closed:
                raise ValueError("Snapshot is closed")
            for _, fd, size in self._files:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_size != size or info.st_nlink != 0:
                    raise ValueError("Owned snapshot metadata changed")
            self._borrowers += 1
        try:
            yield self._files
        finally:
            with self._condition:
                self._borrowers -= 1
                self._condition.notify_all()

    def _spawn(self, argv, **kwargs):
        with self._borrow() as files, tempfile.TemporaryFile() as description:
            data = {"manifest": self._manifest,
                    "files": [{"name": name, "fd": fd} for name, fd, _ in files]}
            description.write(json.dumps(data).encode())
            description.flush()
            description.seek(0)
            return subprocess.Popen([*argv, "--prepared-fd", str(description.fileno())],
                                    pass_fds=(*[fd for _, fd, _ in files], description.fileno()), **kwargs)

    def fork(self, **options):
        from . import Database
        return Database(**{**self._options, **options, "snapshot": self})

    def close(self):
        """Release owned backing; persisted source artifacts are never removed."""
        with self._condition:
            if self._closed:
                self._condition.wait_for(lambda: self._released)
                if self._close_error is not None:
                    raise self._close_error
                return
            self._closed = True
            self._condition.wait_for(lambda: self._borrowers == 0)
            try:
                for _, fd, _ in self._files:
                    try:
                        os.close(fd)
                    except OSError as error:
                        self._close_error = self._close_error or error
                self._files = ()
                if self._temporary is not None:
                    try:
                        self._temporary.cleanup()
                    except OSError as error:
                        self._close_error = self._close_error or error
            finally:
                self._released = True
                self._condition.notify_all()
            if self._close_error is not None:
                raise self._close_error

    def __enter__(self):
        with self._borrow():
            return self

    def __exit__(self, *exc):
        self.close()
