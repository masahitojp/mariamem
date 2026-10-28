#!/usr/bin/env python3
"""Run/validate bounded G1 observations; declarations alone never grant PASS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import time

from consumer_module import source_identity
from git_identity import require_commit

ROOT = Path(__file__).resolve().parents[1]
HOSTS = {'macos-15': ('Darwin', 'arm64'), 'ubuntu-24.04': ('Linux', 'x86_64')}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def numeric(value):
    return type(value) in (int, float) and value >= 0 and value < float('inf')


def input_paths(resources):
    return ['mariamemtest/campaign_test.go', 'mariamemtest/fixture_test.go',
            'scripts/go_fixture_campaign.py', 'docs/reviews/v06x-fixture-acceptance.json',
            'docs/go-prepared-fixture.md', resources['retention_input']['path']]


def available_memory():
    if platform.system() == 'Linux':
        entries = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        return int(entries['MemAvailable'].split()[0]) * 1024, 'Linux MemAvailable'
    raw = subprocess.check_output(['vm_stat'], text=True)
    page_size = int(raw.split('page size of ', 1)[1].split(' bytes', 1)[0])
    counters = dict(line.split(':', 1) for line in raw.splitlines()[1:] if ':' in line)
    pages = sum(int(counters[key].strip().rstrip('.')) for key in
                ('Pages free', 'Pages inactive', 'Pages speculative'))
    return pages * page_size, 'macOS estimate: (free+inactive+speculative) pages; not physical footprint'


def process_rss(pid):
    raw = subprocess.check_output(['ps', '-A', '-o', 'pid=,ppid=,rss='], text=True)
    rows = [tuple(map(int, line.split())) for line in raw.splitlines() if line.strip()]
    family = {pid}
    while True:
        children = {p for p, parent, _ in rows if parent in family}
        if children <= family:
            break
        family |= children
    values = {str(p): rss * 1024 for p, _, rss in rows if p in family}
    need(str(pid) in values, 'runtime process RSS unavailable')
    return values


def host_profile():
    system, arch = platform.system(), platform.machine()
    need((system, arch) in HOSTS.values(), 'unsupported campaign host')
    if system == 'Darwin':
        version = subprocess.check_output(['sw_vers', '-productVersion'], text=True).strip()
        need(int(version.split('.')[0]) >= 15, 'requires macOS15+')
        return {'system': system, 'architecture': arch, 'version': version}
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    need(release['ID'].strip('"') == 'ubuntu' and release['VERSION_ID'].strip('"') == '24.04', 'requires Ubuntu24.04')
    return {'system': system, 'architecture': arch, 'version': '24.04'}


def run_command(command, output, env=None):
    started = time.monotonic()
    with Path(output).open('w') as stream:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=600)
    need(result.returncode == 0, 'command failed; see ' + str(Path(output).name))
    return {'command': command, 'elapsed_seconds': time.monotonic() - started}


def observe(command, directory, env, resources):
    stop = directory / 'STOP.txt'
    env = dict(env, MARIAMEM_G1_STOP=str(stop))
    samples, errors = [], []
    started = time.monotonic()
    with (directory / 'stdout.txt').open('w') as stream:
        proc = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, start_new_session=True)
        while proc.poll() is None:
            try:
                members = process_rss(proc.pid)
                available, mechanism = available_memory()
                rss = sum(members.values())
                samples.append({'at_seconds': time.monotonic() - started,
                                'unix_ns': time.time_ns(), 'process_tree_rss_bytes': rss,
                                'members': members, 'available_memory_bytes': available,
                                'available_memory_mechanism': mechanism})
                if rss - samples[0]['process_tree_rss_bytes'] > resources['incremental_rss_ceiling_bytes']:
                    stop.write_text('incremental process-tree RSS guard')
            except Exception as exc:
                if proc.poll() is None:
                    errors.append(str(exc))
                    stop.write_text('UNVERIFIED host counter: ' + str(exc))
            if time.monotonic() - started > 330:
                stop.write_text('campaign process deadline; cleanup unconfirmed')
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                break
            time.sleep(.1)
        code = proc.wait()
    report = {'result': 'PASS' if code == 0 and samples and not errors and not stop.exists() else 'UNVERIFIED',
              'returncode': code, 'elapsed_seconds': time.monotonic() - started,
              'requested_interval_seconds': .1, 'rss_mechanism': 'sampled process-tree ps RSS sum',
              'samples': samples, 'counter_errors': errors,
              'stop_reason': stop.read_text() if stop.exists() else None}
    write(directory / 'os.json', report)
    need(report['result'] == 'PASS', 'runtime/guard/counter failure; evidence preserved')


def validate_mode(go, observed, cap, parallel, resources):
    need(go['result'] == 'PASS' and go['cleanup_complete'] is True and not go['stop_reason'], 'runtime did not finish cleanly')
    need(go['cap'] == cap and go['parallel'] == parallel, 'wrong cap/parallel mode')
    need(go['guards'] == {k: resources[k] for k in ('owned_disk_ceiling_bytes', 'min_free_disk_bytes', 'min_fd_headroom')}, 'runtime guard values differ')
    need(min(cap, parallel) <= go['peak_children'] <= cap, 'unobserved/exceeded child budget')
    need(2 <= go['peak_physical_pool_connections'] <= 2 * cap, 'physical pool connection budget')
    need([b['label'] for b in go['batches']] == ['warmup', 'observed_1', 'observed_2', 'observed_3'], 'missing warmup/observed batch')
    need(all(numeric(b['elapsed_seconds']) and b['elapsed_seconds'] > 0 for b in go['batches']), 'batch timing missing')
    need(len(go['cases']) == 16, 'incomplete case batch')
    for case in go['cases']:
        need(all(numeric(case[key]) and case[key] > 0 for key in
                 ('admission_seconds', 'sql_seconds', 'cleanup_seconds')), 'case phase timing missing')
    phases = {p['name'] for p in go['phases'] if numeric(p['seconds']) and p['seconds'] > 0}
    need({'start', 'prepare', 'disconnect', 'capture'} <= phases, 'setup phase timing missing')
    need(go['new_fixture_seconds'] > 0 and go['fixture_close_seconds'] > 0, 'fixture timing missing')
    samples = go['samples']
    need(samples[0]['label'] == 'baseline' and samples[-1]['label'] == 'final', 'FD baseline/final missing')
    for s in samples:
        for key in ('fd', 'fd_soft_limit', 'linked_temp_bytes', 'unlinked_file_bytes', 'disk_free_bytes',
                    'children', 'baselines', 'physical_pool_connections'):
            need(numeric(s[key]), 'missing counter ' + key)
        need(s['fd_soft_limit'] - s['fd'] >= resources['min_fd_headroom'], 'FD headroom breach')
        need(s['linked_temp_bytes'] + s['unlinked_file_bytes'] <= resources['owned_disk_ceiling_bytes'], 'owned disk breach')
        need(s['disk_free_bytes'] >= resources['min_free_disk_bytes'], 'free disk breach')
        need(s['children'] <= cap and s['physical_pool_connections'] <= cap * 2, 'runtime budget breach')
    retained_samples = []
    for count in (1, 2, 3):
        retained = [s for s in samples if s['label'] == 'retained_' + str(count)]
        need(len(retained) == 1 and retained[0]['baselines'] == count and retained[0]['children'] == 0,
             'missing retained-baseline observation')
        end = [s for s in samples if s['label'] == 'retained_end_' + str(count)]
        need(len(end) == 1 and end[0]['baselines'] == count, 'retention observation window missing')
        retained_samples.append((retained[0], end[0]))
    final = samples[-1]
    need(all(final[key] == 0 for key in ('children', 'baselines', 'physical_pool_connections',
                                      'linked_temp_bytes', 'unlinked_file_bytes')), 'cleanup debt remains')
    # Go's lazy netpoll initialization may retain a few process-global FDs.
    need(final['fd'] <= samples[0]['fd'] + 8, 'unexpected final FD growth')
    need(observed['result'] == 'PASS' and not observed['counter_errors'] and not observed['stop_reason'], 'OS counters unverified/stopped')
    os_samples = observed['samples']
    need(len(os_samples) >= 3, 'missing RSS/available-memory observation')
    for s in os_samples:
        need(numeric(s['process_tree_rss_bytes']) and s['process_tree_rss_bytes'] > 0, 'RSS absent')
        need(numeric(s['available_memory_bytes']) and s['available_memory_bytes'] > 0, 'available memory absent')
        need(str(go['pid']) in s['members'] and sum(s['members'].values()) == s['process_tree_rss_bytes'], 'wrong process-tree observation')
        need(s['process_tree_rss_bytes'] - os_samples[0]['process_tree_rss_bytes'] <= resources['incremental_rss_ceiling_bytes'], 'RSS ceiling breach')
    retention = []
    for s, end in retained_samples:
        candidates = [o for o in os_samples if s['unix_ns'] <= o['unix_ns'] <= end['unix_ns']]
        need(candidates, 'retained baseline has no aligned RSS/available-memory sample')
        o = candidates[0]
        retention.append({'baselines': s['baselines'], 'fd': s['fd'],
                          'physical_pool_connections': s['physical_pool_connections'],
                          'temp_bytes': s['linked_temp_bytes'] + s['unlinked_file_bytes'],
                          'rss_bytes': o['process_tree_rss_bytes'],
                          'available_memory_bytes': o['available_memory_bytes']})
    return {'cap': cap, 'parallel': parallel, 'result': 'PASS', 'retention': retention,
            'fd_baseline_peak_final': [samples[0]['fd'], max(s['fd'] for s in samples), final['fd']],
            'sampled_rss_peak_bytes': max(s['process_tree_rss_bytes'] for s in os_samples),
            'available_memory_min_bytes': min(s['available_memory_bytes'] for s in os_samples)}


def validate_host(directory, expected, expected_host=None):
    directory = Path(directory)
    report = json.loads((directory / 'host.json').read_text())
    need(report['source_commit'] == expected, 'source SHA mismatch')
    need(report['source_inventory_sha256'] == source_identity(ROOT), 'source bytes mismatch')
    need(report['toolchain'] == 'go1.26.10', 'wrong Go toolchain')
    resources = json.loads((ROOT / 'docs/reviews/v06x-fixture-acceptance.json').read_text())['resources']
    need(set(report['inputs_sha256']) == set(input_paths(resources)), 'input identity inventory missing')
    for path, sha in report['inputs_sha256'].items():
        need(digest(ROOT / path) == sha, 'input bytes mismatch: ' + path)
    if expected_host:
        need((report['host']['system'], report['host']['architecture']) == HOSTS[expected_host], 'wrong host architecture')
        if expected_host == 'macos-15':
            need(report['host']['version'].split('.')[0] == '15', 'CI Mac receipt must be macOS15')
    need(report['result'] == 'PASS', 'host campaign incomplete')
    need(len(report['modes']) == 4, 'missing cap/parallel modes')
    modes = set()
    for row in report['modes']:
        cap, parallel = row['cap'], row['parallel']
        modes.add((cap, parallel))
        mode = directory / ('cap%d-parallel%d' % (cap, parallel))
        derived = validate_mode(json.loads((mode / 'go.json').read_text()), json.loads((mode / 'os.json').read_text()), cap, parallel, resources)
        need(row == derived, 'host summary differs from raw observations')
    need(modes == {(c, p) for c in (1, 2) for p in (1, 4)}, 'mode census incomplete')
    validate_guard_probe(json.loads((directory / 'guard-probe/go.json').read_text()))
    need(report['guard_probe'] == 'PRE_ADMISSION_FD_STOP_CONFIRMED', 'guard negative control missing')
    timing = report['three_time_outcomes']
    need(timing['first_test_setup']['elapsed_seconds'] > 0 and timing['second_test_edits']['added_lines'] > 0,
         'first/second-test observations missing')
    need(timing['second_test_edits']['repeated_lifecycle_lines'] == 0 and timing['repeat_batch_elapsed'] == 'per-mode warmup plus three observed batches', 'repeated lifecycle/timing missing')
    need(timing['human_authoring_minutes'] is None and timing['acquisition_state'] == 'unmeasured; existing Go toolchain/module cache', 'invented cold/human-time claim')
    sums = json.loads((directory / 'SHA256SUMS.json').read_text())
    required = {'host.json', 'first-test.txt', 'second-test.txt', 'guard-probe/go.json',
                'guard-probe/os.json', 'guard-probe/stdout.txt'} | {
        'cap%d-parallel%d/%s' % (c, p, name) for c in (1, 2) for p in (1, 4)
        for name in ('go.json', 'os.json', 'stdout.txt')}
    need(required <= sums.keys(), 'receipt checksum inventory incomplete')
    for name, sha in sums.items():
        path = directory / name
        need(path.is_relative_to(directory) and '..' not in Path(name).parts and digest(path) == sha, 'receipt checksum mismatch')
    return report


def validate_guard_probe(go):
    need(go['result'] == 'STOP' and go['stop_reason'] == 'FD headroom guard', 'guard did not STOP')
    need(go['cleanup_complete'] is True and go['peak_children'] == 0
         and go['new_fixture_seconds'] == 0 and not go['phases'], 'guard admitted a source/child')
    need(go['samples'] and all(s['children'] == 0 and s['baselines'] == 0
                              and s['physical_pool_connections'] == 0 for s in go['samples']),
         'guard-probe owner accounting missing')


def run(expected, output):
    require_commit(ROOT, expected)
    need(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == expected, 'checkout SHA mismatch')
    need(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT), 'campaign requires clean candidate')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    plan = json.loads((ROOT / 'docs/reviews/v06x-fixture-acceptance.json').read_text())
    resources = plan['resources']
    profile = host_profile()
    version = subprocess.check_output(['go', 'version'], text=True).split()[2]
    need(version == 'go1.26.10', 'requires Go1.26.10')
    inputs = input_paths(resources)
    need(digest(ROOT / resources['retention_input']['path']) == resources['retention_input']['sha256'], 'SQL fixture changed')
    report = {'result': 'RUNNING', 'source_commit': expected, 'source_inventory_sha256': source_identity(ROOT),
              'toolchain': version, 'host': profile, 'inputs_sha256': {p: digest(ROOT / p) for p in inputs},
              'ci': {k: os.getenv(k) for k in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_JOB')}, 'modes': []}
    write(output / 'host.json', report)
    try:
        # Observe an actual first test and the additive second test from the guide.
        code = (ROOT / 'docs/go-prepared-fixture.md').read_text().split('```go\n', 1)[1].split('```', 1)[0]
        first, second = code.split('func TestSeed', 1)
        first_path, second_path = output / 'first_test.go', output / 'second_test.go'
        first_path.write_text(first)
        second_code = 'package app_test\nimport "testing"\nfunc TestSeed' + second
        second_path.write_text(second_code)
        first_result = run_command(['go', 'test', str(first_path), '-count=1', '-timeout=3m'], output / 'first-test.txt')
        second_result = run_command(['go', 'test', str(first_path), str(second_path), '-count=1', '-timeout=3m'], output / 'second-test.txt')
        report['three_time_outcomes'] = {
            'first_test_setup': {**first_result, 'authored_lines': len(first.splitlines()), 'steps': ['copy first test + TestMain preparation', 'go test']},
            'second_test_edits': {**second_result, 'added_lines': len(second_code.splitlines()), 'repeated_lifecycle_lines': 0, 'steps': ['add second test using fixture.DB(t)', 'go test both tests']},
            'repeat_batch_elapsed': 'per-mode warmup plus three observed batches',
            'human_authoring_minutes': None, 'acquisition_state': 'unmeasured; existing Go toolchain/module cache'}
        binary = output / 'fixture.test'
        report['build'] = run_command(['go', 'test', '-p', '1', '-c', '-tags=integration', './mariamemtest', '-o', str(binary)], output / 'build.txt')
        report['binary_sha256'] = digest(binary)
        limits = output / 'limits.json'
        write(limits, {k: resources[k] for k in ('owned_disk_ceiling_bytes', 'min_free_disk_bytes', 'min_fd_headroom')})
        for cap in (1, 2):
            for parallel in (1, 4):
                directory = output / ('cap%d-parallel%d' % (cap, parallel))
                (directory / 'runtime-tmp').mkdir(parents=True)
                env = dict(os.environ, TMPDIR=str(directory / 'runtime-tmp'), MARIAMEM_G1_CAP=str(cap),
                           MARIAMEM_G1_REPORT=str(directory / 'go.json'), MARIAMEM_G1_LIMITS=str(limits),
                           MARIAMEM_G1_SQL=str(ROOT / resources['retention_input']['path']))
                command = [str(binary), '-test.run=^TestFixtureCampaign$', '-test.parallel='+str(parallel), '-test.timeout=5m', '-test.v']
                observe(command, directory, env, resources)
                go = json.loads((directory / 'go.json').read_text())
                observed = json.loads((directory / 'os.json').read_text())
                report['modes'].append(validate_mode(go, observed, cap, parallel, resources))
        probe = output / 'guard-probe'
        (probe / 'runtime-tmp').mkdir(parents=True)
        probe_limits = probe / 'limits.json'
        strong_limits = json.loads(limits.read_text())
        strong_limits['min_fd_headroom'] = 1 << 62  # Intentionally impossible, never a relaxed positive budget.
        write(probe_limits, strong_limits)
        env = dict(os.environ, TMPDIR=str(probe / 'runtime-tmp'), MARIAMEM_G1_CAP='1',
                   MARIAMEM_G1_REPORT=str(probe / 'go.json'), MARIAMEM_G1_LIMITS=str(probe_limits),
                   MARIAMEM_G1_SQL=str(ROOT / resources['retention_input']['path']))
        try:
            observe([str(binary), '-test.run=^TestFixtureCampaign$', '-test.parallel=1', '-test.timeout=5m', '-test.v'], probe, env, resources)
        except ValueError:
            pass  # The negative control must fail; inspect the original STOP receipt below.
        validate_guard_probe(json.loads((probe / 'go.json').read_text()))
        report['guard_probe'] = 'PRE_ADMISSION_FD_STOP_CONFIRMED'
        need(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT), 'source became dirty during campaign')
        report['result'] = 'PASS'
    except Exception as exc:
        report['result'], report['error'] = 'FAIL', str(exc)
        raise
    finally:
        write(output / 'host.json', report)
        sums = {p.relative_to(output).as_posix(): digest(p) for p in sorted(output.rglob('*'))
                if p.is_file() and p.suffix in ('.json', '.txt') and p.name != 'SHA256SUMS.json'}
        write(output / 'SHA256SUMS.json', sums)
    validate_host(output, expected)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--validate-matrix', type=Path)
    args = parser.parse_args()
    if args.validate_matrix:
        for host in HOSTS:
            path = args.validate_matrix / ('go-fixture-host-' + host + '-' + args.expected_source_commit)
            validate_host(path, args.expected_source_commit, host)
        print('G1_BOTH_HOST_CAMPAIGN_PASS')
    else:
        need(args.output is not None, '--output required')
        run(args.expected_source_commit, args.output)
        print('G1_HOST_CAMPAIGN_PASS')


if __name__ == '__main__':
    main()
