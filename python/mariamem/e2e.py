"""Owned, sequential browser cases over an application-specific Live target.

Playwright is supplied by the caller; it is not a mariamem dependency. Hooks
must cooperate with deadlines and retire physical SQL sessions before Reset.
"""
import math
import threading
import time
from dataclasses import dataclass, field
from types import MappingProxyType


class EntryError(RuntimeError):
    def __init__(self, stage, admission, cleanup="not-attempted"):
        self.stage, self.admission, self.cleanup = stage, admission, cleanup
        super().__init__(f"E2E {stage}; admission={admission}; cleanup={cleanup}. "
                         "Inspect the original cause; close the owner before retrying.")


class HookContext:
    """Cooperative deadline. A hook must join its work before returning."""
    def __init__(self, timeout):
        self.deadline = time.monotonic() + timeout

    def remaining(self):
        self.check()
        return self.deadline - time.monotonic()

    def check(self):
        if time.monotonic() >= self.deadline:
            raise TimeoutError("E2E hook deadline expired")


@dataclass(frozen=True)
class Config:
    prepare: object
    start_ready: object
    sole_work_source: bool = False
    resume: object = None
    external_state: object = None
    options: object = field(default_factory=dict)
    setup_timeout: float = 120
    reset_timeout: float = 120
    drain_timeout: float = 5
    cleanup_timeout: float = 30

    def __post_init__(self):
        for name in ("prepare", "start_ready"):
            if not callable(getattr(self, name)):
                raise ValueError(f"{name} must be callable")
        for name in ("resume", "external_state"):
            if getattr(self, name) is not None and not callable(getattr(self, name)):
                raise ValueError(f"{name} must be callable or None")
        if self.resume is None and self.sole_work_source is not True:
            raise ValueError("declare sole_work_source=True or supply resume")
        for name in ("setup_timeout", "reset_timeout", "drain_timeout", "cleanup_timeout"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        object.__setattr__(self, "options", MappingProxyType(dict(self.options)))


def _raise(original, cleanups):
    if not cleanups:
        raise original
    group = BaseExceptionGroup("E2E cleanup failures", cleanups)
    if not isinstance(original, Exception):
        raise original from group
    raise BaseExceptionGroup("E2E operation and cleanup failed", [original, group])


class BrowserEntry:
    """Use as a session fixture; each case owns a fresh browser context.

    prepare(source) closes its connections. start_ready(ctx, target, register)
    registers partial handles before failure and returns a registered app with
    identity, base_url, quiesce_and_retire(ctx), and stop_reap(ctx).
    """
    def __init__(self, config):
        if not isinstance(config, Config):
            raise TypeError("config must be Config")
        self.config = config
        self._condition = threading.Condition()
        self._close_lock = threading.Lock()
        self._active = None
        self._failed = self._closing = self._closed = False
        self._started = False
        self._apps = []
        self._source = self._baseline = self._live = self.app = None
        self.cleanup_errors = []
        self._close_errors = []

    def _register_app(self, app):
        if self._active != threading.get_ident() or self.app is not None:
            raise EntryError("app_register", "stopped")
        # Retain even a malformed partial handle; shutdown will report uncertainty.
        if app is None or any(app is item for item in self._apps):
            raise ValueError("register one unique non-None app handle")
        self._apps.append(app)
        for name in ("quiesce_and_retire", "stop_reap"):
            if not callable(getattr(app, name, None)):
                raise ValueError(f"app requires {name}")

    def __enter__(self):
        with self._condition:
            if self._started or self._closing:
                raise EntryError("start", "stopped")
            self._started = True
            self._active = threading.get_ident()
        try:
            from . import start
            ctx = HookContext(self.config.setup_timeout)
            self._source = start(**self.config.options)
            ctx.check()
            self.config.prepare(self._source)
            ctx.check()
            self._source.wait_disconnected(timeout=min(self.config.drain_timeout, ctx.remaining()))
            ctx.check()
            self._baseline = self._source.snapshot(timeout=ctx.remaining())
            self._live = self._baseline.live()
            ctx.check()
            self._target = self._live.connection_info()
            self.app = self.config.start_ready(ctx, dict(self._target), self._register_app)
            ctx.check()
            if not any(self.app is item for item in self._apps):
                raise ValueError("start_ready must return a registered app")
            self._identity = self.app.identity
            if not self._identity or not self.app.base_url:
                raise ValueError("ready app requires identity and base_url")
            return self
        except BaseException as original:
            self._failed = True
            self._release()
            errors = self._close_collect()
            _raise(original, errors)
        finally:
            self._release()

    def _release(self):
        with self._condition:
            self._active = None
            self._condition.notify_all()

    def case(self, *, browser):
        return _BrowserCase(self, browser)

    def _close_collect(self):
        with self._condition:
            if self._active == threading.get_ident():
                raise EntryError("close_during_case", "stopped", "unconfirmed")
            self._closing = True
            deadline = time.monotonic() + self.config.cleanup_timeout
            while self._active is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._failed = True
                    raise EntryError("close_wait", "stopped", "unconfirmed")
                self._condition.wait(remaining)
        with self._close_lock:
            if self._closed:
                return list(self._close_errors)
            errors = []
            ctx = HookContext(self.config.cleanup_timeout)
            for app in reversed(self._apps):
                try:
                    app.stop_reap(ctx)
                    ctx.check()
                except BaseException as error:
                    errors.append(error)
            for resource in (self._live, self._baseline, self._source):
                if resource is not None:
                    try:
                        resource.close()
                    except BaseException as error:
                        errors.append(error)
            self.cleanup_errors.extend(errors)
            self._close_errors = errors
            self._closed = True
            self._failed |= bool(errors)
            return list(errors)

    def close(self):
        errors = self._close_collect()
        if errors:
            raise BaseExceptionGroup("E2E owner cleanup unconfirmed", errors)

    def __exit__(self, kind, original, traceback):
        errors = self._close_collect()
        if original is not None:
            if errors:
                _raise(original, errors)
            return False
        if errors:
            raise BaseExceptionGroup("E2E owner cleanup unconfirmed", errors)


class _BrowserCase:
    def __init__(self, owner, browser):
        self.owner, self.browser = owner, browser
        self._resources = []
        self._entered = False
        self._finished = False
        self.app = self.page = None

    def register(self, resource):
        """Register a case resource with close() immediately after allocation."""
        if not self._entered or self._finished:
            raise EntryError("case_register", "stopped")
        if any(resource is item for item in self._resources):
            raise ValueError("duplicate case resource")
        self._resources.append(resource)
        if not callable(getattr(resource, "close", None)):
            raise ValueError("case resource requires close")
        return resource

    def __enter__(self):
        o = self.owner
        with o._condition:
            if self._entered or o._failed or o._closing or not o._started or o._live is None:
                raise EntryError("case_admission", "stopped")
            if o._active is not None:
                raise EntryError("case_overlap", "rejected")
            o._active = threading.get_ident()
            self._entered = True
        stage = "quiesce"
        try:
            ctx = HookContext(o.config.setup_timeout)
            o.app.quiesce_and_retire(ctx)
            ctx.check()
            stage = "reset"
            before = o._live.status()
            o._live.reset(timeout=o.config.reset_timeout, drain_timeout=o.config.drain_timeout)
            after = o._live.status()
            if (after["state"] != "ready" or after["generation"] != before["generation"] + 1
                    or o._live.connection_info() != o._target or o.app.identity != o._identity):
                raise EntryError("identity", "stopped")
            ctx.check()
            stage = "resume"
            if o.config.resume is not None:
                o.config.resume(ctx, o.app)
                ctx.check()
            stage = "external_state"
            if o.config.external_state is not None:
                o.config.external_state(ctx, o.app, self.register)
                ctx.check()
            stage = "browser_context"
            context = self.register(self.browser.new_context())
            self.page = context.new_page()
            ctx.check()
            self.app = o.app
            return self
        except BaseException as original:
            o._failed = True
            errors = self._finish()
            if isinstance(original, Exception):
                failure = EntryError(stage, "stopped", "unconfirmed" if errors else "case-cleaned")
                failure.__cause__ = original
                _raise(failure, errors)
            _raise(original, errors)

    def _finish(self):
        if self._finished:
            return []
        self._finished = True
        errors = []
        try:
            for resource in reversed(self._resources):
                try:
                    resource.close()
                except BaseException as error:
                    errors.append(error)
            if errors:
                self.owner._failed = True
                self.owner.cleanup_errors.extend(errors)
        finally:
            self.owner._release()
        return errors

    def __exit__(self, kind, original, traceback):
        errors = self._finish()
        if original is not None:
            if errors:
                _raise(original, errors)
            return False
        if errors:
            raise BaseExceptionGroup("E2E case cleanup unconfirmed", errors)
