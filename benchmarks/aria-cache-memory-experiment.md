# Aria page cache: bounded memory A/B

Status: both-platform measurements completed; see [results and rejection](aria-cache-memory-results.md).
The corrected CPU rerun completed on both platforms; its valid CPU/memory
baselines and the final combined trade-off decision are recorded in that report.
No production cache setting has changed.

## Hypothesis and source boundary

The earlier plugin attribution identifies roughly 126 MiB of mapping growth
with Aria's eagerly initialized 128 MiB page cache. Mapping size and raw RSS do
not establish marginal physical cost. The hypothesis is that reducing **only**
`aria_pagecache_buffer_size` to 16 MiB materially reduces real per-instance
memory, without compromising ordinary MariaDB semantics or parallel behavior.

`guest/experimental.patch` adds the explicit 128M/16M option at the existing
embedded `mysql_server_init()` argument boundary. One instrumented WASM/AOT is
used by both conditions. An experiment-only private environment variable selects
16M; the control explicitly selects 128M. Every timed fork queries the actual
server variable after its measurement boundary and fails if it differs.
InnoDB/MyISAM settings, plugin selection, prepared RSA keys, startup integrity
validation, snapshot copy and runtime configuration are unchanged.
The experimental patch is separate from production provenance and rejected by
release verification. No experiment artifact is a release candidate.

## Running and immutable identity

Dispatch `guest-build-boundary.yml` on the exact pushed experiment branch with
`aria_memory_comparison=true`. It builds/reuses the verified WASM once and each
platform AOT once, then runs on macOS 15 arm64 and Ubuntu 24.04 x86_64 (SSE2 +
SSSE3 AOT baseline). Source/patch changes invalidate the WASM reuse identity;
AOT reuse requires the exact WASM hash and platform/runtime/settings identity.
Both conditions consume those same verified artifacts, never independently
built equivalents. Docker and Tart are absent.

The bounded runner is `benchmarks/aria_cache_ab.py --native-dir build/guest-aot`.
It uses the canonical Go runner with `--aria-memory-ab --guest-stage-timing`;
compilation and provenance collection are outside all measurements. Defaults:
1,000 rows / 32-character payload, two warmups, 20 measured rounds per condition
at each of ×1/4/8. Each round alternates A/B then B/A; worker-count groups run
sequentially. Raw output is ignored `benchmarks/results/init-aria-cache.json`;
its Markdown summary and AOT provenance are uploaded in the workflow's
`initialization-<platform>-<sha>` artifact. CI handoff is submission only: no
polling or supervision.

## Measurement scopes

- Latency: existing Fork → connection → successful fixture COUNT, separately
  per DB and barrier → all DBs ready. Existing host/guest stage timings remain.
- CPU: Go host process CPU delta from G(0) to the all-ready counter collection,
  plus runtime/guest lifetime CPU observed at that collection. Combined CPU is
  calculated from the **same** interval, not added percentile columns. Cleanup
  and correctness SQL are outside it. The version query and startup bookkeeping
  following first SQL, Go sampler overhead and sequential counter collection
  are included; `ps`/counter-helper subprocess CPU is excluded. Ubuntu uses
  `/proc/<pid>/stat` ticks; macOS uses `proc_pid_rusage` Mach CPU ticks converted using recorded
  `mach_timebase_info` (the first successful run omitted this conversion; its
  macOS CPU values are invalid).
- Memory: each batch records zero-active-DB G(0), all-ready G(n), incremental
  G(n)−G(0), incremental/n, sampled group peak, and after-Close host state.
  Group includes Go host and runtime descendants. Linux records `smaps_rollup`
  PSS and private clean/dirty/hugetlb bytes; macOS records summed physical
  footprint accounting and RSS, with private bytes explicitly unavailable.
  RSS is secondary. macOS footprint is an accounting charge, not globally unique
  physical memory; PSS may shift as external sharing changes. Unmapped kernel /
  filesystem cache is outside this process accounting. These measures
  must be interpreted separately per platform.
- Repeated cycles: all runtimes must disappear after every group Close;
  after-close memory and raw G(0) sequence expose retained Go heap / drift. No
  forced GC is used to manufacture a low baseline. Requested sampling is 50 ms
  plus recorded collection time; brief peaks may be missed. Counter failures at
  baseline/ready/after-close fail the run rather than become zero-byte savings.
  New or disappearing processes with unavailable/zero-page counters during
  startup are retained in `memory_sampling_gaps`; only complete samples enter
  group peak calculations. Other counter/parse failures still fail the run.
- Marginal growth: `(incremental(4)−incremental(1))/3` and
  `(incremental(8)−incremental(4))/4`, matched by round index. These are sequential
  group comparisons, not concurrent populations. ×8 CPU amplification is
  `CPU(8)/(8×CPU(1))` per matched round. Raw values remain available.

The 128M control establishes the consistent CPU/incremental-memory baseline
before deciding numeric KPI thresholds. No new performance pass/fail CI gate
is introduced.

## Correctness and over-cache workload

Outside the canonical timed fixture, build a separate snapshot with 24,000
unique 2,048-character Aria rows (`ROW_FORMAT=PAGE`). Require its actual `.MAD`
file to exceed 16 MiB. Setup inserts use 200 rows (about 400 KiB) per
statement to stay below the existing 1 MiB SQL/wire limit. Then fork it five times per condition in balanced order.
Verify exact count, total payload length and aggregate CRC32 against the inserted
fixture; read the full table; execute a
large GROUP BY with session-local 16 KiB temporary-table limits and require an
increase in `Created_tmp_disk_tables`. Those session settings exist only for
this identical correctness workload; they do not alter startup or timed Forks.
Record workload wall/combined CPU and before/after memory separately. A
fork-local insert must not leak into subsequent forks from the same snapshot.

The workflow also runs the existing Go race/lifecycle integration and Python
multi-client/interruption suites for **both** conditions, preserving
Snapshot/Fork, session isolation, transaction rejection, unusable-state and
cleanup semantics. The normal 1,000-row benchmark repeats create/destroy at
×1/4/8 and rejects unexpected runtime descendants.

## Decision after measurement

Accept as a production candidate only if real incremental/physical memory falls
reproducibly by roughly ≥64 MiB per DB, correctness and cleanup pass, and latency,
CPU and parallel tails show no meaningful reproducible regression. Inspect
balanced per-round differences and raw drift, not only aggregate medians.
If only mapping size changes, reject. If tail behavior is ambiguous, repeat this
same comparison; do not tune another cache/subsystem.

The v0.2 latency KPI remains ×1 p50 ≤500 ms / p95 ≤750 ms. The 600/900 ms line is
only a diagnostic regression red line; 250/500 ms remains a longer-term stretch.
CPU numeric goals and incremental-memory budgets are provisional pending this
control baseline. Existing competitive latency value is already established.
No restore/direct-WASI, VFS/CoW/runtime-sharing/continuation or public API work
is part of this experiment.
