"""A full Windows pipe must not park its writer during owner shutdown."""
import os
import threading

import pytest

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='native Windows synchronous I/O cancellation')


def test_full_pipe_writer_is_cancelled_before_close():
    from mariamem._windows_io import WriterIO, stop_writer
    read_fd, write_fd = os.pipe()
    io = WriterIO()
    stop, entered, done = threading.Event(), threading.Event(), threading.Event()
    condition = threading.Condition()
    errors = []
    def write():
        try:
            io.register()
            entered.set()
            if not stop.is_set():
                os.write(write_fd, b'x' * (1 << 20))
        except OSError as error:
            errors.append(error)
        finally:
            io.close()
            done.set()
    writer = threading.Thread(target=write, daemon=True)
    try:
        writer.start()
        assert entered.wait(2)
        assert not done.wait(.1), 'the deliberately full pipe did not block'
        stop_writer(writer, io, stop, condition)
        assert done.is_set() and not writer.is_alive()
        assert errors, 'the blocked write was not interrupted'
    finally:
        stop.set()
        # Closing the reader is a last-resort test cleanup, never the production
        # cancellation oracle: it makes a failed cancellation test terminate.
        os.close(read_fd)
        writer.join(timeout=2)
        if not writer.is_alive():
            os.close(write_fd)
