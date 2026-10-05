#!/usr/bin/env python3
"""Bounded candidate validation and paired cost comparison; no mmap or forced GC.

Run only through experiment_workspace.py. Local cache/input paths can be
specified with MARIAMEM_SHARED_REPO, MARIAMEM_CACHE and MARIAMEM_RELEASE_GUEST.
"""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tarfile
import time
from fixtures import build

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
TEMP = Path(os.environ['MARIAMEM_EXPERIMENT_TEMP'])
EVIDENCE = Path(os.environ['MARIAMEM_EXPERIMENT_EVIDENCE'])
COMMON_GIT = Path(subprocess.check_output(['git', 'rev-parse', '--git-common-dir'], cwd=ROOT, text=True).strip())
if not COMMON_GIT.is_absolute():
    COMMON_GIT = ROOT/COMMON_GIT
SHARED = Path(os.environ.get('MARIAMEM_SHARED_REPO', str(COMMON_GIT.resolve().parent)))
CACHE = Path(os.environ['MARIAMEM_CACHE'])
GUEST = Path(os.environ['MARIAMEM_RELEASE_GUEST'])
RELEASE = '547fb1a6c01e5edb0daa27de273a2e94e66eb098'
env = dict(os.environ, GOTOOLCHAIN='go1.26.8', GOWORK='off', GOENV='off', GOFLAGS='', GOEXPERIMENT='', CGO_ENABLED='0', GOCACHE=str(SHARED/'build/gocache'))
GO = Path(subprocess.check_output(['go', 'env', 'GOROOT'], env=env, text=True).strip())/'bin/go'
env['PATH'] = str(GO.parent)+os.pathsep+env['PATH']
record = {'released_base': RELEASE, 'backing': 'unchanged Go heap', 'mmap': False, 'phases': [], 'rss_limit_bytes': 6*(1<<30), 'physical_limit_bytes': 8*(1<<30)}

def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def save():
    (EVIDENCE/'campaign.json').write_text(json.dumps(record, indent=2)+'\n')

def limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (180, 200))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))

def run(name, command, cwd=ROOT, timeout=600, extras=None):
    print('RUN', name, flush=True)
    row = {'name': name, 'command': list(map(str, command)), 'peak_rss_bytes': 0, 'peak_physical_bytes': 0}
    record['phases'].append(row)
    start = time.monotonic()
    save()
    with (EVIDENCE/(name+'.log')).open('wb') as log:
        p = subprocess.Popen(list(map(str, command)), cwd=cwd, env=dict(env, **(extras or {})), stdout=log, stderr=subprocess.STDOUT, preexec_fn=limits)
        try:
            while p.poll() is None:
                if time.monotonic()-start > timeout:
                    raise RuntimeError(name+': watchdog')
                counter = TEMP/'process-cost'
                if counter.exists():
                    pairs = [tuple(map(int, x.split())) for x in subprocess.check_output(['ps', '-A', '-o', 'pid=,ppid='], text=True).splitlines() if len(x.split()) == 2]
                    ids = {p.pid}
                    for _ in pairs:
                        prior = len(ids)
                        ids.update(a for a, b in pairs if b in ids)
                        if len(ids) == prior:
                            break
                    counters = json.loads(subprocess.check_output([str(counter), *map(str, ids)], text=True))
                    rss = sum(x.get('rss_bytes', 0) for x in counters.values())
                    physical = sum(x.get('primary_bytes', 0) for x in counters.values())
                    row['peak_rss_bytes'] = max(row['peak_rss_bytes'], rss)
                    row['peak_physical_bytes'] = max(row['peak_physical_bytes'], physical)
                    if rss > record['rss_limit_bytes'] or physical > record['physical_limit_bytes']:
                        row['stop'] = 'memory budget'
                        save()
                        raise RuntimeError(name+': memory budget')
                time.sleep(.2)
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
    row.update(exit_code=p.returncode, elapsed_seconds=time.monotonic()-start)
    save()
    print('END', name, p.returncode, flush=True)
    if p.returncode:
        raise RuntimeError(name+': failed; evidence retained')

