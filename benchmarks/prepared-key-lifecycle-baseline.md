# Prepared-key Fork lifecycle baseline

Branch: `experiment/prepared-auth-keys`. Analysis only: no optimization,
production provisioning, merge or new architecture selection.

## Evidence and exact condition

Measured source: `25a02d2f516e77f749af68dfd16a263aeac3313a`.
Run: https://github.com/masahitojp/mariamem/actions/runs/36284840859.
Use the existing-key half of the completed paired experiment: 20 measured
invocations after two warmup pairs; 1,000 rows with 32-character payloads;
Go canonical runner; first successful COUNT for Fork, SELECT 1 for Start.
Per-DB n is 20/80/160 at ×1/4/8; there are 20 independent batches per level.
MacOS 15.7.9 arm64, 3 CPUs; Ubuntu 24.04.5 x86_64, 4 CPUs; Go 1.26.8,
Wasmer 7.4.2, MariaDB 13.1 embedded. Do not compare these runners as equal hardware.

[RSA experiment report](prepared-auth-keys-experiment.md) records exact ZIP
digests, WASM/AOT provenance and disposable key setup. Both downloaded ZIP
digests were verified. Raw completed reports were revalidated fail-closed:
plugin ACTIVE/public PEM match at startup; successful load, no generation
events; complete monotonic diagnostic records and no dropped events.
No configuration/cache/plugin/runtime/public-semantics changes were introduced.

The required lifecycle raw data already exists, so this task reaggregates it
instead of rerunning expensive diagnostics. These are real measured prepared-key
results, not hypothetical subtraction of RSA from an older baseline.
Post-ready memory diagnostics are present in the original run, outside first-SQL
latency; no new memory inspection or CI was performed. Long post-ready capture
may influence subsequent runner/cache conditions; this is not a diagnostic-off
confirmation run. Raw/derived JSON remains ignored under
`benchmarks/results/auth-keys-36284840859/`.

## Actual path and timing boundaries

`Snapshot.Fork` holds a reader lock, then calls public `start`: option/context
checks, `artifacts.Resolve` (native files/sidecar/build identity), temporary
directories, then `host.Start`. The host digests module metadata again and
validates snapshot inventory, prepares a transfer directory, and calls Wasmer.
Wasmer maps `/snapshot-in` and the test-key directory. Guest `multi_resident`
copies `/snapshot-in/data` to `/mariadb`, calls `l4m_open` / `mysql_server_init`,
bootstraps the embedded connection/database, initializes slot synchronization,
writes timing evidence and emits ready. Host then listens on TCP; caller connects
and verifies COUNT. Nothing is restored lazily in this baseline.

**Measured versus derived:** stage durations use monotonic offsets within one
clock scope. Public-outside-host is a duration difference:
`caller.database_returned - caller.begin - host.end`. It includes public
preparation **and** tail work after host timing (trace JSON write/return/watch);
those parts cannot be separated here. It is not exclusively artifact validation.
Combined preparation is that difference plus host metadata/snapshot validation,
computed per DB before taking quantiles.

The runtime envelope cannot directly timestamp host spawn against guest main:
clocks are independent. Its derived residual includes runtime/CRT/static setup,
scheduling, diagnostic serialization/I/O and ready delivery. It is **not pure
Wasmer overhead**. There is no independently observed AOT-init boundary.

## Fork waterfall

Values are **p50 / p95 milliseconds** per DB. Guest restore and init are nested
inside host launch→ready. Quantiles do not add; overlapping rows are marked.

