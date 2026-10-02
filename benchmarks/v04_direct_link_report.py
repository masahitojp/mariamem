#!/usr/bin/env python3
"""Render the canonical direct-link comparison without filtering slow trials."""
import argparse
import hashlib
import json
from pathlib import Path

from final_latency import distribution

ROOT = Path(__file__).resolve().parents[1]
MIB = 2**20


def classify(old, new):
    delta = new/old - 1
    return 'approximately unchanged' if abs(new-old) <= old*.05 else ('improved' if delta < 0 else 'regressed')


def orm_summary(report):
    result = []
    for n in (10, 50, 100):
        for mode in ('start', 'fork'):
            rows = [s for s in report['suites'] if s['phase'] == 'measurement' and s['tests'] == n and s['mode'] == mode]
            if len(rows) < 3 or any(len(s['samples']) != n for s in rows):
                raise ValueError('incomplete ORM suite')
            result.append(dict(tests=n, mode=mode, suite=distribution([s['suite_seconds'] for s in rows]),
                               setup=distribution([s['setup_seconds'] for s in rows]),
                               ready=distribution([v['ready_seconds'] for s in rows for v in s['samples']]),
                               workload=distribution([v['workload_seconds'] for s in rows for v in s['samples']])))
    return result


def compact(value):
    """Keep OS counters/observations, replacing incidental PID indexes by counts."""
    if isinstance(value, list):
        return [compact(x) for x in value]
    if isinstance(value, dict):
        return {k: ([compact(v) for v in x.values()] if k == 'members' else compact(x))
                for k, x in value.items() if k not in ('pid', 'runtime_pid', 'host_pid')}
    return value


def observations(trials, resource=False):
    """Retain scenario values/timelines, not repeated build metadata or probe queries."""
    result = []
    for t in trials:
        samples = t['report']['samples']
        if not resource:
            samples = [x for x in samples if x['case'] in ('start_first_sql', 'start_seeded', 'snapshot', 'fork_first_sql')]
            samples = [{k: v for k, v in x.items() if k in ('case', 'workers', 'phase', 'run', 'latency_seconds', 'api_return_seconds', 'per_db', 'stage_timings')}
                       for x in samples]
        result.append({'round': t['round'], 'workers': t['workers'], 'status': t['status'], 'samples': compact(samples)})
    return result


def pair(d, scale=1, precision=1):
    return f"{d['p50']*scale:.{precision}f} / {d['p95']*scale:.{precision}f}"


