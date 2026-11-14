"""Owned Windows thread handle for bounded cancellation of a pipe writer."""
import ctypes
from ctypes import wintypes
import threading
import time

_kernel = ctypes.WinDLL('kernel32', use_last_error=True)
_kernel.GetCurrentThreadId.argtypes = []
_kernel.GetCurrentThreadId.restype = wintypes.DWORD
_kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel.OpenThread.restype = wintypes.HANDLE
_kernel.CancelSynchronousIo.argtypes = [wintypes.HANDLE]
_kernel.CancelSynchronousIo.restype = wintypes.BOOL
_kernel.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel.CloseHandle.restype = wintypes.BOOL


class WriterIO:
    def __init__(self):
        self._lock = threading.Lock()
        self._handle = None

    def register(self):
        # Open from the writer itself. Keeping the handle until that thread
        # closes it prevents a recycled thread ID from targeting unrelated I/O.
        with self._lock:
            handle = _kernel.OpenThread(1, False, _kernel.GetCurrentThreadId())
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            self._handle = handle

    def cancel(self):
        with self._lock:
            if self._handle is not None and not _kernel.CancelSynchronousIo(self._handle):
                error = ctypes.get_last_error()
                if error != 1168:  # ERROR_NOT_FOUND: no synchronous I/O pending.
                    raise ctypes.WinError(error)

    def close(self):
        with self._lock:
            if self._handle is not None:
                if not _kernel.CloseHandle(self._handle):
                    raise ctypes.WinError(ctypes.get_last_error())
                self._handle = None


def stop_writer(thread, io, stop, condition, timeout=2):
    stop.set()
    with condition:
        condition.notify_all()
    if thread is threading.current_thread():
        io.close()
        return
    deadline = time.monotonic() + timeout
    while thread.is_alive():
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError('Windows control writer did not stop')
        # Cancel may run just before WriteFile enters the kernel. Repeat until
        # the dedicated thread exits; it cannot begin another frame after stop.
        io.cancel()
        thread.join(timeout=min(.01, left))
    io.close()
