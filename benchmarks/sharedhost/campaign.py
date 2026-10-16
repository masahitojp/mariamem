#!/usr/bin/env python3
"""Bounded paired comparison; ordinary and sampled-resource runs stay separate."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from git_identity import require_commit, verify_go_binary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for label in ('baseline', 'candidate'):
        p.add_argument('--'+label, type=Path, required=True, help='clean exact-source checkout')
        p.add_argument('--'+label+'-commit', required=True)
        p.add_argument('--'+label+'-host', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--scratch', type=Path, required=True)
    p.add_argument('--scales', nargs='+', choices=('small', 'medium', '100mib'), default=['small', 'medium', '100mib'])
    p.add_argument('--plain-repeats', type=int, default=6)
    p.add_argument('--resource-repeats', type=int, default=3)
    a = p.parse_args()
    if min(a.plain_repeats, a.resource_repeats) < 1 or len(a.scales) != len(set(a.scales)):
        p.error('positive repeat counts and unique scales required')
    a.output.mkdir(parents=True, exist_ok=False)
    a.scratch.mkdir(parents=True, exist_ok=True)
    source = {}
    for label in ('baseline', 'candidate'):
        root, commit, host = (getattr(a, label), getattr(a, label+'_commit'), getattr(a, label+'_host'))
        source[label] = dict(identity=asdict(require_commit(root, commit)),
            host_sha256=hashlib.sha256(host.read_bytes()).hexdigest(),
            build_info=verify_go_binary(root, host, commit))
    (a.output/'inputs.json').write_text(json.dumps(dict(sources=source,
        platform=platform.platform(), machine=platform.machine(), python=sys.version,
        scales=a.scales, plain_repeats=a.plain_repeats, resource_repeats=a.resource_repeats,
        harness={n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in ('workflow.py', 'campaign.py')}), indent=2)+'\n')
    results = []
    for resources, repeats in ((False, a.plain_repeats), (True, a.resource_repeats)):
        for scale in a.scales:
            for rep in range(repeats):
                order = ('baseline', 'candidate') if rep % 2 == 0 else ('candidate', 'baseline')
                for label in order:
                    name = f'{"resource" if resources else "plain"}-{scale}-{rep}-{label}'
                    out = a.output/(name+'.json')
                    with tempfile.TemporaryDirectory(prefix=name+'-', dir=a.scratch) as scratch:
                        env = {k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_', 'MYSQLMEM_'))}
                        env['TMPDIR'] = scratch
                        command = [sys.executable, str(Path(__file__).with_name('workflow.py')),
                            '--sdk', str(getattr(a, label)/'python'), '--host', str(getattr(a, label+'_host')),
                            '--scale', scale, '--output', str(out)]
                        samples = []
                        with out.with_suffix('.txt').open('w') as log:
                            proc = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
                            until = time.monotonic()+180
                            while proc.poll() is None:
                                if time.monotonic() > until:
                                    proc.kill(); proc.wait()
                                    raise TimeoutError(name)
                                if resources:
                                    raw = subprocess.check_output(['ps', '-axo', 'pid=,ppid=,rss='], text=True)
                                    processes = [tuple(map(int,line.split())) for line in raw.splitlines() if line.strip()]
                                    descendants = {proc.pid}
                                    while True:
                                        expanded = descendants | {pid for pid,ppid,rss in processes if ppid in descendants}
                                        if expanded == descendants:
                                            break
                                        descendants = expanded
                                    hosts = [(pid, rss) for pid,ppid,rss in processes if pid in descendants and pid != proc.pid]
                                    samples.append(dict(host_rss_kib=sum(rss for pid,rss in hosts), host_count=len(hosts)))
                                time.sleep(.025)
                            if proc.returncode:
                                raise RuntimeError(f'{name} exited {proc.returncode}; see {log.name}')
                        if list(Path(scratch).iterdir()):
                            raise RuntimeError('owned scratch survived: '+scratch)
                    result = json.loads(out.read_text())
                    result.update(label=label, resources_enabled=resources, repetition=rep)
                    if resources:
                        result['resource_samples'] = samples
                        result['sampled_host_peak_rss_mib'] = max(s['host_rss_kib'] for s in samples)/1024
                    out.write_text(json.dumps(result, indent=2)+'\n')
                    results.append(result)
                    print(name, round(result['whole_ms'],2), flush=True)
    summary = {}
    for scale in a.scales:
        cell = {}
        for label in ('baseline', 'candidate'):
            plain = [r for r in results if r['scale']==scale and r['label']==label and not r['resources_enabled']]
            observed = [r for r in results if r['scale']==scale and r['label']==label and r['resources_enabled']]
            cell[label] = dict(whole_ms=[r['whole_ms'] for r in plain], median_ms=statistics.median(r['whole_ms'] for r in plain),
                snapshot_median_ms=statistics.median(r['times_ms']['prepare/snapshot'] for r in plain),
                child_start_median_ms=statistics.median(v for r in plain for k,v in r['times_ms'].items() if k.endswith('/start') and k.startswith('child')),
                resource_whole_ms=[r['whole_ms'] for r in observed],
                sampled_peak_rss_mib=[r['sampled_host_peak_rss_mib'] for r in observed])
        cell['median_reduction_percent'] = 100*(1-cell['candidate']['median_ms']/cell['baseline']['median_ms'])
        summary[scale] = cell
    (a.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')


if __name__ == '__main__':
    main()
