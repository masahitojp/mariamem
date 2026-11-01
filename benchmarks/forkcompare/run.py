"""Copy to workspace evidence/run.py; Issue68: bounded wait-stack and client-wire diagnostic."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

W = Path(__file__).resolve().parents[1]
C, T, E = W / 'worktree', W / 'temp', W / 'evidence'
B = C / 'benchmarks/forkcompare'
sys.path.insert(0, str(C / 'scripts'))
from git_identity import ReleasePin, require_commit, verify_release_pin
from experiment_disk import DiskGuard, run_guarded, stop_group


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Darwin SDK sys/resource.h: rusage_info_v0, flavor RUSAGE_INFO_V0.
class Usage(ctypes.Structure):
    _fields_ = [('uuid', ctypes.c_uint8 * 16)] + [(n, ctypes.c_uint64) for n in
        ('user_time', 'system_time', 'pkg_idle_wkups', 'interrupt_wkups',
         'pageins', 'wired_size', 'resident_size', 'phys_footprint',
         'proc_start_abstime', 'proc_exit_abstime')]


libproc = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
libproc.proc_pid_rusage.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
libproc.proc_pid_rusage.restype = ctypes.c_int


def rss(pid):
    usage = Usage()
    if libproc.proc_pid_rusage(pid, 0, ctypes.byref(usage)) != 0:
        raise OSError(ctypes.get_errno(), 'proc_pid_rusage')
    return usage.resident_size


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['build', 'pilot', 'measure'], required=True)
    args = parser.parse_args()
    pins = json.loads((B / 'source-pins.json').read_text())
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=C, text=True).strip()
    require_commit(C, commit)
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=C)
    for name, directory in [('mariamem', 'product')]:
        pin = ReleasePin(**pins[name])
        verify_release_pin(T / directory, pin)
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=T / directory, text=True).strip() == pin.source_commit
        assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=T / directory)
    env = {k: v for k, v in os.environ.items() if not k.startswith(
        ('MARIAMEM_', 'MYSQLMEM_', 'GODEBUG', 'GOMEMLIMIT', 'GOGC', 'GOFLAGS'))}
    env.update(GOTOOLCHAIN='local', CGO_ENABLED='0', GOMAXPROCS='8',
               GOCACHE=str(T / 'go-cache'), GOMODCACHE=str(T / 'go-mod'),
               GOTMPDIR=str(T / 'go-tmp'), TMPDIR=str(T / 'scratch'))
    for name in ['go-cache', 'go-mod', 'go-tmp', 'scratch', 'bin']:
        (T / name).mkdir(parents=True, exist_ok=True)
    version = subprocess.check_output(['go', 'version'], env=env, text=True).strip()
    assert version == 'go version go1.27.3 darwin/arm64'
    guard = DiskGuard(W, min_free_gib=16, budget_gib=8)
    if args.phase == 'build':
        subprocess.run([sys.executable,str(B/'overlay.py')],check=True)
        overlay_hashes=json.loads((E/'overlay-hashes.json').read_text())
        inputs = dict(harness_source_commit=commit, products=pins, go=version,
                      os=platform.mac_ver()[0], cpu='Apple M1', memory_bytes=17179869184,
                      plan=json.loads((B / 'plan.json').read_text()), overlay_hashes=overlay_hashes, binaries={})
        for name, package in [('mariamem', 'maria')]:
            binary = T / 'bin' / name
            with (E / ('build-' + name + '.txt')).open('w') as log:
                code = run_guarded(['go', 'build', '-overlay', str(T/'overlay.json'), '-p', '1', '-mod=readonly', '-trimpath',
                                    '-buildvcs=true', '-o', str(binary), './' + package],
                                   guard, cwd=B, env=env, output=log, timeout=1200)
            assert code == 0, name
            info = subprocess.check_output(['go', 'version', '-m', binary], env=env, text=True)
            assert 'vcs.revision=' + commit in info and 'vcs.modified=false' in info
            inputs['binaries'][name] = dict(sha256=sha(binary), build_info=info.replace(str(W), '<WORKSPACE>'))
            print('BUILD PASS', name, flush=True)
        save(E / 'inputs.json', inputs)
        return
    inputs = json.loads((E / 'inputs.json').read_text())
    assert inputs['harness_source_commit'] == commit
    for name, info in inputs['binaries'].items():
        assert sha(T / 'bin' / name) == info['sha256']
    # Sanity check the ABI against ps once, outside measurement.
    own_rss = rss(os.getpid())
    ps_rss = int(subprocess.check_output(['ps', '-o', 'rss=', '-p', str(os.getpid())])) * 1024
    assert abs(own_rss - ps_rss) < 8 * 1024**2 and own_rss > 0
    save(E / (args.phase + '-sampler.json'), dict(libproc_rss=own_rss, ps_rss=ps_rss, interval_ms=20))
    records = []

    def run(name, p, rep, count=48, negative=False, warmup=False, delayed=False):
        label = f'{args.phase}-v2/{rep}-{name}-p{p}' + ('-negative' if negative else '-delayed' if delayed else '-warmup' if warmup else '')
        out = E / (label + '.json')
        out.parent.mkdir(parents=True, exist_ok=True)
        sync = T / 'sync' / label
        scratch = T / 'scratch' / label
        sync.mkdir(parents=True)
        scratch.mkdir(parents=True)
        stacks=E/(label+'-stacks');stacks.mkdir(parents=True)
        cmd = [str(T / 'bin' / name), '-out', str(out), '-stacks',str(stacks), '-route', 'tcp', '-parallel', str(p),
               '-count', str(count), '-sync-dir', str(sync)] + (['-corrupt-seed'] if negative else []) + (['-delay-probe'] if delayed else [])
        guard.check()
        process = None
        samples = []
        baseline = None
        with (E / (label + '.stderr.txt')).open('w') as log:
            try:
                process = subprocess.Popen(cmd, cwd=B, env=dict(env, TMPDIR=str(scratch)),
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + 100
                while not (sync / 'ready').exists():
                    assert process.poll() is None and time.monotonic() < deadline, 'no ready handshake'
                    time.sleep(.02)
                baseline = rss(process.pid)
                begin = time.monotonic()
                (sync / 'go').write_text('go')
                while not (sync / 'done').exists():
                    assert time.monotonic() < deadline, 'batch timeout'
                    if process.poll() is not None:
                        raise RuntimeError('process exited before batch done')
                    samples.append(dict(offset_ms=(time.monotonic() - begin) * 1000, rss_bytes=rss(process.pid)))
                    time.sleep(.02)
                process.wait(timeout=30)
                code = process.returncode
            finally:
                if process is not None:
                    stop_group(process)
        guard.check()
        d = json.loads(out.read_text())
        trace=json.loads(Path(str(out)+'.trace.json').read_text())
        assert trace['dropped']==0 and trace['events']
        assert any(x['kind']=='pread_begin' for x in trace['events'])
        assert any(x['kind']=='task_start' for x in trace['events'])
        assert d['cleanup_complete'] and not any(scratch.iterdir())
        assert d['root_closed_before_forks'] and d['gomaxprocs'] == 8 and d['parallel'] == p
        if negative:
            assert code != 0 and not d['success'] and 'pristine oracle' in d['error']
        else:
            assert code == 0 and d['success'] and len(d['samples']) == count
            assert {s['index'] for s in d['samples']} == set(range(count))
            assert all(s['oracle'] and s['cleanup_complete'] for s in d['samples'])
        events = sorted([(s['offset_ms'], 1) for s in d['samples']] +
                        [(s['offset_ms'] + s['total_ms'], -1) for s in d['samples']])
        active = peak = 0
        for _, delta in events:
            active += delta
            peak = max(peak, active)
        assert active == 0 and peak <= p
        if not negative:
            assert peak == p
        if delayed:
            assert list(stacks.glob('*.json')) and list(stacks.glob('*.txt'))
        memory = dict(baseline_rss_bytes=baseline, sampled_peak_rss_bytes=max(s['rss_bytes'] for s in samples),
                      interval_ms=20, samples=samples, observed_peak_active_children=peak)
        save(E / (label + '-memory.json'), memory)
        records.append(dict(backend=name, parallel=p, repetition=rep, negative=negative,
                            warmup=warmup, delayed=delayed, count=count, report=label + '.json', memory=label + '-memory.json', returncode=code))
        save(E / (args.phase + '-records.json'), records)
        print('PASS', label, round(d['batch_ms'], 2), 'ms', flush=True)

    if args.phase == 'pilot':
        run('mariamem',1,0,1)
        run('mariamem',8,0,8)
        save(E/'completion.json',dict(result='PASS',processes=2,normal_children=9,scope='Trace concurrency source, no policy changes'))
    else:
        raise RuntimeError('No expanded campaign authorized by this plan')

if __name__ == '__main__':
    main()
