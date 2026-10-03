#!/usr/bin/env python3
"""Compare the accepted A+B candidate with both retained canonical baselines."""
import argparse
import hashlib
import json
from pathlib import Path

from final_latency import distribution
from v04_direct_link_report import comparison, observations, orm_summary, pair

ROOT = Path(__file__).resolve().parents[1]


def table(rows, title):
    lines = [title, '', '| Metric (p50 / p95) | Baseline | Final | Delta absolute; relative | Verdict p50 / p95 |',
             '| --- | ---: | ---: | ---: | --- |']
    for i in range(0, len(rows), 2):
        a, b = rows[i:i+2]
        precision = 3 if a['unit'] in ('s', 'CPU-sec') else 1
        fmt = lambda v: f'{v:.{precision}f}'
        lines.append(f"| {a['metric']} ({a['unit']}) | {fmt(a['baseline'])} / {fmt(b['baseline'])} | "
                     f"{fmt(a['candidate'])} / {fmt(b['candidate'])} | "
                     f"{a['absolute_delta']:+.{precision}f} / {b['absolute_delta']:+.{precision}f}; "
                     f"{a['relative_delta_percent']:+.1f}% / {b['relative_delta_percent']:+.1f}% | "
                     f"{a['verdict']} / {b['verdict']} |")
    return lines


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('candidate', 'orm', 'acceptance', 'allocation'):
        p.add_argument('--'+n, type=Path, required=True)
    a = p.parse_args()
    new, orm, acceptance, alloc = [json.loads(f.read_text()) for f in (a.candidate, a.orm, a.acceptance, a.allocation)]
    if not new['completed'] or not orm['completed'] or new['source_commit'] != orm['source_commit'] or new['source_commit'] != acceptance['source_commit']:
        raise ValueError('incomplete campaign or candidate identity mismatch')
    if new['runtime_kind'] != 'direct-linked generated-Go':
        raise ValueError('wrong runtime')
    old = json.loads((ROOT/'benchmarks/v04-baseline-values.json').read_text())
    previous = json.loads((ROOT/'benchmarks/v04-direct-link-values.json').read_text())
    suites = orm_summary(orm)
    comparisons = {name: comparison(base, new, base['orm_summary'], suites)
                   for name, base in [('wasmer', old), ('previous_direct_link', previous)]}
    phases = {'snapshot_ms': [], 'total_alloc_mib': [], 'export_shutdown_ms': [], 'publish_ms': []}
    for sample in alloc['samples']:
        if not sample['isolation_pass'] or not sample['corruption_rejected']:
            raise ValueError('allocation diagnostic correctness failure')
        phases['snapshot_ms'].append(sample['snapshot_ms'])
        phases['total_alloc_mib'].append(sample['total_alloc_delta']/2**20)
        events = {e['name']: e['offset_ns'] for t in sample['traces'] if t['operation'] == 'snapshot' for e in t['events']}
        phases['export_shutdown_ms'].append((events['export_acknowledged']-events['sessions_drained'])/1e6)
        phases['publish_ms'].append((events['snapshot_published']-events['guest_stopped'])/1e6)
    summaries = {k: distribution(v) for k, v in phases.items()}
    raw = {n: hashlib.sha256(getattr(a, n).read_bytes()).hexdigest() for n in ('candidate', 'orm', 'acceptance', 'allocation')}
    evidence = {k: v for k, v in new.items() if k != 'trials'}
    evidence.update(acceptance=acceptance, comparisons=comparisons, orm_summary=suites,
                    orm_packages=orm['packages'], python_host_manifest=orm['native_manifest'],
                    wheel_sha256=orm['wheel_origin']['archive_info']['hashes']['sha256'],
                    raw_results='$work/v04-integrated/{candidate,orm,acceptance,snapshot-allocation}.json',
                    raw_sha256=raw, allocation_summary=summaries, allocation_observations=phases,
                    startup_observations=observations([t for t in new['trials'] if t['kind']=='startup' and t['phase']=='measurement']),
                    scaling_observations=observations([t for t in new['trials'] if t['kind']=='batch' and t['phase']=='measurement'], resource=True))
    (ROOT/'benchmarks/v04-integrated-values.json').write_text(json.dumps(evidence, indent=2)+'\n')
    lines = ['# v0.4 integrated direct-link candidate: FD lifetime + cold-copy preallocation', '',
             '**V0.4 INTEGRATED CANDIDATE COMPLETE** — local normal acceptance and one canonical campaign; no tag, publication or release-readiness declaration.', '',
             '## Identity / acceptance', '',
             f"Pre-integration: `{acceptance['pre_integration_sha']}`. Measured runtime: `{new['source_commit']}` on v0.4/generated-go-integration.",
             f"A: `{acceptance['fd_commit']}`; B source recipe: `{acceptance['guest_recipe_commit']}`; B generated-artifact integration: `{new['source_commit']}`.",
             f"Guest: `{acceptance['guest_sha256']}`; generated provenance: `{acceptance['generated_provenance_sha256']}`.",
             f"{acceptance['hardware']}; {acceptance['os'].replace(chr(10), '; ')}; {new['go_version']}; Python {orm['python']}; dependencies {orm['packages']}.",
             'Canonical source→WASM SHA matches the separately built lane B artifact, without experimental.patch. A fresh converter produces the identical entire input manifest/inventory. Repeated canonical generated-runtime installation is byte-identical, including provenance. Exact source/tool pins and build evidence are in release/generated-go-{inputs,translation,build}.json.',
             'Handwritten runtime/FD/MemFS/thread/TLS/futex adapters are unchanged. Required image provenance is regenerated, not removed; those images are unused by ordinary Go startup.', '',
             '| Acceptance | Result |', '| --- | --- |']
    lines += [f'| {k} | {v} |' for k, v in acceptance['gates'].items()]
    lines += ['', 'The original checkout retains unrelated user-owned npm files. Its publication allowlist rejects them. The exact measured commit passes canonical check in a managed clean checkout (393 Python PASS / 6 optional skips / public 554 files); no checker rule or user file was changed. Normal integration and held-FD regression run on the integration checkout. Python uses a clean-checkout installed host-only wheel. Linux image cross-compilation passes; native Ubuntu release acceptance is not claimed by this local campaign.', '',
              '## Method', '',
              'The original public API fixture/harness is unchanged. 2 startup warmups + 30 independent processes; 1 scaling warmup per size + 10 independent processes each for ×1/4/8/16, round-robin. SQLAlchemy 10/50/100 Start/Fork: 3 order-balanced suite runs, existing v0.3 CRUD fixture, preparation/Snapshot/final cleanup included. Go then ORM run sequentially with no competing heavy workload. No slow runs excluded.',
              new['memory_boundary'], new['cpu_boundary'],
              'Physical footprint is the historical primary counter; RSS is separate. Incremental=(G(n)−G(0))/n. No forced GC in the canonical path. Historical Wasmer OS 27.0 versus current 27.0.1 is an uncontrolled patch-level caveat; previous direct-link uses the same current OS. Classification: each p50/p95 independently, ≤5% approximately unchanged; descriptive, not a significance test.',
              'Raw ignored results: $work/v04-integrated; exact digests and compact observations: [values](v04-integrated-values.json). A final report-only commit follows the measured runtime SHA and does not change its code.', '']
    lines += table(comparisons['wasmer'], '## A. Wasmer → integrated candidate')
    lines += ['']+table(comparisons['previous_direct_link'], '## B. Previous direct-link → integrated candidate')
    lines += ['', '## Startup tails / scaling', '', '| Boundary | min / p50 / p95 / max ms | ≥500 / ≥900 ms |', '| --- | ---: | ---: |']
    for k, d in new['startup'].items():
        lines.append(f"| {k} | "+' / '.join(f'{d[q]*1000:.1f}' for q in ('min','p50','p95','max'))+f" | {d['ge500ms']} / {d['ge900ms']} |")
    lines += ['', 'Start has two ~1-second trials; raw API-return timestamps place the gap before Start returns (1.042/1.050 s), with first SQL ~1 ms later. This is consistent with the documented guest-side tail shape, but the campaign did not enable direct wait/wake tracing, so no per-trial page-cleaner causal proof is claimed. No timeout, synchronization or MariaDB setting was changed. Fork p95 regresses versus previous direct-link, while both quantiles improve versus Wasmer. The two 15-trial halves have Fork p95 173.9/251.2 ms, so the upper-tail regression is observed in the whole campaign but stable repeatability is not established. Canonical Fork phase tracing was off. Post-GC diagnostic Forks have a different allocator/hash-walk boundary and are not used to attribute that regression. No repeat campaign or optimization was performed.', '',
              '| DBs | G(0) physical MiB p50/p95 | ready physical MiB p50/p95 | ready RSS MiB p50/p95 | after Close physical MiB p50/p95 |', '| ---: | ---: | ---: | ---: | ---: |']
    for g in new['scaling']['groups']:
        lines.append(f"| {g['workers']} | "+' | '.join(pair(g[k],1/2**20) for k in ('baseline_primary_bytes','ready_primary_bytes','ready_rss_bytes','after_close_primary_bytes'))+' |')
    lines += ['', '## ORM suites (three runs/mode)', '', '| Tests | Mode | suite seconds p50/p95 | preparation seconds p50/p95 |', '| ---: | --- | ---: | ---: |']
    for suite in suites:
        lines.append(f"| {suite['tests']} | {suite['mode']} | {pair(suite['suite'],1,3)} | {pair(suite['setup'],1,3)} |")
    lines += ['', 'The ×4 ready median regression versus Wasmer is removed; all four scaling p95 values improve versus the previous direct-link campaign, without proof assigning that improvement solely to preallocation; its p95 is approximately unchanged. All prepared-scaling immediate Close footprints retain ≥95% of ready footprint (see compact observations). This is still a resource concern. Preserve the prior **OS PHYSICAL ACCOUNTING DOMINATES** finding: large guest/FS Go objects become unreachable and diagnostic GC reduced live HeapAlloc approximately to zero. These counters do not prove exclusive active-DB bytes or a live-object leak, and they are not declared harmless/immediately reclaimable. Lower churn can alter allocator/OS accounting history; changed footprint/RSS is reported without a specific causal attribution.', '',
              '## Snapshot allocation / phases', '', '| Diagnostic metric | experiment before | experiment after | integrated diagnostic (n=5) |', '| --- | ---: | ---: | ---: |']
    for k, before, after in [('total_alloc_mib',914.83,278.17),('snapshot_ms',459.20,384.69),('export_shutdown_ms',171.05,97.73),('publish_ms',209.39,208.61)]:
        lines.append(f"| {k} | {before:.2f} | {after:.2f} | {summaries[k]['p50']:.2f} |")
    lines += ['', 'The integrated diagnostic uses five fresh processes after the canonical campaign; GC/profile and checksum walks occur only after measured boundaries. Every diagnostic child fixture/write/schema/rollback/base-hash/shutdown/corruption check passes. Its small-sample latency must not replace the 30-run canonical Snapshot result. Phase medians are independent and do not sum to the API median. One integrated post-Snapshot diagnostic-GC inuse profile totals about 386.9 KiB sampled, with no dominant guest/FS allocation, supporting the prior ownership finding; it does not measure OS reclamation.',
              'Known-size cold regular copy now pre-sizes its exclusive destination with existing ftruncate before the unchanged 64 KiB copy loop. Seven C lines, no global MemFS growth change. The prior ~775 MiB destination growth history is materially reduced: actual Snapshot TotalAlloc remains ~278 MiB versus ~915 MiB, matching the lane’s ~636 MiB sampled resize reduction. Publication is not optimized. Snapshot still owns ~138 MiB of cold on-disk data, not the exited guest/MemFS. No CoW, format/API change, ready-heap restoration or production GC/scavenging policy is introduced.', '',
              '## Remaining scope / next decision', '',
              'Highest-priority remaining resource issue is substantial and non-monotonic prepared-scaling/post-Close physical/RSS footprint. Attribution precedes any allocator/mapping change. Separately record Start’s sampled tail-frequency/p95 and Fork p95 versus previous direct-link as bounded future performance questions; do not infer a new synchronization bug or fix them here.',
              'Generated-Go/direct-link preserves the measured startup/Fork/CPU/ORM Fork and normal Go distribution improvements: no per-DB executable provisioning, guest subprocess, Wasmer/NativeDir/cache dependency for Options{}. Legacy fallback and encoded images/provisioning/bundle metadata remain isolated; packaging deletion is deferred.',
              'Deferred: immutable Snapshot backing/CoW, deeper Snapshot publish work, mmap linear memory, full shared-memory race adaptation, forced guest kill/failure containment, legacy Wasmer removal, Go1.27.0/1.27.1 arm64 workaround, and MariaDB stable-version migration. No mariamem compiler workaround is used; those arm64 versions remain unsupported pending upstream-fixed Go. No v0.5 work starts here.', '',
              '**V0.4 INTEGRATED CANDIDATE COMPLETE**']
    (ROOT/'benchmarks/v04-integrated-candidate.md').write_text('\n'.join(lines)+'\n')
    print('Wrote integrated report and compact evidence')


if __name__ == '__main__':
    main()