def comparison(old, new, orm_old, orm_new):
    rows = []
    def add(label, before, after, scale, unit):
        for q in ('p50', 'p95'):
            b, a = before[q]*scale, after[q]*scale
            rows.append(dict(metric=label, quantile=q, unit=unit, baseline=b, candidate=a,
                             absolute_delta=a-b, relative_delta_percent=(a/b-1)*100,
                             verdict=classify(b, a)))
    for k, label in [('start_first_sql', 'Start → first SQL'), ('start_seeded', 'Start → 1,000 rows'),
                     ('fork_first_sql', 'prepared Fork → COUNT'), ('snapshot', 'Snapshot')]:
        add(label, old['startup'][k], new['startup'][k], 1000, 'ms')
    for before, after in zip(old['scaling']['groups'][:-1], new['scaling']['groups'][:-1]):
        add(f"×{after['workers']} group-ready", before['group_ready_seconds'], after['group_ready_seconds'], 1, 's')
    a, b = old['scaling']['groups'][-1], new['scaling']['groups'][-1]
    for k, label, scale, unit in [('group_ready_seconds', '×16 group-ready', 1, 's'),
                                 ('average_incremental_bytes', '×16 incremental physical / DB', 1/MIB, 'MiB'),
                                 ('ready_primary_bytes', '×16 total physical', 1/MIB, 'MiB'),
                                 ('combined_cpu_seconds', '×16 CPU', 1, 'CPU-sec'),
                                 ('after_close_primary_bytes', 'after Close physical', 1/MIB, 'MiB')]:
        add(label, a[k], b[k], scale, unit)
    for mode in ('start', 'fork'):
        before = next(s for s in orm_old if s['tests'] == 100 and s['mode'] == mode)
        after = next(s for s in orm_new if s['tests'] == 100 and s['mode'] == mode)
        add('SQLAlchemy100 '+mode, before['suite'], after['suite'], 1, 's')
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('candidate', type=Path)
    p.add_argument('orm', type=Path)
    p.add_argument('--baseline', type=Path, default=ROOT/'benchmarks/v04-baseline-values.json')
    p.add_argument('--acceptance', type=Path, required=True)
    p.add_argument('--attribution', type=Path)
    p.add_argument('--fresh-resources', type=Path)
    p.add_argument('--output', type=Path, default=ROOT/'benchmarks/v04-direct-link-baseline.md')
    args = p.parse_args()
    new, orm, old, acceptance = [json.loads(f.read_text()) for f in (args.candidate, args.orm, args.baseline, args.acceptance)]
    if not new['completed'] or not orm['completed'] or new['runtime_kind'] != 'direct-linked generated-Go':
        raise ValueError('incomplete or wrong-runtime measurement')
    suites = orm_summary(orm)
    comparisons = comparison(old, new, old['orm_summary'], suites)
    batches = [t for t in new['trials'] if t['kind'] == 'batch' and t['phase'] == 'measurement']
    if any(t['status'] != 'pass' for t in new['trials']):
        raise ValueError('failed trial; do not render a complete baseline')
    for t in batches:
        for state in ('baseline', 'ready', 'after_close'):
            if len(t['report']['samples'][0][state]['members']) != 1:
                raise ValueError('unexpected process boundary')
    evidence = {k: new[k] for k in ('schema_version', 'source_commit', 'runtime_kind', 'environment', 'go_version',
                'benchmark', 'scenario_version', 'settings', 'boundary', 'memory_boundary', 'cpu_boundary',
                'runs', 'scaling_runs', 'startup', 'scaling', 'harness_sha256', 'binary_sha256', 'helper_sha256', 'helper_source_sha256')}
    evidence.update(completed=True, acceptance=acceptance, comparison=comparisons, orm_summary=suites,
                    startup_observations=observations([t for t in new['trials'] if t['kind'] == 'startup' and t['phase'] == 'measurement']),
                    scaling_observations=observations(batches,resource=True),
                    runner_environment=new['trials'][0]['report']['environment'],
                    orm_suites=orm['suites'], orm_packages=orm['packages'],
                    orm_workload_sha256=orm['workload_sha256'], orm_harness_sha256=orm['harness_sha256'],
                    python_host_manifest=orm['native_manifest'],
                    wheel_sha256=orm['wheel_origin']['archive_info']['hashes']['sha256'],
                    baseline_source=old['source_commit'], classification_policy='Each p50/p95 separately: ≤5% relative difference approximately unchanged; lower improved; higher regressed. Descriptive, not statistical significance.',
                    raw_sha256={f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in (args.candidate, args.orm, args.acceptance)})
    if args.attribution:
        attribution = json.loads(args.attribution.read_text())
        evidence['attribution'] = {'scope': attribution['scope'], 'coarse_phase_summary': attribution['coarse_phase_summary'],
                                   'observations': [compact([x for x in t['samples'] if x['case'] in ('start_first_sql','snapshot','fork_first_sql')]) for t in attribution['trials']]}
        evidence['raw_sha256'][args.attribution.name] = hashlib.sha256(args.attribution.read_bytes()).hexdigest()
    if args.fresh_resources:
        fresh = json.loads(args.fresh_resources.read_text())
        if not fresh['completed'] or fresh['source_commit'] != new['source_commit']:
            raise ValueError('incomplete or wrong-source fresh resources')
        evidence['fresh_start_resources'] = {k: fresh[k] for k in ('source_commit','runtime_kind','boundary','cpu_boundary','memory_boundary','fresh_resources','binary_sha256','helper_sha256')}
        evidence['fresh_start_resources']['observations'] = observations(fresh['trials'],resource=True)
        evidence['raw_sha256'][args.fresh_resources.name] = hashlib.sha256(args.fresh_resources.read_bytes()).hexdigest()
    dest = args.output.with_name('v04-direct-link-values.json')
    dest.write_text(json.dumps(evidence, indent=2)+'\n')
    lines = ['# v0.4 production direct-link canonical baseline', '',
             '**DIRECT-LINK CANONICAL BASELINE COMPLETE** — normal functional scope; not a tag, publication, full race acceptance or final release-readiness declaration.', '',
             '## Source / environment', '',
             f"Measured source: `{new['source_commit']}`; runtime: **direct-linked generated-Go**; branch `v0.4/generated-go-integration`.",
             f"{new['environment']['platform']}; {acceptance['hardware']}; `{new['go_version']}`; Python {orm['python']}.",
             f"Historical reference: same hardware/toolchain, macOS 27.0 (26A428). Current OS: {acceptance['os']}. The OS patch difference is an uncontrolled comparison caveat; boundaries/fixtures remain unchanged.",
             f"Compiled guest: `{orm['native_manifest']['guest_sha256']}`. Fresh Python host SHA-256: `{orm['native_manifest']['sha256']['mariamem-host']}`.",
             f"[Compact observations, hashes and comparisons]({dest.name}); full raw logs/results are disposable ignored work data.",
             'Runtime/Go harness source is committed at the measured SHA. The environment records a dirty tree because unrelated untracked npm metadata and new report tooling existed; neither participates in the measured runtime. No production/runtime implementation changed in this task.',  '',
             '## Production path / acceptance', '',
             '`Options{}` → host/MySQL wire → `guest.startLinked` → fresh `generatedgo.StartInstance`, all inside the Go consumer. No guest executable decode/write/checksum, guest subprocess, NativeDir resolution, Wasmer discovery/download or native cache. Python uses one installed host executable with the guest directly linked; it is a separate distribution/API boundary.',
             'Fresh per-DB linear memory, thread/TLS/FD state, MemFS and prepared writable state; consuming cold Snapshot and verified independent Fork. No live heap/worker restoration, process fork, new CoW or runtime sharing.', '',
             '| Gate | Result |', '| --- | --- |',
             '| Go unit checks / scoped vet / generated provenance | PASS |',
             '| Non-race core/protocol/auth/CLIENT_FOUND_ROWS/sessions/MaxSessions/reconnect | PASS |',
             '| Repeated/concurrent independent DBs, normal shutdown | PASS |',
             '| Empty PATH/cache default; Snapshot/multiple Forks/fixture/write/schema isolation/corruption | PASS |',
             '| Focused FD/MemFS/prepared-file/thread/TLS/futex/runtime race tests | PASS |',
             '| Installed-wheel SQLAlchemy | 44/44 |', '| External GORM Options{} / repeated AutoMigrate | 32/32 |',
             '| Full generated guest `-race` diagnostic | FAIL — known limitation, explicitly rerun; not a v0.4 gate |',
             '| Python forced query-timeout reclamation diagnostic | FAIL — guest cleanup deadline; separate failure-containment scope, unchanged test retained |', '',
             'Ordinary checkout Python checks: 388 pass / 3 skip; the publication-source test rejects unrelated user-owned untracked npm files. Six new scope/report tests pass separately. A managed Git checkout without those unrelated files passes the normal Go checks, scoped vet, generated provenance, Python checks (392 pass / 6 optional skips) and public-source scan. The user files were not changed.',
             'The forced-timeout diagnostic does not pass and is not advertised as passing. Normal Close/session checks pass; arbitrary failure containment remains a separate decision. This report is the requested normal-path performance baseline.', '',
             '## Method / reproduction', '',
             'Run acceptance first, then each benchmark alone, with no tests/builds concurrently. No optimization or MariaDB configuration changes. No slow-run filtering, forced GC, OS-cache flush or shortened timeouts.',
             'Startup: 2 warmups + 30 independent Go processes, each using the existing 1,000-row InnoDB fixture and public API. Start→SELECT 1 excludes schema/seed; Start→fixture includes them. Snapshot starts after disconnect acknowledgement and consumes its source. Fork→COUNT excludes base preparation and Snapshot.',
             'Scaling: each ×1/×4/×8/×16 has 1 warmup + 10 independent processes, round-robin; isolated forks of a 1,000-row prepared Snapshot. G(0) is the post-preparation holder without live DBs; G(n) is the same owning Go process at all-ready.',
             'CPU: G(0)→all-ready owning-process counters, including observer/version-query collection; excludes fixture preparation and teardown. Sampling: 50 ms + scan overhead.',
             'Memory: historical canonical `primary_bytes` is macOS process-tree **physical footprint**, confirmed from the original report/helper; RSS remains separate. Incremental=(G(n)−G(0))/n. Immediate after-Close is measured before snapshot-holder process exit, with no forced GC; Go heap retention stays visible. OS physical accounting is not an exclusive allocation proof.',
             'SQLAlchemy: unchanged v0.3 `test_03_update_commit_and_delete`, normal QueuePool, identical schema/seed/CRUD/relationship reads in Start and Fork. 10/50/100 tests × 3 suites/mode; base preparation/Snapshot/final cleanup included in Fork suite total. Installed-wheel Python+host boundary; not an in-process Go latency measurement.', '',
             '```sh', 'GOTOOLCHAIN=go1.26.8 python benchmarks/v04_candidate.py --runs 30 --scaling-runs 10 --json /path/to/work/candidate.json',
             '# installed host-only wheel, pinned SQLAlchemy/PyMySQL/pytest; no native override',
             '/path/to/installed/python benchmarks/v04_orm.py --runs 3 --json /path/to/work/orm.json',
             'python benchmarks/v04_direct_link_report.py /path/to/work/candidate.json /path/to/work/orm.json --acceptance /path/to/work/acceptance.json', '```', '',
             '## Canonical comparison', '',
             'Each quantile is classified independently. ≤5% relative difference is “approximately unchanged”; this descriptive rule is not a significance test. Baseline values use full historical precision before rounding.', '',
             '| Metric | Wasmer baseline | direct-link generated-Go | delta | verdict |', '| --- | ---: | ---: | ---: | --- |']
    for r in comparisons:
        precision = 3 if r['unit'] in ('s', 'CPU-sec') else 1
        lines.append(f"| {r['metric']} {r['quantile']} ({r['unit']}) | {r['baseline']:.{precision}f} | {r['candidate']:.{precision}f} | {r['absolute_delta']:+.{precision}f} ({r['relative_delta_percent']:+.1f}%) | {r['verdict']} |")
    lines += ['', '## Startup distribution (ms)', '', '| Boundary | n | min | p50 | p95 | max | ≥500 ms / ≥900 ms |', '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for k, label in [('start_first_sql', 'Start→SQL'), ('start_seeded', 'Start→1,000 rows'), ('fork_first_sql', 'Fork→COUNT'), ('snapshot', 'Snapshot')]:
        d = new['startup'][k]
        lines.append(f"| {label} | {d['count']} | "+' | '.join(f"{d[q]*1000:.1f}" for q in ('min', 'p50', 'p95', 'max'))+f" | {d['ge500ms']} / {d['ge900ms']} |")
    lines += ['', '## Scaling / cleanup', '', '| DBs | trials | ready ms p50/p95 | CPU-sec p50/p95 | incremental physical MiB/DB p50/p95 | ready physical MiB p50/p95 | ready RSS MiB p50/p95 |', '| ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for g in new['scaling']['groups']:
        lines.append(f"| {g['workers']} | {g['successes']} | {pair(g['group_ready_seconds'],1000)} | {pair(g['combined_cpu_seconds'],precision=3)} | {pair(g['average_incremental_bytes'],1/MIB)} | {pair(g['ready_primary_bytes'],1/MIB)} | {pair(g['ready_rss_bytes'],1/MIB)} |")
    lines += ['', '| DBs | G(0) physical MiB p50/p95 | peak physical MiB p50/p95 | after Close physical MiB p50/p95 | after Close − G(0) MiB p50/p95 |', '| ---: | ---: | ---: | ---: | ---: |']
    for g in new['scaling']['groups']:
        lines.append(f"| {g['workers']} | "+' | '.join(pair(g[k],1/MIB) for k in ('baseline_primary_bytes','group_peak_primary_bytes','after_close_primary_bytes','after_close_minus_baseline_bytes'))+' |')
    gaps = sum(len(t['report']['samples'][0]['memory_sampling_gaps']) for t in batches)
    lines += ['', f'{len(batches)}/{len(batches)} measured batches passed. Ready/after-Close process inventory is one owning process, no runtime descendants. Startup counter gaps: {gaps}; not filled with zero, so sampled peaks may miss an edge. Normal lifecycle FD/goroutine checks pass; retained OS footprint does not distinguish live/reachable guest state, allocator retention and compressed-page accounting. No forced GC or long-lived heap soak was performed; the cause is not proved.']
    if args.fresh_resources:
        f = fresh['fresh_resources']
        lines += ['', '## Fresh Start resources — separate boundary', '',
                  '30 fresh independent processes, no prepared Snapshot/base. CPU ends at all-ready counter collection after first SELECT/version query. This is an extra observation, not a replacement for the prepared scaling boundary above.', '',
                  '| Metric | p50 / p95 |', '| --- | ---: |',
                  f"| CPU to ready (CPU-sec) | {pair(f['combined_cpu_seconds'],precision=3)} |",
                  f"| ready physical (MiB) | {pair(f['ready_primary_bytes'],1/MIB)} |",
                  f"| ready RSS (MiB) | {pair(f['ready_rss_bytes'],1/MIB)} |",
                  f"| after Close physical (MiB) | {pair(f['after_close_primary_bytes'],1/MIB)} |"]
    lines += ['', '## ORM suites', '', '| tests | mode | suite s p50/p95 | setup s p50/p95 | per-test ready ms p50/p95 | CRUD ms p50/p95 |', '| ---: | --- | ---: | ---: | ---: | ---: |']
    for s in suites:
        lines.append(f"| {s['tests']} | {s['mode']} | {pair(s['suite'],precision=3)} | {pair(s['setup'],precision=3)} | {pair(s['ready'],1000)} | {pair(s['workload'],1000)} |")
    lines += ['', 'Three suite trials give a coarse tail estimate; individual slow trials remain in evidence. All 18 measured suites / 960 isolated tests completed; GORM 32 cases are compatibility acceptance, not a comparable 100-test performance suite.', '',
              '## Known limitations / distribution / next bounded task', '',
              'The full generated guest is not Go race-detector clean. The [scope investigation](direct-link-race-scope.md) recorded 5,373 reports / 149 conflict signatures / seven broad groups and concluded **GENERAL SHARED-MEMORY MODEL WORK REQUIRED**. No suppression, `//go:norace`, function/address patch or blanket atomic rewrite is used. Focused handwritten/runtime race gates remain enabled. Re-evaluate broader memory adaptation with the planned v0.5 MariaDB/WASIX/toolchain update.',
              'Go1.27.0/1.27.1 arm64 remain unsupported because of upstream `LDPSW: constant is not in pool`; upstream fix `b3f5034b15a7a6f065e92d0617f7a473d5d9dcfa` has already built/run the unchanged consumer. No source/compiler workaround is used.',
              'Normal Go needs no Wasmer/NativeDir/native download/cache or per-DB native executable provisioning. Generated Go is ordinary module/build input; WASM is build-time intermediate. Explicit legacy NativeDir/Wasmer compatibility remains intact.',
              'Later cleanup candidates: encoded platform images in `internal/builtinruntime`, private-executable provisioning/checksum/cleanup, unused generated-guest CLI/spawn scaffolding and historical image metadata. Native bundle resolver/cache and Wasmer packaging metadata remain legacy fallback machinery; they are not all unconditionally removable. No broad packaging deletion was performed.',
              'Performance regressions and the single highest-priority bounded follow-up are discussed below. No optimization is included in this measurement task.']
    if args.attribution:
        phases = evidence['attribution']['coarse_phase_summary']
        lines += ['', '## Regression confirmation / coarse phase attribution', '',
                  'Five separate observations use only existing stage timers, outside the canonical trials. They are coarse intervals, not exclusive engine/allocator attribution; medians from different trials must not be added.', '',
                  '| Interval | n | min / p50 / max (ms) |', '| --- | ---: | ---: |']
        for name, values in phases.items():
            lines.append(f"| {name} | {values['count']} | {values['min_ms']:.1f} / {values['p50_ms']:.1f} / {values['max_ms']:.1f} |")
    snapshot_values = [s['latency_seconds'] for t in new['trials'] if t['kind'] == 'startup' and t['phase'] == 'measurement'
                       for s in t['report']['samples'] if s['case'] == 'snapshot']
    mid = len(snapshot_values)//2
    sixteen = new['scaling']['groups'][-1]
    historical = old['scaling']['groups'][-1]
    sixteen_samples = [t['report']['samples'][0] for t in batches if t['workers'] == 16]
    retained = sum(s['after_close']['primary_bytes'] >= .95*s['ready']['primary_bytes'] for s in sixteen_samples)
    four_values = [t['report']['samples'][0]['group_ready_seconds'] for t in batches if t['workers'] == 4]
    four_mid = len(four_values)//2
    four_old = old['scaling']['groups'][1]['group_ready_seconds']['p50']
    lines += ['', f"×4 group-ready regression also repeats across the two five-trial halves: p50 {distribution(four_values[:four_mid])['p50']*1000:.1f} / {distribution(four_values[four_mid:])['p50']*1000:.1f} ms versus historical {four_old*1000:.1f} ms. Existing per-worker scaling phase attribution was not enabled; no specific cause is claimed."]
    lines += ['', f"Snapshot regression repeats across both halves of the 30 independent trials: p50 {distribution(snapshot_values[:mid])['p50']*1000:.1f} / {distribution(snapshot_values[mid:])['p50']*1000:.1f} ms, versus historical {old['startup']['snapshot']['p50']*1000:.1f} ms. Slow runs are retained; max is {max(snapshot_values)*1000:.1f} ms.",
              f"×16 physical totals range from {min(s['ready']['primary_bytes'] for s in sixteen_samples)/MIB:.1f} to {max(s['ready']['primary_bytes'] for s in sixteen_samples)/MIB:.1f} MiB; {retained}/{len(sixteen_samples)} immediate post-Close samples retain ≥95% of ready footprint. Prepared-holder G(0) p50 is {sixteen['baseline_primary_bytes']['p50']/MIB:.1f} MiB. These are repeat observations, not a claim that the OS counter identifies live allocations. No forced GC, reference clearing or runtime change improved the numbers.",
              f"RSS/physical accounting must not be conflated: historical ×16 RSS p50/p95 was {pair(historical['ready_rss_bytes'],1/MIB)} MiB, now {pair(sixteen['ready_rss_bytes'],1/MIB)} MiB. Physical p50 verdict: {classify(historical['ready_primary_bytes']['p50'],sixteen['ready_primary_bytes']['p50'])}; p95: {classify(historical['ready_primary_bytes']['p95'],sixteen['ready_primary_bytes']['p95'])}. Do not substitute the separate fresh Start figure for prepared ×16 per-DB footprint.", '',
              '**Single highest-priority follow-up:** locally attribute allocation/reference lifetime and retained footprint introduced by prepared-files Snapshot preparation (the elevated G(0) footprint), then distinguish reachable state from Go allocator/OS retention before selecting a fix. Snapshot export/shutdown and publication are the existing coarse time boundaries. This is a bounded performance investigation, not another execution architecture; it is not implemented here. Fork itself improves in this canonical latency comparison.']
    for mode in ('start', 'fork'):
        ready_values = [v['ready_seconds'] for s in orm['suites'] if s['phase'] == 'measurement' and s['mode'] == mode for v in s['samples']]
        lines.append(f"SQLAlchemy {mode}: {sum(v>=.9 for v in ready_values)}/{len(ready_values)} per-test ready observations ≥900 ms; {sum(v>=.5 for v in ready_values)} ≥500 ms.")
    lines += ['', 'The known guest-side ~1s tail remains visible in the Python/host Start boundary. These trials were not individually traced to prove every slow sample is the same race; no claim that the tail was fixed.', '', '**DIRECT-LINK CANONICAL BASELINE COMPLETE.** No performance optimization, tag or publication.']
    args.output.write_text('\n'.join(lines)+'\n')
    print(args.output)
    print(dest)


if __name__ == '__main__':
    main()
