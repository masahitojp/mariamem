#!/usr/bin/env python3
"""Run independent source-to-legacy-EH builds; no historical identity requirement."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--downloads', type=Path, required=True)
    parser.add_argument('--converter-archive', type=Path, required=True)
    parser.add_argument('--llvm-dir', type=Path)
    parser.add_argument('--trials', type=int, default=6)
    parser.add_argument('--parallel', type=int, default=2)
    args = parser.parse_args()
    if args.trials < 2 or not 1 <= args.parallel <= 2:
        parser.error('at least two trials; parallel must be 1 or 2')
    out = args.output.resolve()
    if out.exists():
        parser.error('output must be fresh')
    out.mkdir(parents=True)
    records = []

    def run(i):
        start = datetime.now(timezone.utc).isoformat()
        target = out / f'run-{i}'
        argv = [sys.executable, str(HERE/'readiness_replay.py'), '--output', str(target), '--downloads', str(args.downloads.resolve()), '--converter-archive', str(args.converter_archive.resolve()), '--guest-build-only']
        if args.llvm_dir:
            argv += ['--llvm-dir', str(args.llvm_dir.resolve())]
        with (out/f'run-{i}.log').open('w') as log:
            code = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT).returncode
        replay = target/'replay.json'
        return {'run': i, 'start_utc': start, 'end_utc': datetime.now(timezone.utc).isoformat(), 'exit_code': code, 'replay': json.loads(replay.read_text()) if replay.exists() else None}

    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = [pool.submit(run, i) for i in range(1, args.trials+1)]
        for future in as_completed(futures):
            record = future.result()
            records.append(record)
            records.sort(key=lambda x:x['run'])
            (out/'campaign.json').write_text(json.dumps({'comparison_scope':'independent v0.4 legacy-EH builds; no old/new-EH reference identity gate', 'parallel':args.parallel, 'trials_requested':args.trials, 'runs':records}, indent=2)+'\n')
            print(f"run {record['run']}: exit={record['exit_code']}", flush=True)
    hashes = {x['replay']['guest_sha256'] for x in records if x['exit_code']==0}
    passed = len(hashes)==1 and len(records)==args.trials and all(x['exit_code']==0 for x in records)
    print(json.dumps({'completed':len(records), 'identical_final_sha256':passed, 'final_sha256':sorted(hashes)}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