| Platform | Stage | ×1 | ×4 | ×8 |
|---|---|---:|---:|---:|
| macos | public outside host (derived) | 108.15 / 125.25 | 157.71 / 284.14 | 332.36 / 528.96 |
| macos | host metadata/snapshot validation | 122.36 / 151.08 | 202.57 / 474.78 | 516.73 / 841.46 |
| macos | combined preparation (overlaps preceding rows) | 225.28 / 279.83 | 375.40 / 685.90 | 840.08 / 1263.14 |
| macos | host transfer directory | 0.10 / 0.12 | 0.13 / 0.36 | 0.12 / 0.34 |
| macos | pre-spawn host setup | 0.07 / 0.12 | 0.07 / 1.61 | 0.07 / 3.13 |
| macos | process launch call (overlaps guest/envelope) | 2.03 / 4.64 | 5.56 / 20.76 | 6.49 / 115.88 |
| macos | spawn-return → guest-ready (overlaps guest) | 414.77 / 515.57 | 814.32 / 1290.72 | 1130.07 / 1740.44 |
| macos | guest snapshot restore copy | 225.23 / 288.98 | 427.52 / 807.99 | 494.88 / 981.04 |
| macos | guest pre-init setup | 0.04 / 0.06 | 0.04 / 0.13 | 0.04 / 0.14 |
| macos | mysql_server_init | 108.02 / 130.88 | 221.36 / 356.56 | 422.25 / 810.69 |
| macos | post-srv plugins (nested inside init) | 11.01 / 22.18 | 14.15 / 40.81 | 18.15 / 74.36 |
| macos | bootstrap connection / initial SQL | 0.23 / 0.37 | 0.27 / 0.84 | 0.40 / 1.36 |
| macos | guest ready preparation | 0.01 / 0.01 | 0.01 / 0.02 | 0.01 / 0.02 |
| macos | launch-envelope residual, spawn-begin (derived) | 84.49 / 116.89 | 153.15 / 301.68 | 159.07 / 444.25 |
| macos | host TCP listener ready | 0.14 / 0.31 | 0.08 / 0.31 | 0.08 / 0.49 |
| macos | host trace/readiness finalization | 0.34 / 0.64 | 0.35 / 0.76 | 0.33 / 1.64 |
| macos | client connection | 6.63 / 9.96 | 6.47 / 15.09 | 7.52 / 23.76 |
| macos | first SQL | 1.06 / 2.05 | 1.06 / 2.53 | 1.45 / 3.30 |
| ubuntu | public outside host (derived) | 115.16 / 116.54 | 127.82 / 142.62 | 248.02 / 318.19 |
| ubuntu | host metadata/snapshot validation | 154.45 / 156.43 | 175.13 / 190.88 | 362.92 / 464.80 |
| ubuntu | combined preparation (overlaps preceding rows) | 269.48 / 272.97 | 304.68 / 328.28 | 615.45 / 745.01 |
| ubuntu | host transfer directory | 0.06 / 0.06 | 0.08 / 0.12 | 0.08 / 0.26 |
| ubuntu | pre-spawn host setup | 0.04 / 0.05 | 0.06 / 0.19 | 0.05 / 1.61 |
| ubuntu | process launch call (overlaps guest/envelope) | 0.27 / 0.34 | 1.41 / 3.13 | 1.95 / 12.20 |
| ubuntu | spawn-return → guest-ready (overlaps guest) | 360.68 / 383.35 | 519.37 / 624.11 | 871.77 / 995.15 |
| ubuntu | guest snapshot restore copy | 226.21 / 235.83 | 291.18 / 427.56 | 501.53 / 694.69 |
| ubuntu | guest pre-init setup | 0.02 / 0.03 | 0.03 / 0.04 | 0.03 / 0.05 |
| ubuntu | mysql_server_init | 92.83 / 106.41 | 147.40 / 192.89 | 231.25 / 340.37 |
| ubuntu | post-srv plugins (nested inside init) | 10.94 / 14.23 | 24.60 / 41.62 | 39.19 / 79.59 |
| ubuntu | bootstrap connection / initial SQL | 0.12 / 0.15 | 0.13 / 0.27 | 0.14 / 0.23 |
| ubuntu | guest ready preparation | 0.01 / 0.02 | 0.01 / 0.01 | 0.01 / 0.02 |
| ubuntu | launch-envelope residual, spawn-begin (derived) | 41.42 / 43.44 | 68.20 / 83.69 | 126.49 / 190.44 |
| ubuntu | host TCP listener ready | 0.06 / 0.08 | 0.07 / 0.11 | 0.07 / 0.11 |
| ubuntu | host trace/readiness finalization | 0.29 / 0.47 | 0.44 / 0.98 | 0.45 / 1.39 |
| ubuntu | client connection | 6.41 / 6.91 | 11.17 / 20.50 | 19.86 / 45.92 |
| ubuntu | first SQL | 0.91 / 1.11 | 1.27 / 3.30 | 1.59 / 5.63 |

