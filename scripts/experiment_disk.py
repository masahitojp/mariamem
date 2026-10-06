#!/usr/bin/env python3
"""Disk-only guard for owned experiment output; never starts a guest itself."""
import argparse
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

GIB = 1 << 30


class DiskLimit(RuntimeError):
    pass


class ProcessStopError(DiskLimit):
    """Owned children could not be confirmed stopped; retain their scratch."""


def signal_group(group, signum):
    try:
        os.killpg(group, signum)
    except ProcessLookupError:
        return
    except PermissionError:
        # A group can disappear or contain only zombies between signals.
        # Ignore denial only when a process snapshot confirms no live member.
        rows = subprocess.check_output(['ps', '-A', '-o', 'pgid=,stat='], text=True)
        members = [row.split()[1] for row in rows.splitlines()
                   if len(row.split()) == 2 and row.split()[0] == str(group)]
        if any(not state.startswith('Z') for state in members):
            raise


def allocated_bytes(path):
    """Count allocated blocks once per inode, without following links."""
    path = Path(path)
    if path.is_symlink() or not path.exists():
        return 0
    if path.is_file():
        st = path.stat()
        return getattr(st, 'st_blocks', (st.st_size + 511) // 512) * 512
    total, seen = 0, set()
    for parent, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(parent) / d).is_symlink()]
        for name in files:
            try:
                st = (Path(parent) / name).lstat()
            except FileNotFoundError:
                continue  # Compiler temporary files can disappear during a sample.
            key = (st.st_dev, st.st_ino)
            if key not in seen:
                seen.add(key)
                total += getattr(st, 'st_blocks', (st.st_size + 511) // 512) * 512
    return total


class DiskGuard:
    def __init__(self, work_dir, min_free_gib=8, budget_gib=2):
        if not all(math.isfinite(v) and v > 0 for v in (min_free_gib, budget_gib)):
            raise ValueError('disk thresholds must be finite and positive')
        self.work_dir = Path(work_dir).absolute()
        if self.work_dir.resolve() != self.work_dir:
            raise ValueError('work directory has a symlink ancestor; use its real path')
        self.floor = int(min_free_gib * GIB)
        self.budget = int(budget_gib * GIB)
        self.peak = 0
        self.minimum_free = None

    def check(self):
        if self.work_dir.resolve() != self.work_dir or self.work_dir.is_symlink():
            raise DiskLimit('work directory changed to a symlink')
        parent = self.work_dir
        while not parent.exists():
            parent = parent.parent
        free = shutil.disk_usage(parent).free
        used = allocated_bytes(self.work_dir)
        self.peak = max(self.peak, used)
        self.minimum_free = min(free, self.minimum_free if self.minimum_free is not None else free)
        if free < self.floor or used > self.budget:
            raise DiskLimit(
                f'disk guard stopped: free={free/GIB:.2f} GiB (minimum {self.floor/GIB:.2f}), '
                f'owned output={used/GIB:.2f} GiB (budget {self.budget/GIB:.2f}). '
                'Run scripts/experiment_workspace.py cleanup in dry-run mode; '
                'preserve compact evidence and inspect REVIEW items before --apply. '
                'After their users stop, discard recreatable caches; retain only unique evidence/active state.')
        return {'owned_bytes': used, 'free_bytes': free, 'peak_owned_bytes': self.peak,
                'minimum_free_bytes': self.minimum_free}


def stop_group(process):
    signal_group(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    # Also stop descendants that outlive the process-group leader.
    signal_group(process.pid, signal.SIGKILL)
    process.wait()


def run_guarded(command, guard, *, cwd=None, env=None, output=None, interval=0.5, timeout=900):
    if not command or not all(math.isfinite(v) and v > 0 for v in (interval, timeout)):
        raise ValueError('command, positive interval and timeout are required')
    guard.check()  # Fail before spawning anything.
    previous = signal.getsignal(signal.SIGTERM)

    def interrupted(signum, frame):
        raise DiskLimit('experiment interrupted; owned child group will be stopped')

    signal.signal(signal.SIGTERM, interrupted)
    process = None
    try:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=output,
                                   stderr=subprocess.STDOUT if output is not None else None,
                                   start_new_session=True)
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            guard.check()
            if time.monotonic() >= deadline:
                raise DiskLimit('experiment watchdog stopped the owned child group')
            time.sleep(interval)
        guard.check()
        return process.returncode
    finally:
        try:
            if process is not None:
                try:
                    stop_group(process)
                except BaseException as exc:
                    raise ProcessStopError('cannot confirm child-group shutdown; retain scratch for manual review') from exc
        finally:
            signal.signal(signal.SIGTERM, previous)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--min-free-gib', type=float, default=8)
    parser.add_argument('--budget-gib', type=float, default=2)
    parser.add_argument('--timeout', type=float, default=900)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    try:
        guard = DiskGuard(args.work_dir, args.min_free_gib, args.budget_gib)
        stats = guard.check()
        print(f'Disk preflight OK: {stats["free_bytes"]/GIB:.2f} GiB free, '
              f'{stats["owned_bytes"]/GIB:.2f} GiB owned', flush=True)
        return run_guarded(command, guard, timeout=args.timeout) if command else 0
    except (DiskLimit, ValueError, OSError, KeyboardInterrupt) as exc:
        print(str(exc), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
