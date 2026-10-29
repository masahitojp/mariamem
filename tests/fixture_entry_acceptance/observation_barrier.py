"""Test-only cooperative observation barrier for retained P1 owners.

An owner may acknowledge only after it has joined its own threads/tasks and
suspended every operation capable of creating, closing or transferring a process,
FD, connection, child or baseline. The barrier cannot enforce that promise for
uncooperative code or arbitrary descendants. Missing evidence fails closed.
"""
import json
import math
import secrets
import socket
import time

MAX_MESSAGE = 4096


class BarrierError(RuntimeError):
    pass


def _remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise BarrierError('observation barrier deadline exceeded')
    return value


def _send(channel, value, deadline):
    data = json.dumps(value, separators=(',', ':')).encode() + b'\n'
    if len(data) > MAX_MESSAGE:
        raise BarrierError('observation barrier message too large')
    channel.settimeout(_remaining(deadline))
    try:
        channel.sendall(data)
    except (OSError, TimeoutError) as error:
        raise BarrierError('observation barrier send failed') from error


def _receive(channel, deadline):
    # Read a byte at a time to avoid silently accepting extra framed messages.
    # Only two short messages per owner are sent at a checkpoint.
    data = bytearray()
    while len(data) < MAX_MESSAGE:
        channel.settimeout(_remaining(deadline))
        try:
            chunk = channel.recv(1)
        except (OSError, TimeoutError) as error:
            raise BarrierError('observation barrier receive failed') from error
        if not chunk:
            raise BarrierError('observation owner disconnected')
        if chunk == b'\n':
            try:
                result = json.loads(data)
            except (UnicodeDecodeError, ValueError) as error:
                raise BarrierError('invalid observation barrier message') from error
            if not isinstance(result, dict):
                raise BarrierError('invalid observation barrier message')
            return result
        data.extend(chunk)
    raise BarrierError('observation barrier message too large')


def owner_checkpoint(channel, park, *, timeout_seconds):
    """Park cooperatively until release; caller must terminate on an abort/error."""
    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError('finite positive timeout required')
    deadline = time.monotonic() + timeout_seconds
    command = _receive(channel, deadline)
    token = command.get('token')
    if set(command) != {'action', 'token'} or command['action'] != 'park' or not isinstance(token, str) or len(token) != 32:
        raise BarrierError('invalid park request')
    park()  # The owner is responsible for all quiescence before this returns.
    _send(channel, {'action': 'parked', 'token': token}, deadline)
    command = _receive(channel, deadline)
    if command != {'action': 'release', 'token': token}:
        raise BarrierError('observation aborted or invalid release')


def observe_parked(owners, observe, *, timeout_seconds):
    """Sample only after all owned subprocesses acknowledge the same fresh token.

    owners maps subprocess.Popen objects to private connected sockets. It is the
    caller's responsibility to terminate/reap owners after any failure. No
    normal release is sent if observation or an ownership check fails. The
    caller must bound observe independently; it cannot be interrupted here.
    A release send can fail after another owner was released, so cleanup must
    also handle partial release without declaring an atomic transition.
    """
    if (not isinstance(owners, dict) or not owners or type(timeout_seconds) not in (int, float)
            or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
        raise ValueError('nonempty owners and finite positive timeout required')
    if len({p.pid for p in owners}) != len(owners) or len(set(owners.values())) != len(owners):
        raise ValueError('duplicate observation owner or channel')
    deadline = time.monotonic() + timeout_seconds
    token = secrets.token_hex(16)
    released = False
    try:
        for process, channel in owners.items():
            if process.poll() is not None:
                raise BarrierError('observation owner already exited')
            _send(channel, {'action': 'park', 'token': token}, deadline)
        for process, channel in owners.items():
            if _receive(channel, deadline) != {'action': 'parked', 'token': token}:
                raise BarrierError('unexpected observation acknowledgement')
            if process.poll() is not None:
                raise BarrierError('observation owner exited before sampling')
        result = observe()
        _remaining(deadline)
        if any(process.poll() is not None for process in owners):
            raise BarrierError('observation owner exited during sampling')
        for channel in owners.values():
            _send(channel, {'action': 'release', 'token': token}, deadline)
        released = True
        return result
    finally:
        if not released:
            for channel in owners.values():
                try:
                    _send(channel, {'action': 'abort', 'token': token}, time.monotonic() + .1)
                except (BarrierError, OSError):
                    pass