Spawn-return residual (the historical FAST definition) at ×1/4/8 p50:
macOS 81.7/140.5/134.2 ms, Ubuntu 41.2/66.7/123.6 ms. Mac ×8 has three negative
residuals (−163/−286/−284 ms) alongside long `cmd.Start` calls (269/372/367 ms).
Inference: guest execution can overlap the launch call before its return, so
spawn-return residual is not a nonnegative independent stage. The spawn-begin
envelope residual above accounts for that overlap (those three become
106/86/84 ms). Keep raw negatives; do not clamp or call them negative runtime work.

## End-to-end comparison and concurrency

Fork per-DB p50/p95 ms; the pre-RSA column is the matched control from the same
run, not a different machine/day. Batch quantiles remain in the RSA report.

| Platform | × | Control | Prepared keys |
|---|---:|---:|---:|
| macos | 1 | 1321.37 / 2398.62 | 648.57 / 789.56 |
| macos | 4 | 1978.57 / 3310.60 | 1214.44 / 1883.58 |
| macos | 8 | 3776.44 / 5767.05 | 1938.94 / 3133.94 |
| ubuntu | 1 | 1236.24 / 1981.52 | 640.49 / 661.27 |
| ubuntu | 4 | 2000.34 / 2864.59 | 837.17 / 935.88 |
| ubuntu | 8 | 3494.85 / 4723.79 | 1512.17 / 1639.11 |

1. **Largest ×1:** among individually observed stages, restore is ~225/226 ms.
   Grouping preparation gives ~225 ms macOS / 269 ms Ubuntu; that grouping is
   effectively tied with restore on macOS and exceeds it on Ubuntu.
2. **Second largest individual stage:** host metadata/snapshot validation
   ~122/154 ms. Public-outside-host ~108/115 ms and embedded init ~108/93 ms
   follow. Do not rank a containing runtime envelope against its own children.
3. **Largest ×1→×8 grouped growth:** combined preparation rises by ~615 ms
   macOS and ~346 ms Ubuntu. Restore rises ~270/275 ms; embedded init ~314/138 ms.
   Individually, macOS host validation grows ~394 ms; Ubuntu restore ~275 ms.
4. **MariaDB remaining:** ×1 ~108/93 ms, ×8 ~422/231 ms. Post-srv plugins are
   only ~11 ms ×1 (×8 ~18/39 ms). The former auth bucket is no longer dominant.
5. **Storage:** restore copy is material and already consumes substantial CPU.
   Host transfer directory preparation is ~0.1 ms; do not confuse it with copy.
6. **Validation/preparation:** two clock scopes both contribute; snapshot
   inventory versus artifact hashing is not separately timed in host validation.
7. **Runtime/host:** launch itself ~2 ms ×1, listener/finalization below 1 ms,
   client connection ~6–7 ms; envelope residual is tens to hundreds of ms with
   multiple possible owners, not a proven pure runtime initialization cost.
8. **Unexplained:** pre-main initialization and post-ready delivery/diagnostic
   serialization share the residual; public preparation versus trace tail also
   remains unsplit. No independent timing proves how much could be eliminated.

## CPU evidence

Guest process/current-thread CPU milliseconds p50/p95; restore scope is
guest-main→restore-complete (including the negligible pre-restore gap). Process
CPU includes other threads; wrappers/instrumentation can contribute. These are
not host-validation CPU or overall CPU-budget estimates.

| Platform | × | Stage | Process CPU | Current-thread CPU |
|---|---:|---|---:|---:|
| macos | 1 | restore | 223.46 / 272.74 | 167.96 / 215.27 |
| macos | 1 | embedded | 116.68 / 142.93 | 73.28 / 94.62 |
| macos | 1 | post-srv plugins | 19.11 / 34.78 | 5.06 / 11.03 |
| macos | 4 | restore | 284.75 / 353.31 | 222.57 / 272.48 |
| macos | 4 | embedded | 150.36 / 199.13 | 90.04 / 117.10 |
| macos | 4 | post-srv plugins | 16.88 / 32.73 | 5.94 / 11.55 |
| macos | 8 | restore | 207.13 / 360.20 | 151.24 / 264.69 |
| macos | 8 | embedded | 143.05 / 203.55 | 77.10 / 123.67 |
| macos | 8 | post-srv plugins | 17.25 / 39.01 | 5.75 / 11.84 |
| ubuntu | 1 | restore | 199.21 / 212.99 | 107.60 / 117.70 |
| ubuntu | 1 | embedded | 101.74 / 117.42 | 39.47 / 41.42 |
| ubuntu | 1 | post-srv plugins | 20.00 / 26.09 | 4.06 / 4.92 |
| ubuntu | 4 | restore | 195.63 / 215.89 | 106.61 / 120.35 |
| ubuntu | 4 | embedded | 116.62 / 152.01 | 52.05 / 55.05 |
| ubuntu | 4 | post-srv plugins | 24.66 / 35.96 | 5.04 / 5.36 |
| ubuntu | 8 | restore | 197.28 / 221.00 | 109.96 / 121.49 |
| ubuntu | 8 | embedded | 118.10 / 152.36 | 53.24 / 56.53 |
| ubuntu | 8 | post-srv plugins | 26.49 / 37.80 | 5.11 / 5.48 |

