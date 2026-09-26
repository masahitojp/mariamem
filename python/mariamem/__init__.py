"""Initial Python lifecycle wrapper. SQL is sent through a MySQL driver."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import tempfile
import time

from ._artifacts import ArtifactError, resolve
from ._version import PYTHON_VERSION

__version__ = PYTHON_VERSION


class HostError(RuntimeError):
    def __init__(self, message, *, code=None, stage=None, closed=False):
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.closed = closed


class Busy(HostError):
    pass


class TransactionActive(HostError):
    pass


class Database:
    def __init__(self, *, host_binary=None, runtime=None, module=None, log_path=None,
                 wasmer_dir=None, query_timeout=30, startup_timeout=120,
                 shutdown_timeout=30, snapshot=None):
        """Start one memory DB, optionally restoring a validated cold snapshot."""
        for timeout in (query_timeout, startup_timeout, shutdown_timeout):
            if not isinstance(timeout, (int, float)) or not 0 < timeout < float("inf"):
                raise ValueError("timeouts must be positive and finite")
        timing_start = time.perf_counter_ns() if os.environ.get("MARIAMEM_TIMING_DIR") else None
        self._startup_timing = [] if timing_start is not None else None
        def mark(name):
            if timing_start is not None:
                self._startup_timing.append({"name": name, "offset_ns": time.perf_counter_ns() - timing_start})
        mark("begin")
        self._lock = threading.Lock()
        self._sequence = 0
        self._closed = False
        self._shutdown_timeout = shutdown_timeout
        self._messages = queue.Queue()
        try:
            resolved = resolve(host_binary, runtime, module)
        except ArtifactError as exc:
            raise HostError(str(exc), code=exc.code, stage="platform" if exc.code == "unsupported_platform" else "artifact_validation") from exc
        mark("artifacts_resolved")
        host_binary, runtime, module = (resolved[key] for key in ("host_binary", "runtime", "module"))
        self._options = dict(host_binary=host_binary, runtime=runtime, module=module,
                             wasmer_dir=wasmer_dir, query_timeout=query_timeout,
                             startup_timeout=startup_timeout, shutdown_timeout=shutdown_timeout)
        if snapshot is not None:
            snapshot = Snapshot.open(snapshot.path if isinstance(snapshot, Snapshot) else snapshot)
        mark("snapshot_validated")
        self._temporary = tempfile.TemporaryDirectory(prefix="mariamem-")
        self._logs = ""
        if wasmer_dir is None:
            wasmer_dir = Path(self._temporary.name) / "runtime"
            wasmer_dir.mkdir()
        if log_path is None:
            log_path = Path(self._temporary.name) / "host.log"
        self.log_path = Path(log_path).absolute()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._log = self.log_path.open("xb")
        except BaseException:
            self._temporary.cleanup()
            raise
        argv = [str(Path(host_binary).absolute()), "--runtime", str(Path(runtime).absolute()),
                "--module", str(Path(module).absolute()), "--query-timeout", f"{query_timeout}s",
                "--startup-timeout", f"{startup_timeout}s", "--shutdown-timeout", f"{shutdown_timeout}s"]
        if wasmer_dir is not None:
            argv += ["--wasmer-dir", str(Path(wasmer_dir).absolute())]
        if snapshot is not None:
            argv += ["--snapshot", str(snapshot.path)]
        mark("host_spawn_begin")
        try:
            self._process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                             stderr=self._log, text=True, encoding="utf-8", bufsize=1)
        except OSError as exc:
            self._log.close()
            self._temporary.cleanup()
            raise HostError(f"Host launch failed: {argv[0]}; install the matching platform wheel/native bundle and check executable permissions. Cause: {exc}", code="host_start", stage="host_launch", closed=True) from exc
        except BaseException:
            self._log.close()
            self._temporary.cleanup()
            raise
        mark("host_spawn_returned")
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        try:
            ready = self._receive(startup_timeout + 15)
            if ready.get("event") == "error":
                error = ready.get("error", {})
                raise HostError(error.get("message", "Guest startup failed"),
                                code=error.get("code", "guest_start"), stage=error.get("stage"), closed=True)
            if ready.get("event") != "ready" or ready.get("protocol") != 1:
                raise HostError("Host startup greeting is invalid; expected control protocol 1. Use host/runtime/guest files from the same matching platform wheel or native bundle.", code="guest_connection", stage="host_control", closed=True)
            mark("host_control_ready")
            self.id = ready["id"]
            self._connection_info = {key: ready[key] for key in ("host", "port", "user", "password", "database")}
            self.capabilities = tuple(ready["capabilities"])
            # Diagnostic data, not the database's public identity.
            self.diagnostics = {"host_pid": ready["pid"], "runtime_pid": ready["runtime_pid"]}
        except BaseException as exc:
            self._dispose()
            if not isinstance(exc, Exception):
                raise
            if isinstance(exc, HostError) and exc.code not in (None, "unusable"):
                if self._logs:
                    exc.args = (str(exc) + "\n" + self._logs[-1024:].strip(),)
                raise
            message = f"Host startup failed before the expected ready handshake (exit status {self._process.returncode}); reinstall the matching platform wheel/native bundle. Cause: {exc}"
            if self._logs:
                message += "\n" + self._logs[-1024:].strip()
            raise HostError(message, code="host_start", stage="host_ready", closed=True) from exc

    def _read(self):
        try:
            for line in self._process.stdout:
                self._messages.put(json.loads(line))
            self._messages.put(HostError(f"Database instance terminated; see {self.log_path}",
                                         code="unusable", closed=True))
        except Exception as exc:
            error = HostError(f"Host control response failed: {exc}", code="guest_connection", stage="host_control", closed=True)
            error.__cause__ = exc
            self._messages.put(error)

    def _receive(self, timeout):
        try:
            message = self._messages.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError("Host control response timed out") from exc
        if isinstance(message, Exception):
            raise message
        return message

    def _request(self, operation, response_timeout=10, **fields):
        if self._process.poll() is not None:
            raise HostError(f"Database instance terminated; see {self.log_path}",
                            code="unusable", closed=True)
        self._sequence += 1
        try:
            self._process.stdin.write(json.dumps({"id": self._sequence, "op": operation, **fields}) + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise HostError(f"Database instance terminated; see {self.log_path}",
                            code="unusable", closed=True) from exc
        reply = self._receive(response_timeout)
        if reply.get("id") != self._sequence:
            raise HostError("Host response ID mismatch")
        if not reply.get("ok"):
            error = reply.get("error", {})
            code = error.get("code")
            cls = {"busy": Busy, "transaction_active": TransactionActive}.get(code, HostError)
            raise cls(error.get("message", str(error)), code=code, stage=error.get("stage"), closed=reply.get("closed", False))
        return reply

    def status(self):
        with self._lock:
            if self._closed:
                raise HostError("Database is closed")
            try:
                return self._request("status")
            except HostError as exc:
                if exc.closed:
                    self._dispose()
                raise

    @property
    def closed(self):
        return self._closed or self._process.poll() is not None

    @property
    def logs(self):
        if not self._closed and self.log_path.exists():
            return self.log_path.read_text(errors="replace")[-16384:]
        return self._logs

    def connection_info(self):
        if self.closed:
            raise HostError("Database is closed")
        return dict(self._connection_info)

    def wait_disconnected(self, timeout=5):
        """Wait for driver disconnect/session cleanup before reusing one DB."""
        if not isinstance(timeout, (int, float)) or not 0 < timeout < float("inf"):
            raise ValueError("timeout must be positive and finite")
        deadline = time.monotonic() + timeout
        while self.status()["active_connections"]:
            if time.monotonic() >= deadline:
                raise TimeoutError("SQL connections are still active")
            time.sleep(0.005)

    def close(self):
        with self._lock:
            if self._closed:
                return
            try:
                if self._process.poll() is not None:
                    return
                self._request("close", self._shutdown_timeout + 25)
                code = self._process.wait(timeout=5)
                if code:
                    raise HostError(f"Host exited with code {code}")
            except HostError as exc:
                if not exc.closed:
                    raise
            finally:
                self._dispose()

    def snapshot(self, destination=None, *, rollback=False, timeout=120):
        """Cold snapshot. Success ends this DB; precondition rejection keeps it alive."""
        if not isinstance(timeout, (int, float)) or not 0 < timeout < float("inf"):
            raise ValueError("timeout must be positive and finite")
        if not isinstance(rollback, bool):
            raise ValueError("rollback must be a bool")
        temporary = None
        if destination is None:
            temporary = tempfile.TemporaryDirectory(prefix="mariamem-snapshot-")
            destination = Path(temporary.name) / "snapshot"
        destination = Path(destination).absolute()
        with self._lock:
            if self._closed:
                if temporary:
                    temporary.cleanup()
                raise HostError("Database is closed")
            try:
                # Export/exit has a guest deadline; host copy/hash has no size-independent deadline.
                self._request("snapshot", response_timeout=None, destination=str(destination),
                              rollback=rollback, timeout=f"{timeout}s")
                code = self._process.wait(timeout=5)
                if code:
                    raise HostError(f"Host exited with code {code}")
            except HostError as exc:
                if temporary:
                    temporary.cleanup()
                if exc.closed or exc.code is None:
                    self._dispose()
                raise
            except BaseException:
                if temporary:
                    temporary.cleanup()
                self._dispose()
                raise
            self._dispose()
            try:
                saved = Snapshot.open(destination)
            except BaseException:
                if temporary:
                    temporary.cleanup()
                raise
            saved._temporary = temporary
            saved._options = self._options.copy()
            return saved

    def _dispose(self):
        self._closed = True
        if not self._process.stdin.closed:
            try:
                self._process.stdin.close()  # Owner EOF asks host to shut down guest.
            except (BrokenPipeError, OSError):
                pass
        try:
            self._process.wait(timeout=self._shutdown_timeout + 25)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            try:
                self._process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                # Last-resort cleanup is restricted to this wrapper's own child.
                runtime_pid = getattr(self, "diagnostics", {}).get("runtime_pid")
                if runtime_pid:
                    try:
                        import signal
                        os.killpg(runtime_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                self._process.kill()
                self._process.wait(timeout=5)
        self._reader.join(timeout=5)
        self._process.stdout.close()
        self._log.close()
        try:
            self._logs = self.log_path.read_text(errors="replace")[-16384:]
        except OSError:
            self._logs = ""
        finally:
            self._temporary.cleanup()

    def __enter__(self):
        if self._closed:
            raise HostError("Database is closed")
        return self

    def __exit__(self, *exc):
        self.close()


def start(**options):
    return Database(**options)


from .snapshot import Snapshot
