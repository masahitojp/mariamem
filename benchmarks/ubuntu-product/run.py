#!/usr/bin/env python3
"""Native Ubuntu performance evidence, using unmodified released workloads."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from experiment_disk import DiskGuard, run_guarded
from git_identity import read_release_pin, require_commit, verify_go_binary, verify_release_pin

VERSIONS = ('v0.5.0', 'v0.5.1', 'v0.5.2')
# The reused Python parser requires a digest even when no container mode runs.
IMAGE = 'mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1'
OBSERVER_FILES = ('benchmarks/ownedprepared/main.go', 'benchmarks/ownedprepared/resources.go',
                  'benchmarks/python_product_suites.py')
EXPORT_GUARD = '\tif *export != "" {\n\t\tpanic("persisted fixture export was removed; prepare an in-memory baseline instead")\n\t}\n'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2) + '\n')

def normalize_observer(text):
    return text.replace(EXPORT_GUARD, '').replace('SnapshotOptions{Destination: *export}', 'SnapshotOptions{}')

def plan():
    cells = []
    for version in VERSIONS:
        for language in ('go', 'python'):
            for mode in ('fresh', 'fork'):
                cells.append(dict(version=version, language=language, mode=mode, case='light',
                                  trial=0, size=0, tables=1, workers=1, count=1, pilot=True))
    for trial in range(3):
        order = VERSIONS[trial:] + VERSIONS[:trial]
        for case, size, tables, workers in (('light', 0, 1, 1), ('fixture', 10, 8, 1),
                                            ('parallel', 10, 8, 4), ('large-fork', 100, 8, 1)):
            for language in ('go', 'python'):
                for mode in (('fork',) if size == 100 else ('fresh', 'fork')):
                    for version in (tuple(reversed(order)) if mode == 'fork' else order):
                        cells.append(dict(version=version, language=language, mode=mode, case=case,
                                          trial=trial, size=size, tables=tables, workers=workers, count=4, pilot=False))
    return cells

def cell_name(cell):
    return ('pilot-' if cell['pilot'] else '') + '-'.join(str(cell[k]) for k in ('version', 'language', 'case', 'trial', 'mode'))

def reduce_cell(cell, data, source_commit):
    """Reject incomplete/wrong-source/resource failures before summarizing time."""
    row = {**cell, 'name': cell_name(cell), 'source_commit': source_commit}
    if cell['language'] == 'go':
        assert data['label'] == source_commit
        assert (data['go'], data['goos'], data['goarch']) == ('go1.26.8', 'linux', 'amd64')
        assert (data['forks'], data['lifecycle'], data['workers'], data['payload_mib'], data['tables']) == (
            cell['count'], cell['mode'], cell['workers'], cell['size'], cell['tables'])
        mapping = data['resources']['after_go']['linear_memory_virtual']
        expected = cell['count'] + (cell['mode'] == 'fork')
        assert mapping['creates'] == mapping['releases'] == expected
        assert all(mapping[k] == 0 for k in ('active_mappings', 'active_reserved_bytes', 'active_rw_bytes', 'release_failures'))
        observation = data['go_resource_observation']
        assert observation['process_peak_rss_bytes'] <= 6 * 1024**3
        row.update(wall_seconds=data['suite_product_seconds'], observed_wall_seconds=data['suite_seconds'],
                   cpu_seconds=data['suite_cpu_seconds'], peak_rss_bytes=observation['process_peak_rss_bytes'],
                   cumulative_alloc_bytes=observation['cumulative_alloc_bytes'],
                   after_heap_bytes=data['resources']['after_go']['heap_alloc_bytes'],
                   mapping_creates=mapping['creates'], mapping_releases=mapping['releases'],
                   phases=data['operations'])
        row['starts_seconds'] = [p['seconds'] for p in data['operations']
                                 if p['name'] == 'prepare_start' or p['name'].startswith(('fresh_ready_', 'fork_ready_'))]
        row['snapshot_seconds'] = [p['seconds'] for p in data['operations'] if p['name'] == 'snapshot']
    else:
        assert data['source_commit'] == source_commit and data['completed'] is True
        assert (data['mode'], data['count'], data['workers'], data['tables']) == (
            cell['mode'], cell['count'], cell['workers'], cell['tables'])
        assert len(data['samples']) == cell['count']
        assert data['rows'] == max(1, cell['size'] * 1024)
        assert all(s['server_version'].startswith('12.3.3') for s in data['samples'])
        row.update(wall_seconds=data['suite_wall_seconds'], cpu_seconds=data['runner_and_reaped_host_cpu_seconds'],
                   samples=data['samples'], prepare_snapshot_seconds=data.get('prepare_snapshot_seconds'))
    assert row['wall_seconds'] > 0
    return row

def summarize(rows):
    assert len(rows) == len(plan()) == 138
    assert {r['name'] for r in rows} == {cell_name(c) for c in plan()}
    result = []
    for language in ('go', 'python'):
        for case in ('light', 'fixture', 'parallel', 'large-fork'):
            for mode in (('fork',) if case == 'large-fork' else ('fresh', 'fork')):
                item = dict(language=language, case=case, mode=mode, versions={})
                for version in VERSIONS:
                    matched = [r for r in rows if not r['pilot'] and
                               (r['language'], r['case'], r['mode'], r['version']) == (language, case, mode, version)]
                    assert len(matched) == 3
                    times = [r['wall_seconds'] for r in matched]
                    item['versions'][version] = dict(n=3, values_seconds=times, median_seconds=statistics.median(times),
                                                      min_seconds=min(times), max_seconds=max(times))
                    for metric in ('cpu_seconds', 'peak_rss_bytes', 'cumulative_alloc_bytes', 'after_heap_bytes'):
                        if all(metric in r for r in matched):
                            values = [r[metric] for r in matched]
                            item['versions'][version][metric] = dict(values=values, median=statistics.median(values))
                    for metric in ('starts_seconds', 'snapshot_seconds'):
                        values = [v for r in matched for v in r.get(metric, [])]
                        if values:item['versions'][version][metric] = dict(n=len(values), values=values, median=statistics.median(values))
                current = item['versions']['v0.5.2']['median_seconds']
                item['median_change_percent'] = {v: 100 * (current / item['versions'][v]['median_seconds'] - 1)
                                                  for v in ('v0.5.0', 'v0.5.1')}
                result.append(item)
    return result

def run(workspace):
    assert platform.system() == 'Linux' and platform.machine() == 'x86_64', 'native Linux x86_64 required'
    os_release = platform.freedesktop_os_release()
    assert (os_release['ID'], os_release['VERSION_ID']) == ('ubuntu', '24.04')
    assert sys.version_info[:3] == (3, 14, 8), sys.version
    work = workspace.resolve();temp = work / 'temp';out = work / 'evidence'
    temp.mkdir(parents=True, exist_ok=False);out.mkdir(parents=True, exist_ok=False)
    deadline = time.monotonic() + 7200
    guard = DiskGuard(work, min_free_gib=8, budget_gib=20)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('MARIAMEM_', 'MYSQLMEM_'))}
    for key in ('GOMAXPROCS', 'GOMEMLIMIT', 'GOGC', 'GOFLAGS', 'GOEXPERIMENT'):
        env.pop(key, None)
    env.update(GOTOOLCHAIN='local', CGO_ENABLED='0', GOWORK='off', GOENV='off', PYTHONDONTWRITEBYTECODE='1')
    for key, name in (('GOPATH', 'go-path'), ('GOMODCACHE', 'go-mod'), ('GOCACHE', 'go-cache'), ('GOTMPDIR', 'go-tmp')):
        env[key] = str(temp / name);Path(env[key]).mkdir(exist_ok=True)
    compiler = shutil.which('go');assert compiler
    version = subprocess.check_output([compiler, 'version'], env=env, text=True).strip()
    assert version == 'go version go1.26.8 linux/amd64', version
    harness_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    require_commit(ROOT, harness_commit)
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)
    receipt = dict(completed=False, harness_source_commit=harness_commit, go=version, python=sys.version,
                   os_release=os_release, platform=platform.platform(), commands=[], sources={}, cells=[])
    receipt['environment'] = {p: Path(p).read_text() for p in ('/proc/cpuinfo', '/proc/meminfo', '/proc/loadavg')}
    receipt['cgroup'] = {p: Path(p).read_text() for p in ('/sys/fs/cgroup/cpu.max', '/sys/fs/cgroup/memory.max') if Path(p).exists()}
    receipt['dependencies'] = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
    receipt['cc_version'] = subprocess.check_output(['cc', '--version'], text=True)
    receipt['git_version'] = subprocess.check_output(['git', '--version'], text=True).strip()
    receipt['runner_image'] = {k: os.environ.get(k) for k in ('ImageOS', 'ImageVersion', 'RUNNER_ENVIRONMENT')}
    receipt['harness_sha256'] = {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__), ROOT/'benchmarks/sharedhost/campaign.py', ROOT/'benchmarks/sharedhost/workflow.py', ROOT/'benchmarks/tools/process_cost.c']}
    write(out/'receipt.json', receipt);write(out/'plan.json', plan())

    def command(name, argv, cwd=ROOT, extra=None, timeout=900):
        remaining = deadline - time.monotonic()
        if remaining <= 0:raise TimeoutError('campaign budget reached; incomplete')
        started = time.monotonic()
        with (out/(name+'.txt')).open('w') as log:
            code = run_guarded([str(a) for a in argv], guard, cwd=cwd, env={**env, **(extra or {})},
                               output=log, timeout=min(timeout, remaining), interval=2)
        receipt['commands'].append(dict(name=name, argv=list(map(str, argv)), returncode=code,
                                        seconds=time.monotonic()-started, disk=guard.check()))
        write(out/'receipt.json', receipt)
        assert code == 0, f'{name} failed; original oracle retained, see {name}.txt'

    roots = {};bins = {}
    for release in VERSIONS:
        pin = read_release_pin(ROOT/f'release/baselines/{release}.json')
        identity = verify_release_pin(ROOT, pin)
        root = temp/release;roots[release] = root
        command('clone-'+release, ['git', 'clone', '--shared', '--no-checkout', ROOT, root])
        command('checkout-'+release, ['git', 'checkout', '--detach', pin.source_commit], cwd=root)
        require_commit(root, pin.source_commit)
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == pin.source_commit
        assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=root)
        directory = temp/'binaries'/release;directory.mkdir(parents=True);bins[release] = directory
        source = dict(pin=asdict(pin), identity=asdict(identity), observer_sha256={n: sha(root/n) for n in OBSERVER_FILES},
                      guest_sha256=json.loads((root/'release/generated-go-inputs.json').read_text())['guest_sha256'],
                      provenance_sha256=sha(root/'internal/generatedgo/provenance.json'), binaries={})
        for target, package in (('mariamem-host', './cmd/mariamem-host'), ('ownedprepared', './benchmarks/ownedprepared')):
            binary = directory/target
            command('build-'+release+'-'+target, [compiler, 'build', '-p', '1', '-mod=readonly', '-trimpath', '-buildvcs=true', '-o', binary, package], cwd=root, timeout=2400)
            source['binaries'][target] = dict(sha256=sha(binary), build_info=verify_go_binary(root, binary, pin.source_commit, go=compiler))
        receipt['sources'][release] = source;write(out/'receipt.json', receipt)
    # Preserve the old export-only difference; reject any other observer drift.
    for name in OBSERVER_FILES:
        texts = [(roots[v]/name).read_text() for v in VERSIONS]
        if name.endswith('/main.go'):texts = [normalize_observer(t) for t in texts]
        assert len(set(texts)) == 1, 'observer mismatch: '+name
    assert (ROOT/'benchmarks/python_product_suites.py').read_bytes() == (roots['v0.5.2']/'benchmarks/python_product_suites.py').read_bytes()
    helper = temp/'binaries/process-cost'
    command('build-process-cost', ['cc', '-O2', ROOT/'benchmarks/tools/process_cost.c', '-o', helper])
    receipt['process_helper_sha256'] = sha(helper)
    matrix = out/'matrix';matrix.mkdir()
    rows = []
    for cell in plan():
        label = cell['version'];root = roots[label];name = cell_name(cell);destination = matrix/(name+'.json')
        source = receipt['sources'][label]['pin']['source_commit']
        if cell['language'] == 'go':
            argv = [bins[label]/'ownedprepared', '-payload-mib', cell['size'], '-tables', cell['tables'],
                    '-workers', cell['workers'], '-forks', cell['count'], '-workload', 'app-connections',
                    '-lifecycle', cell['mode'], '-go-resources', '-helper', helper, '-label', source, '-out', destination]
        else:
            argv = [sys.executable, ROOT/'benchmarks/python_product_suites.py', '--payload-mib', cell['size'],
                    '--tables', cell['tables'], '--workers', cell['workers'], '--count', cell['count'],
                    '--mode', cell['mode'], '--host', bins[label]/'mariamem-host', '--helper', helper,
                    '--image', IMAGE, '--out', destination]
        scratch = temp/'cells'/name;scratch.mkdir(parents=True)
        command(name, argv, cwd=root, extra={'PYTHONPATH':str(root/'python'), 'TMPDIR':str(scratch)})
        assert not list(scratch.iterdir()), 'owned cell scratch survived: '+name
        rows.append(reduce_cell(cell, json.loads(destination.read_text()), source))
        receipt['cells'].append(name);write(out/'receipt.json', receipt);write(out/'cells.json', rows)
    write(out/'matrix-summary.json', summarize(rows))
    for baseline in ('v0.5.0', 'v0.5.1'):
        argv = [sys.executable, ROOT/'benchmarks/sharedhost/campaign.py', '--output', out/('reuse-'+baseline),
                '--scratch', temp/('reuse-'+baseline)]
        for label, v in (('baseline', baseline), ('candidate', 'v0.5.2')):
            argv += ['--'+label, roots[v], '--'+label+'-commit', receipt['sources'][v]['pin']['source_commit'],
                     '--'+label+'-host', bins[v]/'mariamem-host']
        command('reuse-'+baseline, argv, timeout=1800)
        plain = list((out/('reuse-'+baseline)).glob('plain-*.json'))
        resource = list((out/('reuse-'+baseline)).glob('resource-*.json'))
        assert len(plain) == 36 and len(resource) == 18
        assert all(json.loads(p.read_text())['result'] == 'PASS' for p in plain+resource)
    for v in VERSIONS:
        for target in ('mariamem-host', 'ownedprepared'):
            assert sha(bins[v]/target) == receipt['sources'][v]['binaries'][target]['sha256']
            verify_go_binary(roots[v], bins[v]/target, receipt['sources'][v]['pin']['source_commit'], go=compiler)
    receipt.update(completed=True, matrix_cells=138, measured_cells=126, pilots=12, reuse_cells=108,
                   total_executions=246, disk=guard.check(), elapsed_seconds=7200-(deadline-time.monotonic()))
    write(out/'receipt.json', receipt)
    print('COMPLETE: 246 executions accounted for; performance direction requires result review', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.workspace)
    except Exception as error:
        write(args.workspace/'evidence/failure.json', dict(completed=False, error_type=type(error).__name__,
                                                         message=str(error)))
        raise
