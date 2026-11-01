"""Bounded Darwin per-Fork resources; invoke from the owned workspace evidence dir."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import selectors
import shutil
import subprocess
import sys
import time

W = Path(__file__).resolve().parents[1]
C, T, E = W / 'worktree', W / 'temp', W / 'evidence'
sys.path.insert(0, str(C / 'scripts'))
from git_identity import ReleasePin, require_commit, verify_release_pin


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['build', 'pilot', 'matrix'], required=True)
    phase = parser.parse_args().phase
    source = C / 'benchmarks/forkresources'
    pins = json.loads((source / 'source-pins.json').read_text())
    for label, leaf in [('mariamem', 'product'), ('pgmem', 'pgmem')]:
        root = T / leaf
        pin = pins[label]
        verify_release_pin(root, ReleasePin(**pin))
        require_commit(root, pin['source_commit'])
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == pin['source_commit']
        assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=C, text=True).strip()
    require_commit(C, commit)
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=C, text=True), 'commit harness first'
    env = {k: v for k, v in os.environ.items() if not k.startswith(('MARIAMEM_', 'MYSQLMEM_', 'MODELCASE_', 'GODEBUG', 'GOMEMLIMIT', 'GOGC', 'GOFLAGS'))}
    env.update(GOTOOLCHAIN='local', CGO_ENABLED='0', GOMAXPROCS='8', GOCACHE=str(T / 'go-cache'),
               GOMODCACHE=str(T / 'go-mod'), GOTMPDIR=str(T / 'go-tmp'), TMPDIR=str(T / 'scratch'))
    for leaf in ['go-cache', 'go-mod', 'go-tmp', 'scratch', 'bin']:
        (T / leaf).mkdir(exist_ok=True)
    go = shutil.which('go')
    version = subprocess.check_output([go, 'version'], env=env, text=True).strip()
    assert version == 'go version go1.27.3 darwin/arm64'
    if phase == 'build':
        inputs = dict(sources=pins, harness_source_commit=commit, go=version, gomaxprocs=8, cgo_enabled=0,
                      host=dict(cpu='Apple M1', ram_bytes=17179869184, os=platform.mac_ver()[0], architecture=platform.machine()),
                      plan=json.loads((source / 'plan.json').read_text()), binaries={},
                      source_hashes={str(p.relative_to(source)): digest(p) for p in source.rglob('*') if p.is_file()},
                      instrumentation='ReadMemStats + process getrusage; external ps RSS KiB at acknowledged checkpoints; ru_maxrss Darwin bytes',
                      limitations='Sequential growth 0/1/2/4; resource-observed, no latency comparison to uninstrumented runs; no forced GC between forks; baseline GC, post-close GC and FreeOSMemory explicitly labelled')
        for label in ['maria', 'postgres']:
            binary = T / 'bin' / label
            command = [go, 'build', '-mod=readonly', '-p', '1', '-trimpath', '-buildvcs=true', '-o', str(binary), './' + label]
            print('BUILD', label, flush=True)
            with (E / ('build-' + label + '.txt')).open('w') as log:
                subprocess.run(command, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=1200)
            inputs['binaries'][label] = dict(sha256=digest(binary), bytes=binary.stat().st_size,
                build_info=subprocess.check_output([go, 'version', '-m', binary], text=True, env=env))
        save(E / 'inputs.json', inputs)
        print('BUILD PASS', flush=True)
        return
    inputs = json.loads((E / 'inputs.json').read_text())
    assert inputs['harness_source_commit'] == commit
    for label, info in inputs['binaries'].items():
        assert digest(T / 'bin' / label) == info['sha256']
    records = []

    def run(label, rep, negative=False, warmup=False):
        name = f'{phase}/{label}-{rep}' + ('-negative' if negative else '')
        report = E / (name + '.json')
        report.parent.mkdir(parents=True, exist_ok=True)
        scratch = T / 'scratch' / name
        scratch.mkdir(parents=True)
        args = [str(T / 'bin' / label), '-out', str(report)]
        if negative:
            args.append('-corrupt-seed')
        observed = []
        at = time.monotonic()
        with (E / (name + '.stderr.txt')).open('w') as log:
            process = subprocess.Popen(args, cwd=C, env=dict(env, TMPDIR=str(scratch)), stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=log, text=True, bufsize=1)
            try:
                selector = selectors.DefaultSelector()
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    assert selector.select(timeout=30), 'event timed out'
                    line = process.stdout.readline()
                    if not line:
                        break
                    event = json.loads(line)
                    rss = int(subprocess.check_output(['/bin/ps', '-o', 'rss=', '-p', str(process.pid)], text=True).strip()) * 1024
                    observed.append(dict(stage=event['stage'], children=event['children'], rss_bytes=rss))
                    save(E / (name + '.rss.json'), observed)
                    process.stdin.write('continue\n')
                    process.stdin.flush()
                code = process.wait(timeout=10)
            finally:
                selector.close()
                if process.poll() is None:
                    process.kill()
                    process.wait()
                process.stdin.close()
                process.stdout.close()
        result = json.loads(report.read_text())
        assert result['cleanup_complete'] and not any(scratch.iterdir())
        assert [x['stage'] for x in result['events']] == [x['stage'] for x in observed]
        if negative:
            assert code != 0 and not result['success'] and 'pristine oracle' in result['error']
        else:
            assert code == 0 and result['success'] and len(result['events']) == 16
            assert result['events'][-1]['stage'] == 'closed_all_scavenge'
        record = dict(name=name, warmup=warmup, negative=negative, backend=result['backend'], returncode=code,
                      wall_ms=(time.monotonic() - at) * 1000, scratch_empty=True, report=name + '.json', rss=name + '.rss.json')
        records.append(record)
        save(E / (phase + '-records.json'), records)
        print('PASS', name, round(record['wall_ms'], 1), 'ms', flush=True)

    if phase == 'pilot':
        for label in ['maria', 'postgres']:
            run(label, 0)
            run(label, 0, negative=True)
        save(E / 'pilot-result.json', dict(result='PASS', positive=2, negative=2))
    else:
        assert json.loads((E / 'pilot-result.json').read_text())['result'] == 'PASS'
        for label in ['maria', 'postgres']:
            run(label, -1, warmup=True)
        for rep in range(5):
            for label in (['maria', 'postgres'] if rep % 2 == 0 else ['postgres', 'maria']):
                run(label, rep)
        save(E / 'completion.json', dict(result='PASS', measured_processes=10, warmup_processes=2,
             measured_retained_children=40, scope='Sequential retained children 0/1/2/4, both TCP, one local M1; no performance acceptance'))


if __name__ == '__main__':
    main()
