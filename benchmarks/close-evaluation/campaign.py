#!/usr/bin/env python3
"""Finite #206 campaign. Run from a clean committed experiment worktree."""
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(sys.argv[1]).resolve()
EVIDENCE = WORK / 'evidence'
TEMP = WORK / 'temp'
ENV = dict(os.environ, GOTOOLCHAIN='go1.26.10', GOWORK='off', GOENV='off', GOFLAGS='', GOEXPERIMENT='', GOMAXPROCS='8', GOGC='100', CGO_ENABLED='0', GOCACHE=str(TEMP/'go-cache'))
CELLS = [(1, 2), (2, 4), (1, 1), (2, 2)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked(args, name, env=ENV):
    with (EVIDENCE/name).open('w') as out:
        r = subprocess.run(args, cwd=ROOT, env=env, stdout=out, stderr=subprocess.STDOUT)
    if r.returncode:
        raise RuntimeError(f'{name}: exit {r.returncode}')


def trial(binary, p, cap, mode, phase, pair=None):
    env = dict(ENV, CLOSE_EVAL='1', CLOSE_P=str(p), CLOSE_CAP=str(cap), CLOSE_MODE=mode)
    output = TEMP/'trial.txt'
    argv = [str(binary), '-test.run=^TestCloseEvaluation$', '-test.timeout=120s', '-test.count=1']
    utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    load = os.getloadavg()
    start = time.perf_counter()
    with output.open('w') as f:
        pid = os.posix_spawn(str(binary), argv, env, file_actions=[(os.POSIX_SPAWN_DUP2, f.fileno(), 1), (os.POSIX_SPAWN_DUP2, f.fileno(), 2)])
    _, status, usage = os.wait4(pid, 0)
    wall = (time.perf_counter()-start)*1000
    raw = output.read_text()
    records = [json.loads(line.removeprefix('CLOSE_RESULT ')) for line in raw.splitlines() if line.startswith('CLOSE_RESULT ')]
    record = records[0] if len(records) == 1 else {}
    record.update(utc=utc, host_load_before=load, host_load_after=os.getloadavg(), phase=phase, pair=pair, exit_status=os.waitstatus_to_exitcode(status), process_wall_ms=wall, process_cpu_ms=(usage.ru_utime+usage.ru_stime)*1000, peak_rss_bytes=usage.ru_maxrss*(1 if sys.platform == 'darwin' else 1024))
    with (EVIDENCE/'runs.jsonl').open('a') as f:
        f.write(json.dumps(record)+'\n')
    if status != 0 or not records or record.get('failures'):
        (EVIDENCE/'failed-trial.txt').write_text(raw)
        raise RuntimeError(f'failed {phase} P{p}/cap{cap}/{mode}: {record}')
    time.sleep(.15)
    return record


def main():
    source = json.loads(subprocess.check_output([sys.executable, 'scripts/git_identity.py', 'inspect', 'HEAD'], cwd=ROOT, text=True))['source_commit']
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True):
        raise RuntimeError('candidate must be committed and clean before builds')
    meta = {'source_commit': source, 'product_baseline_source_commit': 'f563128520fc49097ac83ef47cdea2dee21ff62a', 'platform': platform.platform(), 'machine': platform.machine(), 'go': subprocess.check_output(['go', 'version'], env=ENV, text=True).strip(), 'measurement_cgo_enabled': 0, 'race_build_cgo_enabled': 1, 'gomaxprocs': 8, 'gogc': 100, 'cells': CELLS, 'children': 48, 'rows': 1000, 'sleep_between_processes_s': .15, 'host_load_start': os.getloadavg()}
    (EVIDENCE/'inputs.json').write_text(json.dumps(meta, indent=2)+'\n')
    checked(['go', 'test', '-p', '1', '.', './mariamemtest', './internal/guest', './internal/host', './internal/generatedgo', './internal/forklimit', './internal/disposal'], 'safety.txt')
    checked(['go', 'test', '-p', '1', '-tags=integration', './tests/generatedmemory', './internal/generatedgo', '-run', 'TestPureMemory32|TestProcessImageSurvivesIndependentRootsAndSnapshots|TestWorkerTrapActualGuestNotifiesAndIsolatesPeer|TestActualGuestStoppedBeforeMemoryRelease', '-count=1'], 'actual-guest.txt')
    plain, diag, race = [TEMP/n for n in ('plain.test', 'diag.test', 'race.test')]
    checked(['go', 'test', '-c', '-p', '1', '-tags=closeeval', '-o', str(plain), '.'], 'build-plain.txt')
    # Smoke before the more expensive race build; both public Close and early
    # stop run through the real host/guest and drain every handle.
    for mode in ('sync', 'stop'):
        trial(plain, 2, 4, mode, 'smoke')
    path = ROOT/'close_evaluation_test.go'
    text = path.read_text()
    assert text.count('const evalDiagnostic = false') == 1
    overlay_source = TEMP/'diag.go'
    overlay_source.write_text(text.replace('const evalDiagnostic = false', 'const evalDiagnostic = true'))
    overlay = TEMP/'overlay.json'
    overlay.write_text(json.dumps({'Replace': {str(path): str(overlay_source)}}))
    checked(['go', 'test', '-c', '-p', '1', '-tags=closeeval', '-overlay', str(overlay), '-o', str(diag), '.'], 'build-diag.txt')
    checked(['go', 'test', '-c', '-race', '-p', '1', '-tags=closeeval', '-o', str(race), '.'], 'build-race.txt', env=dict(ENV, CGO_ENABLED='1'))
    for mode in ('sync', 'stop'):
        trial(race, 2, 4, mode, 'race')
    meta['binaries'] = {name: {'sha256': sha(binary), 'bytes': binary.stat().st_size, 'buildinfo': subprocess.check_output(['go', 'version', '-m', str(binary)], env=ENV, text=True).replace(str(binary), name)} for name, binary in [('plain', plain), ('diagnostic', diag), ('race', race)]}
    meta['diagnostic_overlay_sha256'] = sha(overlay_source)
    (EVIDENCE/'inputs.json').write_text(json.dumps(meta, indent=2)+'\n')
    # No build, test or diagnostic process overlaps the main campaign.
    for p, cap in CELLS:
        for mode in ('sync', 'stop'):
            trial(plain, p, cap, mode, 'warmup')
    for pair in range(5):
        cells = CELLS[pair % 4:] + CELLS[:pair % 4]
        for p, cap in cells:
            for mode in (('sync', 'stop') if pair % 2 == 0 else ('stop', 'sync')):
                trial(plain, p, cap, mode, 'measure', pair)
    for p, cap in CELLS:
        for mode in ('sync', 'stop'):
            trial(diag, p, cap, mode, 'diagnostic')
    meta['host_load_end'] = os.getloadavg()
    (EVIDENCE/'inputs.json').write_text(json.dumps(meta, indent=2)+'\n')
    runs = [json.loads(s) for s in (EVIDENCE/'runs.jsonl').read_text().splitlines()]
    summary = []
    for p, cap in CELLS:
        row = {'p': p, 'cap': cap, 'pairs': []}
        for pair in range(5):
            arms = {r['mode']: r for r in runs if r['phase'] == 'measure' and r['p'] == p and r['cap'] == cap and r['pair'] == pair}
            a, b = arms['sync'], arms['stop']
            row['pairs'].append({'pair': pair, 'batch_ms_delta': b['batch_drain_ms']-a['batch_drain_ms'], 'batch_pct': (b['batch_drain_ms']/a['batch_drain_ms']-1)*100})
        metrics = ['batch_drain_ms', 'workers_ms', 'drain_ms', 'batch_cpu_ms', 'process_wall_ms', 'process_cpu_ms', 'peak_rss_bytes']
        row['medians'] = {mode: {key: statistics.median(r[key] for r in runs if r['phase'] == 'measure' and r['p'] == p and r['cap'] == cap and r['mode'] == mode) for key in metrics} for mode in ('sync', 'stop')}
        row['paired_median_pct'] = statistics.median(x['batch_pct'] for x in row['pairs'])
        row['paired_median_ms_delta'] = statistics.median(x['batch_ms_delta'] for x in row['pairs'])
        row['faster_pairs'] = sum(x['batch_pct'] < 0 for x in row['pairs'])
        summary.append(row)
    (EVIDENCE/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')


if __name__ == '__main__':
    main()
