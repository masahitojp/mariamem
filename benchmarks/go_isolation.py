#!/usr/bin/env python3
"""Canonical 0.2 core baseline. Go measures lifecycle; shared Python code summarizes."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

from _common import ROOT, RESULTS, environment, positive, validate_guest_timing
from isolation_baseline import summarize, summarize_stages
from stage_report import render


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-dir', type=Path, default=os.environ.get('MARIAMEM_NATIVE_DIR'))
    parser.add_argument('--runs', type=positive, default=20)
    parser.add_argument('--warmup', type=int, default=2)
    parser.add_argument('--workers', nargs='+', type=positive, default=[1, 4, 8])
    parser.add_argument('--rows', type=positive, default=1000)
    parser.add_argument('--queries', type=positive, default=100)
    parser.add_argument('--clients', type=positive, default=2)
    parser.add_argument('--interval', type=float, default=.05)
    parser.add_argument('--hold', type=float, default=.1)
    parser.add_argument('--json', type=Path)
    parser.add_argument('--stage-timing', action='store_true')
    parser.add_argument('--guest-stage-timing', action='store_true')
    args = parser.parse_args()
    args.stage_timing = args.stage_timing or args.guest_stage_timing
    if args.native_dir is None:
        parser.error('--native-dir or MARIAMEM_NATIVE_DIR is required; no artifact auto-download')
    if args.warmup < 0 or not math.isfinite(args.interval) or args.interval <= 0 or not math.isfinite(args.hold) or args.hold < 0:
        parser.error('warmup/hold must be nonnegative; interval positive and finite')
    native = args.native_dir.expanduser().resolve()
    manifest = json.loads((native/'manifest.json').read_text())
    output = (args.json or RESULTS/f'go-isolation-baseline-{time.time_ns()}.json').resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(RESULTS):
        parser.error('repository-local output must be under benchmarks/results/')
    binary = ROOT/'build/bench/isolation-go'
    binary.parent.mkdir(parents=True, exist_ok=True)
    # Build and all artifact metadata work are outside the measured Go interval.
    subprocess.run(['go', 'build', '-trimpath', '-o', str(binary), './benchmarks/goisolation'], cwd=ROOT, check=True)
    command = [str(binary), '--native-dir', str(native), '--json', str(output)]
    for name in ['runs', 'warmup', 'rows', 'queries', 'clients', 'interval', 'hold']:
        command += ['--'+name, str(getattr(args, name))]
    command += ['--workers', ','.join(map(str, args.workers))]
    for name in ['stage_timing', 'guest_stage_timing']:
        if getattr(args, name):
            command += ['--'+name.replace('_', '-')]
    # Never load a stale report after an early executable/build failure.
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = output.with_name(output.name+'.partial')
    command[command.index('--json')+1] = str(raw)
    result = subprocess.run(command, cwd=ROOT)
    if not raw.is_file():
        raise RuntimeError(f'Go runner failed before writing evidence (exit {result.returncode})')
    report = json.loads(raw.read_text())
    raw.unlink()
    args.backend = 'none'  # Common environment collection must not import Python mariamem.
    metadata = environment(args)
    metadata['summary_python'] = metadata.pop('python')
    report['environment'].update(metadata)
    report['environment']['native_manifest'] = manifest
    report['environment']['native_dir'] = str(native)
    report['environment']['runner_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
    report['environment']['mysql_driver'] = subprocess.check_output(
        ['go', 'list', '-m', 'github.com/go-sql-driver/mysql'], cwd=ROOT, text=True).strip()
    sources = [Path(__file__), ROOT/'benchmarks/isolation_baseline.py', ROOT/'benchmarks/_common.py',
               ROOT/'benchmarks/stage_report.py', *sorted((ROOT/'benchmarks/goisolation').glob('*.go'))]
    report['environment']['harness_sha256'] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    report['settings'] = {key: value for key, value in vars(args).items() if key not in {'json', 'backend', 'native_dir'}}
    if args.guest_stage_timing:
        for sample in report['samples']:
            if sample['case'] == 'snapshot':
                continue
            traces = [value.get('stage_timings') for value in sample.get('per_db', [])] or [sample.get('stage_timings')]
            for trace in traces:
                if trace:
                    validate_guest_timing(trace['host'].get('guest'))
    report['summary'] = summarize(report['samples'])
    report['stage_summary'] = summarize_stages(report['samples'])
    output.write_text(json.dumps(report, indent=2)+'\n')
    print(render(report), end='')
    print(f'Raw results: {output}')
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