Measured fact: Ubuntu restore process CPU stays ~195–199 ms while wall grows
226→502 ms; embedded process CPU ~102→118 ms while wall grows 93→231 ms.
Mac restore CPU is ~223/285/207 ms versus wall225/428/495; embedded CPU
~117/150/143 versus wall108/221/422. Inference: wall growth is not proportional
to increased executed CPU; scheduling/contention is plausible, not uniquely
identified. No page-fault/lock/bandwidth attribution or host validation CPU is
available. Whole-run sampled CPU remains in the prior report; coarse Ubuntu
`ps` granularity must not be interpreted as zero work.

## Validation reuse context and bounded scenarios

No new validation optimization or prepared-key reuse run is implemented here.
The [existing probe](mariadb-init-investigation.md#within-call-validation-reuse)
on run36256194463 skips two repeated AOT digests **within one startup**, keeping
initial bundle/sidecar/snapshot checks. Its historical combined-preparation
p50 reduction was ~132 ms macOS / 98 ms Ubuntu at ×1; it was not a paired
prepared-key comparison and did not establish causal end-to-end savings.

The following are **derived optimistic thought experiments**, not measured
end-to-end speedups or guaranteed achievable bounds. For each current ×1 raw
latency subtract the historical constant 132/98 ms and, where shown, that same
record's measured restore duration; then recompute p50/p95. The last row assumes
all measured preparation and restore vanish with zero replacement cost.
Percentile columns are never simply summed/subtracted from each other.

| Platform | Scenario | p50 / p95 ms |
|---|---|---:|
| macos | baseline | 648.57 / 789.56 |
| macos | minus historical repeated validation | 516.57 / 657.56 |
| macos | minus historical validation and measured restore | 292.70 / 408.60 |
| macos | minus all measured preparation and restore | 200.83 / 257.09 |
| ubuntu | baseline | 640.49 / 661.27 |
| ubuntu | minus historical repeated validation | 542.49 / 563.27 |
| ubuntu | minus historical validation and measured restore | 315.33 / 327.93 |
| ubuntu | minus all measured preparation and restore | 143.33 / 156.31 |

9. **FAST-target assessment:** the measured baseline misses p50<250/p95<500 ms.
   Removing only the historical duplicate-validation candidate is insufficient.
   Even assuming that saving plus zero-cost restore leaves p50~293/315 ms,
   although its hypothetical p95 falls below 500. Removing *all* preparation
   and restore could mathematically reach the target, but required integrity
   work cannot simply be erased. Thus a cold-start path is not ruled out; it
   needs evidence for reducing at least two substantial buckets. Continuation
   is not yet compelled by the remaining MariaDB-init time alone. A storage
   probe may matter, but no architecture is selected from this subtraction.

## Recommended next 0.2 FAST probe

Exactly one next probe: **rerun the existing within-call validated-AOT-identity
reuse experiment under prepared keys, interleaved with the unchanged baseline,
with memory diagnostics off**. Keep initial/native/sidecar/snapshot integrity
checks and verified immutable artifacts; do not introduce cross-call caching.
This tests how much of the now-large combined preparation bucket is actually
redundant and whether its measured reduction reaches end-to-end readiness when
RSA variance is gone. It is smaller than a new storage/runtime/continuation
boundary and resolves the historical constant assumption in the scenarios.
No implementation of this next probe is included in this task.