def campaign():
    assert subprocess.check_output(['git', 'rev-parse', 'v0.4.1^{}'], cwd=ROOT, text=True).strip() == RELEASE
    record['guest_sha256'] = digest(GUEST)
    assert record['guest_sha256'] == json.loads((ROOT/'release/generated-go-inputs.json').read_text())['guest_sha256']
    save()
    run('build-counter', ['cc', '-O2', ROOT/'benchmarks/tools/process_cost.c', '-o', TEMP/'process-cost'])
    if 'MARIAMEM_CONVERTER_SOURCE' in os.environ:
        source = Path(os.environ['MARIAMEM_CONVERTER_SOURCE'])
    else:
        archive = CACHE/'wasm2go-fork.tar.gz'
        assert digest(archive) == '1fcd91eecc66e367495d91f34644c68df1ff856a786d00c24fa66061c3dbce0f'
        container = TEMP/'converter'
        container.mkdir()
        with tarfile.open(archive) as tar:
            tar.extractall(container, filter='data')
        source = next(container.iterdir())
        for patch in ['imported-memory.patch','import-function-index.patch','relaxed-madd.patch','pure-memory32.patch']:
            run('patch-'+patch,['git','apply','--unidiff-zero',ROOT/'benchmarks/spikes/wasm2go'/patch],cwd=source)
    run('converter-unit-tests', [GO, 'test', '-p', '1', '-run=^(TestMemoryAccessWidths|TestTrappingLoadIsObservable|TestPureMemory32RetainsIndividualStores|TestDCE.*)$', './internal/codegen', './internal/ssa', './internal/ssa/pass'], cwd=source)
    run('build-converter', [GO, 'build', '-p', '1', '-trimpath', '-o', TEMP/'converter-bin', './cmd/wasm2go'], cwd=source)
    fixture = TEMP/'fixtures'
    record['fixture_case_count'] = build(fixture)
    save()
    run('wasm-reference', ['node', HERE/'reference.js', fixture/'contract.wasm', fixture/'matrix.json'])
    project = TEMP/'fixture'; (project/'fixture').mkdir(parents=True)
    (project/'go.mod').write_text('module genericfixture\n\ngo 1.26.0\n')
    shutil.copyfile(HERE/'matrix.go.txt', project/'main.go')
    run('translate-fixture', [TEMP/'converter-bin', '-pure', '-i', fixture/'contract.wasm', '-o', project/'fixture/fixture.go', '-pkg', 'fixture', '-import', 'genericfixture/fixture'])
    run('fixture-matrix', [GO, 'run', '.', fixture/'matrix.json'], cwd=project)
    read_rows = lambda name: [json.loads(line) for line in (EVIDENCE/(name+'.log')).read_text().splitlines() if line.startswith('{')]
    reference = read_rows('wasm-reference'); candidate = read_rows('fixture-matrix')
    keys = ['op', 'addr', 'grow', 'trap', 'value', 'before', 'after']
    assert len(reference) == len(candidate) == record['fixture_case_count']
    assert [[r[k] for k in keys] for r in reference] == [[r[k] for k in keys] for r in candidate]
    record.update(fixture_pass=True, trap_cases=sum(r['trap'] for r in candidate)); save()
    run('translate-guest', [sys.executable, ROOT/'benchmarks/spikes/generated-go-integration/translate_guest.py', '--guest', GUEST, '--guest-sha256', record['guest_sha256'], '--converter-archive', CACHE/'wasm2go-fork.tar.gz', '--output', TEMP/'translation'])
    manifest = TEMP/'translation/input-manifest.json'
    shutil.copyfile(manifest, ROOT/'release/generated-go-translation.json')
    run('prepare-candidate', [sys.executable, ROOT/'benchmarks/spikes/generated-go-integration/setup_candidate.py', '--source-only', '--source-module', TEMP/'translation/module', '--guest', GUEST, '--input-manifest', manifest, '--output', TEMP/'candidate'])
    pins_path = ROOT/'release/generated-go-inputs.json'
    pins = json.loads(pins_path.read_text())
    module = TEMP/'candidate/module'
    pins['candidate_files_sha256'] = {str(p.relative_to(module)): digest(p) for suffix in ('*.go', '*.s') for p in module.rglob(suffix)}
    pins_path.write_text(json.dumps(pins, indent=2)+'\n')
    run('install-runtime', [sys.executable, ROOT/'scripts/generate_runtime.py', '--source-module', module, '--output', TEMP/'generatedgo'])
    # Carry only the deterministic canonical generated output and existing glue.
    for p in (TEMP/'generatedgo').rglob('*'):
        if p.is_file():
            target = ROOT/'internal/generatedgo'/p.relative_to(TEMP/'generatedgo')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)
    run('verify-provenance', [sys.executable, ROOT/'scripts/verify_generated_runtime.py'])
    shutil.copyfile(HERE/'product_smoke_test.go.txt', ROOT/'tests/godefault/pure_memory32_test.go')
    run('focused-runtime-race', [GO, 'test', '-race', '-p', '1', '-count=1', './internal/generatedgo/code/base'], extras={'CGO_ENABLED': '1'})
    for test in ['GeneratedTraps', 'CRUDSessionsAndFork', 'Auth', 'RepeatedClose']:
        run('product-'+test, [GO, 'test', '-p', '1', '-tags=integration', '-v', '-count=1', '-run=^TestPureMemory32'+test+'$', '-timeout=90s', './tests/godefault'], timeout=150)
    record['compatibility_pass'] = True; save()
    baseline = TEMP/'baseline'; baseline.mkdir()
    archive = TEMP/'baseline.tar'
    with archive.open('wb') as dest:
        subprocess.run(['git', 'archive', RELEASE], cwd=ROOT, stdout=dest, check=True)
    with tarfile.open(archive) as tar:
        tar.extractall(baseline, filter='data')
    archive.unlink()
    for mode, runtime_source in [('baseline', baseline), ('candidate', ROOT)]:
        probe = TEMP/('probe-'+mode); probe.mkdir()
        (probe/'go.mod').write_text('module memorycost\n\ngo 1.26.0\nrequire github.com/masahitojp/mariamem v0.0.0\nreplace github.com/masahitojp/mariamem => '+str(runtime_source)+'\n')
        shutil.copyfile(HERE/'probe.go.txt', probe/'main.go')
        run('build-probe-'+mode, [GO, 'build', '-mod=mod', '-p', '1', '-trimpath', '-o', TEMP/(mode+'-probe'), '.'], cwd=probe)
    for trial in range(20):
        # Alternate ordering; identical source/probe and workload, no excluded tails.
        for mode in (['baseline', 'candidate'] if trial%2 == 0 else ['candidate', 'baseline']):
            run('fresh-%02d-%s' % (trial, mode), [TEMP/(mode+'-probe')], timeout=60)
    for mode in ['baseline', 'candidate']:
        run('repeated-'+mode, [TEMP/(mode+'-probe'), '-generations=20'], timeout=180)
    run('compiler-inline-assessment', [GO, 'build', '-p', '1', '-gcflags=genericfixture/fixture=-m=2', '-o', TEMP/'inline-fixture', '.'], cwd=project)
    record['finished'] = True
    save()

if __name__ == '__main__':
    campaign()
