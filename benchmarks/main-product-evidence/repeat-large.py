"""Twelve bounded follow-up cells for the observed Go 100 MiB slowdown.

Uses the existing binaries/workload/oracles, retains the original n=1, and shares
the original overall deadline. No rebuild, profiling or runtime changes.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--go-root', type=Path, required=True)
    a = p.parse_args()
    w = a.workspace.resolve()
    root = w / 'worktree'
    sys.path.insert(0, str(root / 'scripts'))
    from experiment_disk import DiskGuard, run_guarded
    from experiment_workspace import exclusive
    from git_identity import require_commit, verify_go_binary
    assert json.loads((w / 'evidence/completion.json').read_text())['executions'] == 262
    assert json.loads((w / 'evidence/manual-continuation.json').read_text())['completed']
    deadline = json.loads((w / 'experiment.json').read_text())['created'] + 7200
    out = w / 'evidence/large-repeat'
    out.mkdir(exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('MARIAMEM_', 'MYSQLMEM_'))}
    env.update(PATH=str(a.go_root / 'bin') + os.pathsep + env['PATH'], GOTOOLCHAIN='local',
               TMPDIR=str(w / 'temp/tmp'))
    for key in ['GOMAXPROCS', 'GOMEMLIMIT', 'GOGC']:
        env.pop(key, None)
    sources = {'baseline': '44100ec676c8c9064f32f3a01bd9a990d487bb61',
               'candidate': 'c97e55fc065f6ee7b560325077726da53e5d95d7'}
    receipt = dict(reason='Repeat material adverse Go 100 MiB n=1 observations; original cells retained',
                   repetitions_per_mode=3, original_deadline=deadline,
                   started=time.time(), completed=False, cells=[], inputs={})

    def save():
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')

    with exclusive(w):
        guard = DiskGuard(w, 20, 12)
        for label, sha in sources.items():
            checkout = w / 'temp' / label
            assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip() == sha
            assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=checkout)
            binary = w / 'temp/binaries' / label / 'ownedprepared'
            receipt['inputs'][label] = dict(identity=asdict(require_commit(checkout, sha)),
                binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                build_info=verify_go_binary(checkout, binary, sha, go=a.go_root / 'bin/go'))
        receipt['harness_source_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        receipt['runner_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        save()
        for trial in range(3):
            for mode in ['fresh', 'fork']:
                order = ['baseline', 'candidate'] if (trial + (mode == 'fork')) % 2 == 0 else ['candidate', 'baseline']
                for label in order:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        raise TimeoutError('Original overall budget exhausted: incomplete')
                    name = f'{label}-go-large-{trial}-{mode}'
                    dest = out / (name + '.json')
                    command = [str(w / 'temp/binaries' / label / 'ownedprepared'),
                        '-payload-mib', '100', '-tables', '8', '-workers', '1', '-forks', '4',
                        '-workload', 'app-connections', '-lifecycle', mode, '-go-resources',
                        '-helper', str(w / 'temp/binaries/process-cost'), '-label', sources[label], '-out', str(dest)]
                    start = time.monotonic()
                    with dest.with_suffix('.txt').open('w') as log:
                        code = run_guarded(command, guard, cwd=w / 'temp' / label,
                                           env=env, output=log, timeout=min(900, remaining), interval=5)
                    receipt['cells'].append(dict(name=name, returncode=code, elapsed_seconds=time.monotonic() - start))
                    save()
                    if code:
                        raise SystemExit(f'{name}: unchanged oracle failed ({code}); incomplete')
                    d = json.loads(dest.read_text())
                    assert d['go_resource_observation']['process_peak_rss_bytes'] <= 8 * 1024**3
                    print(name, round(d['suite_product_seconds'], 3), flush=True)
        receipt.update(completed=True, ended=time.time(), peak_owned_bytes=guard.peak,
                       minimum_free_bytes=guard.minimum_free)
        save()
    print('PASS: all 12 follow-up cells complete; original observations retained', flush=True)


if __name__ == '__main__':
    main()
