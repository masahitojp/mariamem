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


def summarize_allocated(data, pid):
    """Exact fstat/libproc blocks, scoped to regular files still held by FDs."""
    if (type(data.get('pid')) is not int or data['pid'] != pid or
            type(data.get('fd_count')) is not int or not 0 < data['fd_count'] <= 4096 or
            not isinstance(data.get('fds'), list) or len(data['fds']) != data['fd_count']):
        raise ValueError('UNVERIFIED allocated descriptor census')
    descriptors, files = set(), {}
    for row in data['fds']:
        fd = row.get('fd')
        if type(fd) is not int or fd < 0 or fd in descriptors or type(row.get('regular')) is not bool:
            raise ValueError('UNVERIFIED duplicate/invalid descriptor')
        descriptors.add(fd)
        if not row['regular']:
            continue
        keys = ('device', 'inode', 'links', 'blocks', 'logical_bytes')
        if any(type(row.get(k)) is not int or row[k] < 0 for k in keys) or row['inode'] == 0:
            raise ValueError('UNVERIFIED regular-file allocation counters')
        if row['links'] == 0:
            identity = (row['device'], row['inode'])
            value = (row['blocks'] * 512, row['logical_bytes'])
            if identity in files and files[identity] != value:
                raise ValueError('UNVERIFIED file changed during allocation census')
            files[identity] = value
    return dict(pid=pid, fd_count=len(descriptors), unlinked_allocated_bytes=sum(v[0] for v in files.values()),
                unlinked_files=[dict(device=d, inode=i, allocated_bytes=v[0], logical_bytes=v[1])
                                for (d, i), v in sorted(files.items())])


def collect_allocated(pid, darwin_helper=None):
    """Read an explicit owned PID at a quiescent point; partial reads are errors."""
    import json
    import os
    import stat
    import sys
    if type(pid) is not int or pid <= 0:
        raise ValueError('positive explicit owned PID required')
    started = time.time_ns()
    if sys.platform == 'linux':
        directory = Path('/proc') / str(pid) / 'fd'
        entries = list(directory.iterdir())
        if not 0 < len(entries) <= 4096 or any(not p.name.isdecimal() for p in entries):
            raise ValueError('UNVERIFIED descriptor census missing or beyond 4096')
        rows = []
        for entry in entries:
            st = os.stat(entry)
            row = dict(fd=int(entry.name), regular=stat.S_ISREG(st.st_mode))
            if row['regular']:
                row.update(device=st.st_dev, inode=st.st_ino, links=st.st_nlink,
                           blocks=st.st_blocks, logical_bytes=st.st_size)
            rows.append(row)
        data = dict(pid=pid, fd_count=len(rows), fds=rows)
        raw = json.dumps(data).encode()
        mechanism = 'Linux /proc/PID/fd stat; st_blocks * 512'
        tool_sha256 = None
    elif sys.platform == 'darwin':
        if darwin_helper is None:
            raise ValueError('Darwin requires the separately built test-only allocation helper')
        result = subprocess.run([str(darwin_helper), str(pid)], capture_output=True, check=True, timeout=10)
        if result.stderr or len(result.stdout) > 1024 * 1024:
            raise ValueError('UNVERIFIED Darwin allocation output')
        raw = result.stdout
        data = json.loads(raw)
        mechanism = 'Darwin proc_pidfdinfo PROC_PIDFDVNODEINFO; vst_blocks * 512'
        tool_sha256 = hashlib.sha256(Path(darwin_helper).read_bytes()).hexdigest()
    else:
        raise ValueError('unsupported allocation observer platform')
    observed = summarize_allocated(data, pid)
    observed.update(start_unix_ns=started, end_unix_ns=time.time_ns(), mechanism=mechanism,
                    tool_sha256=tool_sha256,
                    limitations='FD-backed regular files only; not mmap-only storage, RSS, or an atomic process-tree census')
    return observed, raw


def merge_process_allocations(observations):
    """Deduplicate unlinked allocations across explicit, already sampled owners.

    The caller must independently establish process-tree completeness, stable
    ownership and sample alignment. An empty, partial or conflicting census is
    unverified, never an empty set or zero-byte observation.
    """
    if not isinstance(observations, dict) or not observations:
        raise ValueError('UNVERIFIED empty process allocation census')
    files = {}
    total_fds = 0
    for pid, observation in observations.items():
        if type(pid) is not int or pid <= 0 or not isinstance(observation, dict):
            raise ValueError('UNVERIFIED invalid process allocation owner')
        if observation.get('pid') != pid or type(observation.get('pid')) is not int:
            raise ValueError('UNVERIFIED process allocation identity')
        count = observation.get('fd_count')
        claimed = observation.get('unlinked_allocated_bytes')
        entries = observation.get('unlinked_files')
        if (type(count) is not int or count <= 0 or type(claimed) is not int or
                claimed < 0 or not isinstance(entries, list)):
            raise ValueError('UNVERIFIED incomplete process allocation census')
        local = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError('UNVERIFIED invalid allocated file')
            keys = ('device', 'inode', 'allocated_bytes', 'logical_bytes')
            if any(type(entry.get(k)) is not int or entry[k] < 0 for k in keys) or entry['inode'] == 0:
                raise ValueError('UNVERIFIED invalid allocated file counters')
            identity = (entry['device'], entry['inode'])
            value = (entry['allocated_bytes'], entry['logical_bytes'])
            if identity in local:
                raise ValueError('UNVERIFIED duplicate allocation in one process')
            if identity in files and files[identity] != value:
                raise ValueError('UNVERIFIED shared allocation changed during census')
            local[identity] = value
            files[identity] = value
        if sum(value[0] for value in local.values()) != claimed:
            raise ValueError('UNVERIFIED allocation subtotal mismatch')
        total_fds += count
    return dict(fd_total=total_fds, unlinked_allocated_bytes=sum(v[0] for v in files.values()),
                unlinked_files=[dict(device=d, inode=i, allocated_bytes=v[0], logical_bytes=v[1])
                                for (d, i), v in sorted(files.items())])


def validate_process_window(before, after, observations, *, max_window_ns):
    """Reject missing owners and non-overlapping or excessively long censuses.

    Stable endpoints do not exclude transient processes between snapshots; the
    campaign must hold owner transitions behind a barrier while this runs.
    """
    if (not isinstance(before, set) or not before or before != after or
            any(type(p) is not int or p <= 0 for p in before) or
            not isinstance(observations, dict) or set(observations) != before or
            type(max_window_ns) is not int or max_window_ns <= 0):
        raise ValueError('UNVERIFIED process-tree census or budget')
    starts=[]; ends=[]
    for pid, row in observations.items():
        if not isinstance(row, dict) or row.get('pid') != pid:
            raise ValueError('UNVERIFIED process allocation identity')
        start=row.get('start_unix_ns');end=row.get('end_unix_ns')
        if type(start) is not int or type(end) is not int or start <= 0 or end < start:
            raise ValueError('UNVERIFIED process observation timing')
        starts.append(start);ends.append(end)
    if max(ends)-min(starts)>max_window_ns:
        raise ValueError('UNVERIFIED process observation window exceeded')
    return dict(processes=sorted(before),start_unix_ns=min(starts),end_unix_ns=max(ends),
                max_window_ns=max_window_ns,atomic=False,
                limitation='stable endpoints do not exclude transient processes')
