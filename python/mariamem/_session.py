"""Internal owner of one automatically managed host and its request routing."""
import json
import os
from collections import deque
from pathlib import Path
import select
import subprocess
import tempfile
import threading
import time


class _Reply:
    def __init__(self):
        self.ready = threading.Event()
        self.value = None
        self.abandoned = False
        self.cleanup = None
        self.fields = {}
        self.op = None


class _Write:
    def __init__(self, message, deadline):
        self.data = (json.dumps(message, allow_nan=False) + "\n").encode("utf-8")
        if len(self.data) > 1 << 20:
            raise ValueError("control request exceeds 1 MiB")
        self.identifier = message.get("id")
        self.deadline = deadline
        self.started = False
        self.cancelled = threading.Event()
        self.written = threading.Event()


class Session:
    def __init__(self, binary):
        from . import HostError
        self.binary = str(Path(binary).absolute())
        self._lock = threading.RLock()
        self._write_condition = threading.Condition(self._lock)
        self._writes = deque()
        self._transport_stop = threading.Event()
        self._exited = threading.Event()
        self._pending = {}
        self._sequence = 0
        self._refs = 0
        self._failure = None
        self._closing = False
        self._reaped = threading.Event()
        self._logs = ""
        self._handoffs = set()
        self._temp = tempfile.TemporaryDirectory(prefix="mariamem-")
        self.root = Path(self._temp.name)
        self._stderr = None
        self._process = None
        self._writer_io = None
        if os.name == "nt":
            from ._windows_io import WriterIO
            self._writer_io = WriterIO()
        try:
            self._stderr = (self.root / "host.log").open("xb")
            self._process = subprocess.Popen(
                [self.binary, "--shared"], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=self._stderr, bufsize=0,
                env={**os.environ, "TMPDIR": str(self.root),
                     **({"TMP": str(self.root), "TEMP": str(self.root)} if os.name == "nt" else {})})
            self._hello = _Reply()
            # Windows pipe select/nonblocking support does not cover Python3.11.
            # The existing dedicated I/O threads own blocking Windows pipe calls;
            # request deadlines and process retirement remain on caller threads.
            if os.name != "nt":
                os.set_blocking(self._process.stdin.fileno(), False)
                os.set_blocking(self._process.stdout.fileno(), False)
            self._reader = threading.Thread(target=self._read, daemon=True)
            self._reader.start()
            self._writer = threading.Thread(target=self._write, daemon=True)
            self._writer.start()
            self._waiter = threading.Thread(target=self._wait_exit, daemon=True)
            self._waiter.start()
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

    def _wait_exit(self):
        self._process.wait()
        self._exited.set()

    def _enqueue(self, task):
        with self._write_condition:
            while self._writes:
                left = task.deadline - time.monotonic()
                if left <= 0:
                    raise TimeoutError("Host control submission timed out")
                self._write_condition.wait(left)
            if self._transport_stop.is_set():
                raise OSError("control transport closed")
            self._writes.append(task)
            self._write_condition.notify_all()

    def _cancel(self, identifier):
        # Best effort and nonblocking. A late response still has a cleanup owner
        # if a full writer queue prevents cancellation from being sent.
        task = _Write(dict(op="cancel", target=identifier), time.monotonic()+5)
        with self._write_condition:
            if not self._writes and not self._transport_stop.is_set():
                self._writes.append(task)
                self._write_condition.notify_all()

    def _unsent(self, task):
        error = TimeoutError("Host control message was not sent")
        error.submitted = False
        with self._lock:
            pending = self._pending.pop(task.identifier, None)
            if pending is not None:
                if pending.abandoned:
                    self._refs += 1
                else:
                    pending.value = error
                    pending.ready.set()
        if pending is not None and pending.abandoned:
            threading.Thread(target=self._late, args=(error, pending), daemon=True).start()
        task.written.set()

    def _write(self):
        from . import HostError
        io = getattr(self, "_writer_io", None)
        try:
            if io is not None:
                io.register()
            while not self._transport_stop.is_set():
                with self._write_condition:
                    while not self._writes and not self._transport_stop.is_set():
                        self._write_condition.wait(.1)
                    if self._transport_stop.is_set():
                        return
                    task = self._writes.popleft()
                    task.started = True
                    self._write_condition.notify_all()
                offset = 0
                while offset < len(task.data) and not self._transport_stop.is_set():
                    if offset == 0 and (task.cancelled.is_set() or time.monotonic() >= task.deadline):
                        self._unsent(task)
                        break
                    try:
                        count = os.write(self._process.stdin.fileno(), task.data[offset:])
                        if count == 0:
                            raise BrokenPipeError("zero-byte control write")
                        offset += count
                    except BlockingIOError:
                        select.select([], [self._process.stdin.fileno()], [], .1)
                else:
                    task.written.set()
                # A partially written JSON frame must finish before another
                # frame. Only this one writer remains parked on a full pipe;
                # the caller's deadline still expires independently.
        except (OSError, ValueError) as exc:
            if not self._closing:
                self._fail(HostError("Shared host control pipe closed: " + str(exc),
                                     code="unusable", stage="host_control", closed=True))

        finally:
            if io is not None:
                io.close()

    def _stop_windows_writer(self):
        io = getattr(self, "_writer_io", None)
        thread = getattr(self, "_writer", None)
        if io is None or thread is None or thread.ident is None:
            return
        from ._windows_io import stop_writer
        try:
            stop_writer(thread, io, self._transport_stop, self._write_condition)
        except (OSError, TimeoutError):
            # A failed control transport already invalidates this host. Retire
            # its process before retrying any CRT pipe close that could block.
            if self._process.poll() is None:
                self._process.terminate()
            thread.join(timeout=2)
            if thread.is_alive():
                raise TimeoutError("Windows host control writer cleanup unconfirmed")
            io.close()

    def _abandon(self, identifier, pending, task, error):
        with self._write_condition:
            unsent = task is None or (not task.started and task not in self._writes)
            if pending.ready.is_set() or unsent:
                self._pending.pop(identifier, None)
                value = pending.value if pending.ready.is_set() else error
                if unsent:
                    not_sent = TimeoutError("Control message was not submitted: " + str(error))
                    not_sent.submitted = False
                    value = not_sent
                self._refs += 1
                threading.Thread(target=self._late, args=(value, pending), daemon=True).start()
            else:
                pending.abandoned = True
                task.cancelled.set()
                self._write_condition.notify_all()
                self._cancel(identifier)

    def request(self, op, response_timeout=None, _cleanup=None, _cleanup_errors=True, **fields):
        from . import HostError, Busy, TransactionActive
        pending = _Reply()
        pending.cleanup, pending.op, pending.fields = _cleanup, op, fields
        with self._lock:
            if self._failure is not None:
                raise self._failure
            self._sequence += 1
            identifier = self._sequence
            self._pending[identifier] = pending
        started = time.monotonic()
        deadline = None if response_timeout is None else started+response_timeout
        send_deadline = min(started+5, deadline) if deadline is not None else started+5
        task = None
        try:
            task = _Write(dict(id=identifier, op=op, **fields), send_deadline)
            self._enqueue(task)
            if not task.written.wait(max(0, send_deadline-time.monotonic())) and not pending.ready.is_set():
                raise TimeoutError("Host control submission timed out; cleanup owns any late response")
            left = None if deadline is None else max(0, deadline-time.monotonic())
            ready = pending.ready.wait(left)
        except BaseException as exc:
            self._abandon(identifier, pending, task, exc)
            raise
        if not ready:
            with self._lock:
                if not pending.ready.is_set():
                    pending.abandoned = True
                    task.cancelled.set()
                    self._cancel(identifier)
                    # Keep the pending owner until the late reply is collected.
                    # A late created handle is closed by _read, not leaked.
                    raise TimeoutError("Host control response timed out; the request was cancelled")
        reply = pending.value
        if isinstance(reply, BaseException):
            if _cleanup is not None and _cleanup is not False:
                self._abandon(identifier, pending, task, reply)
            raise reply
        if not reply.get("ok"):
            error = reply.get("error", {})
            cls = {"busy": Busy, "transaction_active": TransactionActive}.get(error.get("code"), HostError)
            exc = cls(error.get("message", "Host request failed"), code=error.get("code"),
                      stage=error.get("stage"), closed=reply.get("closed", op in ("start", "fork")))
            exc.response = reply
            if _cleanup_errors and _cleanup is not False and (_cleanup is not None or any(k in reply for k in ("cleanup", "cleanup_handle", "database", "snapshot", "lease"))):
                self._abandon(identifier, pending, task, exc)
            raise exc
        return reply

    def _lines(self):
        data = b""
        while not self._transport_stop.is_set():
            if os.name != "nt" and not select.select([self._process.stdout.fileno()], [], [], .1)[0]:
                continue
            chunk = os.read(self._process.stdout.fileno(), 65536)
            if not chunk:
                return
            data += chunk
            while b"\n" in data:
                line, data = data.split(b"\n", 1)
                if len(line) > 1 << 20:
                    raise ValueError("oversized host response")
                yield line
            if len(data) > 1 << 20:
                raise ValueError("oversized host response")

    def _read(self):
        from . import HostError
        try:
            for line in self._lines():
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
                    threading.Thread(target=self._late, args=(value, pending), daemon=True).start()
            with self._lock:
                expected = self._closing and not self._pending
            if not expected:
                raise EOFError("host exited")
        except (OSError, ValueError, EOFError, HostError) as exc:
            self._fail(exc if isinstance(exc, HostError) else
                       HostError("Shared host terminated or sent invalid control data: " + str(exc),
                                 code="unusable", stage="host_control", closed=True))

    def _late(self, reply, pending=None):
        try:
            if pending is not None and pending.cleanup is not None:
                if pending.cleanup is not False:
                    pending.cleanup(reply)
                return
            if isinstance(reply, BaseException):
                return
            if "database" in reply:
                self.request("db_close", handle=reply["database"]["handle"], response_timeout=60, _cleanup=False)
            if "live" in reply:
                self.request("live_close", handle=reply["live"]["handle"], response_timeout=None, _cleanup=False)
            if "snapshot" in reply:
                self.request("snapshot_close", handle=reply["snapshot"], response_timeout=60, _cleanup=False)
            if "cleanup" in reply:
                self.request("cleanup_status", cleanup=reply["cleanup"], response_timeout=5, _cleanup=False)
            if "cleanup_handle" in reply:
                self.request("db_cleanup", handle=reply["cleanup_handle"], response_timeout=5, _cleanup=False)
            if pending is not None and "reservation" in reply:
                self.request("fork_cancel", handle=pending.fields["handle"], reservation=reply["reservation"], response_timeout=5, _cleanup=False)
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
            abandoned = []
            for pending in self._pending.values():
                pending.value = error
                pending.ready.set()
                if pending.abandoned:
                    self._refs += 1
                    abandoned.append(pending)
            self._pending.clear()
            self._transport_stop.set()
            self._write_condition.notify_all()
        for pending in abandoned:
            threading.Thread(target=self._late, args=(error, pending), daemon=True).start()
        if first_failure:
            try:
                threading.Thread(target=self._owner_eof, daemon=True).start()
            except RuntimeError:
                self._owner_eof()

    def _owner_eof(self):
        # Irrecoverable control failure invalidates the lineage. Stop admitting
        # work and ask its host to close all DBs, preserving logs until release.
        try:
            self._stop_windows_writer()
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
                self._stop_windows_writer()
                if not self._process.stdin.closed:
                    self._process.stdin.close()
                self._transport_stop.set()
                with self._write_condition:
                    self._write_condition.notify_all()
                try:
                    self._process.wait(timeout=45 if not force else 1)
                except subprocess.TimeoutExpired:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=12)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait(timeout=5)
                self._exited.set()
                from . import HostError
                self._fail(HostError("Host is closed", code="closed", stage="host_control", closed=True))
                if hasattr(self, "_reader") and self._reader.ident is not None and threading.current_thread() is not self._reader:
                    self._reader.join(timeout=5)
                self._process.stdout.close()
                if hasattr(self, "_writer") and self._writer.ident is not None and threading.current_thread() is not self._writer:
                    self._writer.join(timeout=5)
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
