"""Internal owner of one automatically managed host and its request routing."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading


class _Reply:
    def __init__(self):
        self.ready = threading.Event()
        self.value = None
        self.abandoned = False


class Session:
    def __init__(self, binary):
        from . import HostError
        self.binary = str(Path(binary).absolute())
        self._lock = threading.RLock()
        self._write_lock = threading.Lock()
        self._pending = {}
        self._sequence = 0
        self._refs = 0
        self._failure = None
        self._closing = False
        self._reaped = threading.Event()
        self._logs = ""
        self._temp = tempfile.TemporaryDirectory(prefix="mariamem-")
        self.root = Path(self._temp.name)
        self._stderr = None
        self._process = None
        try:
            self._stderr = (self.root / "host.log").open("xb")
            self._process = subprocess.Popen(
                [self.binary, "--shared"], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=self._stderr, text=True,
                encoding="utf-8", bufsize=1,
                env={**os.environ, "TMPDIR": str(self.root)})
            self._hello = _Reply()
            self._reader = threading.Thread(target=self._read, daemon=True)
            self._reader.start()
            if not self._hello.ready.wait(15):
                raise HostError("Shared host greeting timed out", code="host_start",
                                stage="host_ready", closed=True)
            value = self._hello.value
            if isinstance(value, BaseException):
                raise value
            self.guest_identity = value.get("guest_sha256")
            self.capabilities = tuple(value.get("capabilities", ()))
            if value.get("protocol") != 2:
                raise HostError("Invalid host greeting; expected control protocol 2. Use files from the same matching platform wheel or native bundle",
                                code="guest_connection", stage="host_control", closed=True)
        except BaseException as exc:
            self._finish(force=True)
            if isinstance(exc, OSError):
                raise HostError("Host launch failed: " + self.binary + "; install the matching platform wheel and check executable permissions. Cause: " + str(exc),
                                code="host_start", stage="host_launch", closed=True) from exc
            if not isinstance(exc, Exception):
                raise
            if isinstance(exc, HostError) and exc.code not in (None, "unusable"):
                if self._logs:
                    exc.args = (str(exc) + "\n" + self._logs[-1024:].strip(),)
                raise
            status = self._process.returncode if self._process is not None else None
            message = f"Host startup failed before the expected ready handshake (exit status {status}); reinstall the matching platform wheel/native bundle. Cause: {exc}"
            if self._logs:
                message += "\n" + self._logs[-1024:].strip()
            raise HostError(message, code="host_start", stage="host_ready", closed=True) from exc

    def retain(self):
        with self._lock:
            if self._failure is not None:
                raise self._failure
            if self._closing:
                from . import HostError
                raise HostError("Host is closed", code="unusable", closed=True)
            self._refs += 1

    def release(self):
        with self._lock:
            self._refs -= 1
            if self._refs < 0:
                raise RuntimeError("Host ownership underflow")
            final = self._refs == 0
        if final:
            self._finish()

    def _send(self, message):
        with self._write_lock:
            self._process.stdin.write(json.dumps(message) + "\n")
            self._process.stdin.flush()

    def request(self, op, response_timeout=None, **fields):
        from . import HostError, Busy, TransactionActive
        pending = _Reply()
        with self._lock:
            if self._failure is not None:
                raise self._failure
            self._sequence += 1
            identifier = self._sequence
            self._pending[identifier] = pending
        try:
            self._send(dict(id=identifier, op=op, **fields))
        except (OSError, ValueError) as exc:
            self._fail(HostError("Shared host control pipe closed: " + str(exc),
                                 code="unusable", stage="host_control", closed=True))
        try:
            ready = pending.ready.wait(response_timeout)
        except BaseException:
            # An interrupted caller no longer owns a late-created resource.
            with self._lock:
                if pending.ready.is_set():
                    value = pending.value
                    if not isinstance(value, BaseException):
                        self._refs += 1
                        threading.Thread(target=self._late, args=(value,), daemon=True).start()
                else:
                    pending.abandoned = True
                    try:
                        self._send(dict(op="cancel", target=identifier))
                    except (OSError, ValueError):
                        pass
            raise
        if not ready:
            with self._lock:
                if not pending.ready.is_set():
                    pending.abandoned = True
                    try:
                        self._send(dict(op="cancel", target=identifier))
                    except (OSError, ValueError):
                        pass
                    # Keep the pending owner until the late reply is collected.
                    # A late created handle is closed by _read, not leaked.
                    raise TimeoutError("Host control response timed out; the request was cancelled")
        reply = pending.value
        if isinstance(reply, BaseException):
            raise reply
        if not reply.get("ok"):
            error = reply.get("error", {})
            cls = {"busy": Busy, "transaction_active": TransactionActive}.get(error.get("code"), HostError)
            raise cls(error.get("message", "Host request failed"), code=error.get("code"),
                      stage=error.get("stage"), closed=reply.get("closed", op in ("start", "fork")))
        return reply

    def _read(self):
        from . import HostError
        try:
            for line in self._process.stdout:
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("invalid host response object")
                if not self._hello.ready.is_set():
                    if value.get("event") == "error" and isinstance(value.get("error"), dict):
                        error = value["error"]
                        raise HostError(error.get("message", "Host startup failed"),
                                        code=error.get("code", "guest_start"),
                                        stage=error.get("stage"), closed=True)
                    if value.get("event") != "ready":
                        raise ValueError("invalid host greeting")
                    self._hello.value = value
                    self._hello.ready.set()
                    continue
                identifier = value.get("id")
                if type(identifier) is not int or identifier <= 0 or type(value.get("ok")) is not bool:
                    raise ValueError("invalid host response header")
                if not value["ok"] and not isinstance(value.get("error"), dict):
                    raise ValueError("invalid host error object")
                with self._lock:
                    pending = self._pending.pop(identifier, None)
                    if pending is None:
                        raise ValueError("unknown host response id")
                    abandoned = pending.abandoned
                    if abandoned:
                        self._refs += 1  # Cleanup owns the Session through its reply.
                    else:
                        pending.value = value
                        pending.ready.set()
                if abandoned:
                    threading.Thread(target=self._late, args=(value,), daemon=True).start()
            with self._lock:
                expected = self._closing and not self._pending
            if not expected:
                raise EOFError("host exited")
        except (OSError, ValueError, EOFError, HostError) as exc:
            self._fail(exc if isinstance(exc, HostError) else
                       HostError("Shared host terminated or sent invalid control data: " + str(exc),
                                 code="unusable", stage="host_control", closed=True))

    def _late(self, reply):
        try:
            if "database" in reply:
                self.request("db_close", handle=reply["database"]["handle"], response_timeout=60)
            if "live" in reply:
                self.request("live_close", handle=reply["live"]["handle"], response_timeout=None)
            if "snapshot" in reply:
                self.request("snapshot_close", handle=reply["snapshot"], response_timeout=60)
        except Exception:
            # Host failure invalidates all its handles; final owner reaps it.
            pass
        finally:
            self.release()

    def _fail(self, error):
        with self._lock:
            first_failure = self._failure is None
            if first_failure:
                self._failure = error
            if not self._hello.ready.is_set():
                self._hello.value = error
                self._hello.ready.set()
            for pending in self._pending.values():
                pending.value = error
                pending.ready.set()
            self._pending.clear()
        if first_failure:
            threading.Thread(target=self._owner_eof, daemon=True).start()

    def _owner_eof(self):
        # Irrecoverable control failure invalidates the lineage. Stop admitting
        # work and ask its host to close all DBs, preserving logs until release.
        try:
            with self._write_lock:
                if not self._process.stdin.closed:
                    self._process.stdin.close()
        except (OSError, ValueError):
            pass

    @property
    def failed(self):
        with self._lock:
            return self._failure is not None or self._process.poll() is not None

    def _finish(self, force=False):
        with self._lock:
            if self._closing:
                return
            self._closing = True
        try:
            if self._process is not None:
                if self._process.poll() is None and not force:
                    try:
                        self.request("shutdown", response_timeout=5)
                    except Exception:
                        pass
                if not self._process.stdin.closed:
                    self._process.stdin.close()
                try:
                    self._process.wait(timeout=45 if not force else 1)
                except subprocess.TimeoutExpired:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=12)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait(timeout=5)
                if hasattr(self, "_reader") and self._reader.ident is not None and threading.current_thread() is not self._reader:
                    self._reader.join(timeout=5)
                self._process.stdout.close()
        finally:
            if self._stderr is not None:
                self._stderr.close()
            try:
                with (self.root / "host.log").open("rb") as stream:
                    stream.seek(max(0, stream.seek(0, 2)-16384))
                    self._logs = stream.read().decode("utf-8", errors="replace")
            except OSError:
                pass
            self._temp.cleanup()
            self._reaped.set()
