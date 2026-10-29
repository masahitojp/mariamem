"""Test-only FD observer feasibility, not the P1 resource acceptance campaign."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import time


def parse_lsof(raw, expected_pids):
    """Count numeric descriptors; deduplicate FD-backed unlinked REG logical sizes.

    Non-numeric cwd/text/mapping records are outside this probe's byte counter.
    Logical size is not allocated blocks or physical memory. Missing data fails.
    """
    if not raw or not raw.endswith(b'\0\n'):
        raise ValueError('incomplete lsof framing')
    processes = {}
    files = {}
    pid = None
    current = None

    def flush():
        if current is None:
            return
        fd = current['f']
        if not fd.isdecimal():
            if fd[:1].isdecimal():
                raise ValueError('ambiguous numeric descriptor')
            return
        if pid is None or fd in processes[pid]:
            raise ValueError('missing process or duplicate descriptor')
        processes[pid].add(fd)
        if not current.get('t'):
            raise ValueError('missing descriptor type')
        if current['t'] == 'REG':
            try:
                device = int(current['D'], 16)
                inode, links, size = (int(current[k]) for k in ('i', 'k', 's'))
            except (KeyError, ValueError) as error:
                raise ValueError('unverified regular-file counter') from error
            if min(device, inode, links, size) < 0:
                raise ValueError('negative regular-file counter')
            if links == 0:
                identity = (device, inode)
                if identity in files and files[identity] != size:
                    raise ValueError('file changed during observation')
                files[identity] = size

    for token in raw.split(b'\0'):
        token = token.lstrip(b'\n')
        if not token:
            continue
        value = token[1:].decode('ascii')
        if token[:1] == b'p':
            flush()
            current = None
            pid = int(value)
            if pid in processes:
                raise ValueError('duplicate process')
            processes[pid] = set()
        elif token[:1] == b'f':
            flush()
            if pid is None:
                raise ValueError('descriptor precedes process')
            current = {'f': value}
        else:
            key = token[:1].decode('ascii')
            if current is None or key not in {'D', 'i', 'k', 's', 't'} or key in current:
                raise ValueError('unexpected or duplicate lsof field')
            current[key] = value
    flush()
    if set(processes) != set(expected_pids) or not all(processes.values()):
        raise ValueError('missing/unexpected process or empty descriptor census')
    return dict(fd_by_pid={str(p): len(fds) for p, fds in processes.items()},
                fd_total=sum(map(len, processes.values())),
                fd_backed_unlinked_logical_bytes=sum(files.values()),
                unlinked_files=[dict(device=d, inode=i, logical_bytes=s)
                                for (d, i), s in sorted(files.items())])


def collect(pids):
    pids = set(pids)
    if not pids or any(type(p) is not int or p <= 0 for p in pids):
        raise ValueError('positive explicit owned PIDs required')
    tool = shutil.which('lsof')
    if not tool:
        raise RuntimeError('lsof missing; resource counter UNVERIFIED')
    argv = [tool, '-nP', '-a', '-p', ','.join(map(str, sorted(pids))), '+L', '-F0pfDikst']
    started = time.time_ns()
    result = subprocess.run(argv, capture_output=True, timeout=10)
    if result.returncode != 0 or result.stderr:
        raise RuntimeError('lsof failed/warned; resource counter UNVERIFIED: ' +
                           result.stderr[-2048:].decode(errors='replace'))
    observed = parse_lsof(result.stdout, pids)
    observed.update(start_unix_ns=started, end_unix_ns=time.time_ns(),
                    mechanism='lsof numeric FDs; FD-backed unlinked regular-file logical size',
                    limitations='not allocated blocks, mmap-only files, physical memory or an atomic process-tree census',
                    tool=tool, tool_sha256=hashlib.sha256(Path(tool).read_bytes()).hexdigest())
    return observed, result.stdout
