"""Private owner of a source-host slot while a different host owns its DB."""
import shutil
import threading
import weakref


class RemoteLease:
    def __init__(self, parent, source, handle, reservation, scratch, target):
        self._lock = threading.RLock()
        self.parent = weakref.ref(parent)
        self.source, self.handle, self.reservation = source, handle, reservation
        self.scratch, self.target = scratch, target
        self.exported = False
        self.target_handle = self.cleanup_token = None
        self.target_done = self.done = False
        self.error = None
        self.log_path, self.owned_log = None, False
        self._source_held = True
        self._watching = set()
        self._blocking = False
        with source._lock:
            source._handoffs.add(self)

    def remove_scratch(self):
        try:
            shutil.rmtree(self.scratch)
        except FileNotFoundError:
            pass

    def _source_request(self, op):
        return self.source.request(op, handle=self.handle, reservation=self.reservation,
                                   response_timeout=5, _cleanup=False)

    def _drop_source(self):
        with self.source._lock:
            self.source._handoffs.discard(self)
        if self._source_held:
            self._source_held = False
            self.source.release()

    def _block(self, cause):
        from . import HostError
        self.error = HostError("Remote child cleanup is not confirmed; retry closing its owner. Cause: " + str(cause),
                               code="unusable", stage="fork_cleanup", closed=True)
        self.error.__cause__ = cause
        parent = self.parent()
        if parent is not None:
            with parent._lock:
                parent._admission_error = HostError(str(self.error), code="unusable",
                                                     stage="fork_admission", closed=False)
                parent._debt_version += 1
        if self.exported and not self._blocking and not self.source.failed:
            self._blocking = True
            def block():
                try:
                    self._source_request("handoff_abandon")
                except Exception:
                    pass  # The local latch and issued lease remain owned.
            threading.Thread(target=block, daemon=True).start()

    def _after_exit(self, session):
        if session in self._watching:
            return
        self._watching.add(session)
        def joined():
            session._exited.wait()
            try:
                self.retry()
            except Exception:
                pass  # Keep the owner/debt for an explicit retry.
        threading.Thread(target=joined, daemon=True).start()

    def _clean_exited_target(self):
        # A transport failure alone is insufficient. Execution must have exited.
        if not self.target._exited.is_set():
            raise RuntimeError("target process has not exited")
        for path in self.target.root.iterdir() if self.target.root.exists() else ():
            if path.name.startswith(("mariamem-transfer-", "mariamem-import-")):
                try:
                    shutil.rmtree(path)
                except FileNotFoundError:
                    pass
        if self.owned_log and self.log_path is not None:
            self.log_path.unlink(missing_ok=True)
        self.target_done = True

    def _settle(self):
        if not self.target_done:
            raise RuntimeError("target disposal is not confirmed")
        if self.source.failed and not self.source._exited.is_set():
            self._after_exit(self.source)
            raise RuntimeError("source process exit is not confirmed")
        self.remove_scratch()
        if self.owned_log and self.log_path is not None:
            self.log_path.unlink(missing_ok=True)
        if self.source.failed:
            if not self.source._exited.is_set():
                self._after_exit(self.source)
                raise RuntimeError("source process exit is not confirmed")
        else:
            state = self._source_request("handoff_release" if self.exported else "fork_cancel")
            if self.exported and state.get("disposed") is not True:
                raise RuntimeError("source lease settlement was not acknowledged")
        self.done = True
        self._drop_source()

    def finish(self, reply):
        with self._lock:
            if self.done:
                return
            if reply.get("disposed") is True:
                self.target_done = True
            self.target_handle = reply.get("cleanup_handle", self.target_handle)
            self.cleanup_token = reply.get("cleanup", self.cleanup_token)
            try:
                if not self.target_done:
                    self._retry_target()
                self._settle()
            except BaseException as exc:
                self._block(exc)
                self._after_exit(self.target if not self.target_done else self.source)
                raise self.error from exc

    def _retry_target(self):
        if self.target._exited.is_set():
            self._clean_exited_target()
            return
        if self.cleanup_token is not None:
            state = self.target.request("cleanup_status", cleanup=self.cleanup_token,
                                        response_timeout=5, _cleanup=False)
        elif self.target_handle is not None:
            state = self.target.request("db_cleanup", handle=self.target_handle,
                                        response_timeout=5, _cleanup=False)
        else:
            raise RuntimeError("waiting for the late target startup result")
        if state.get("disposed") is not True:
            raise RuntimeError("target cleanup remains incomplete")
        self.target_done = True

    def retry(self):
        with self._lock:
            if self.done:
                return
            if not self.target_done:
                self._retry_target()
            self._settle()

    def parent_closed(self):
        with self._lock:
            if not self.target_done and self.target._exited.is_set():
                try:
                    self._clean_exited_target()
                except OSError as exc:
                    self._block(exc)
            # A closed parent cannot reuse its counter. Once the target and
            # scratch are gone, a lost acknowledgement retains only the host's
            # issued record; final Session EOF reaps it. Never do this for a
            # live/unknown target, and never count this as a slot release.
            if self.target_done and self.error is not None:
                try:
                    self._settle()
                except Exception as exc:
                    self._block(exc)
                    # The target is disposed and this parent is closed. Keep
                    # any issued host record for EOF cleanup, without retaining
                    # the origin process solely for an acknowledgement.
                    if self.source.failed and not self.source._exited.is_set():
                        self._drop_source()
                        return
                    try:
                        self.remove_scratch()
                    except OSError:
                        return
                    self._drop_source()

    def late_export(self, reply):
        with self._lock:
            if self.done:
                return
            try:
                if isinstance(reply, BaseException):
                    if not getattr(reply, "submitted", True):
                        self.target_done = True
                    elif self.source._exited.is_set():
                        self.target_done = True
                    else:
                        self._after_exit(self.source)
                        raise reply
                else:
                    self.exported = "lease" in reply
                    if "cleanup" in reply:
                        state = self.source.request("cleanup_status", cleanup=reply["cleanup"],
                                                    response_timeout=5, _cleanup=False)
                        if state.get("disposed") is not True:
                            raise RuntimeError("source export cleanup remains incomplete")
                    self.target_done = True  # A late export never starts a target.
                self._settle()
            except BaseException as exc:
                self._block(exc)
                self._after_exit(self.source)

    def late_start(self, reply):
        with self._lock:
            if self.done:
                return
            try:
                if isinstance(reply, BaseException):
                    if not getattr(reply, "submitted", True):
                        self.target_done = True
                        self._settle()
                        return
                    raise reply
                if "database" in reply:
                    self.target_handle = reply["database"]["handle"]
                    reply = self.target.request("db_close", handle=self.target_handle,
                                                response_timeout=5, _cleanup=False)
                self.finish(reply)
            except BaseException as exc:
                self._block(exc)
                self._after_exit(self.target)

    def late_close(self, reply):
        try:
            if isinstance(reply, BaseException):
                raise reply
            self.finish(reply)
        except BaseException as exc:
            with self._lock:
                self._block(exc)
                self._after_exit(self.target)

    def late_capture(self, reply):
        # A precondition rejection preserves the target and its source lease.
        if isinstance(reply, dict) and not reply.get("closed"):
            return
        if isinstance(reply, dict) and "snapshot" in reply:
            try:
                self.target.request("snapshot_close", handle=reply["snapshot"],
                                    response_timeout=5, _cleanup=False)
            except Exception as exc:
                with self._lock:
                    self._block(exc)
                return
        self.late_close(reply)
