# Production memory scaling and 16-session readiness probe

Status: completed both-platform results from [run 36514853666](https://github.com/masahitojp/mariamem/actions/runs/36514853666). No product,
MariaDB configuration, cache, guest, runtime, validation or restore change.
This separates independent database isolation from one database's client capacity.

## Measurement contract

Run `python3 scripts/verify.py bench envelope --native-dir /path/to/native
--runs 20 --warmup 1 --json benchmarks/results/init-memory-envelope.json`.
The `guest-build-boundary.yml` input `memory_envelope=true` runs this on both
macOS 15 arm64 and Ubuntu 24.04 x86_64, with exact verified guest/AOT reuse.
Source commit, runtime manifest/hashes, Go build information and harness/helper
hashes are retained. Nothing is released. Results remain ignored artifacts.

### A. Independent databases

The canonical Go API runner creates the existing 1,000-row / 32-character fixture,
snapshots it, then concurrently Forks ×1/4/8/16 using unchanged startup and first
fixture COUNT. Preparation of the fixture is outside the measured batch.
Before Snapshot, close the fixture SQL pool and await `WaitDisconnected` so
server-side session cleanup is acknowledged. This is outside G(0)/Fork timing.
Each trial is a separate process; the supervisor writes retained results after
every trial. Counts run round-robin (not paired performance conditions), with
20 measured trials and one warmup per count if they complete. A failed count is
not retried/tuned; other counts can continue. ×16 failure is evidence, not zero
latency or success. Missing results, exit signals and cgroup memory events where
available are recorded. A signal/exit 137 alone is not proof of OOM. A runner-wide
OOM can still prevent final artifact upload; retained earlier trials are best-effort.

OS counters are the already-established Aria probe mechanism, reused without
any cache-size/engine experiment: macOS `proc_pid_rusage` physical-footprint
accounting and CPU time with Mach timebase; Linux `smaps_rollup` PSS/private,
`/proc/PID/stat` CPU ticks. Counters include Go host and runtime descendants;
raw RSS is secondary. Helpers/supervisor are excluded from that process tree.
The ready counter scan is not atomic across processes.

G(0) is the prepared-snapshot holder Go process with no live database/runtime.
G(n) is host plus all n runtimes after every first SQL succeeds. CPU starts at
G(0), ends at all-ready counter collection, includes timing/sampling and version
queries, and excludes correctness/mapping diagnostics and Close. Group-ready
latency ends at the last first SQL; the small subsequent counter-collection tail
is included in CPU, consistently at every count. Retain host/runtime/combined
CPU, G(0)/G(n), incremental/average private/PSS/footprint, sampled group peak,
collection durations and gaps, and after-Close counters. A missing/vanished
runtime counter is a gap/failure, never zero memory.

Marginal 1→4 / 4→8 / 8→16 uses differences of incremental group cost, matched
by round index, divided by added DB count. These are independent runs, not
simultaneous marginal allocations; baseline host retention can differ. Peak is
sampled (50 ms requested interval plus scan overhead), not guaranteed exact peak.
After Close require no runtime descendants; host GC/allocator retention need not
return to G(0). Fresh processes limit cross-trial retention; this is not a
long-lived-host leak soak test.

### B. One database, 16 sessions

Run this separate probe before isolation scaling so its result survives ×16
pressure where possible. Ten independent trials start one ordinary Database,
open and keep 16 driver connections, record each connection+Ping latency,
measure zero/one/16-session memory and same-interval one→16 host/runtime CPU.
Connections are established sequentially and held simultaneously; this is not
a connection-storm benchmark.

All 16 issue SQL concurrently and verify unique session variables and identically
named temporary tables with unique contents. Session 17 must return MySQL 1040;
all original sessions must remain usable afterward. Close all physical driver
connections, await `WaitDisconnected` (guest cleanup acknowledgement), observe
memory, reconnect/query, then Close the database and require no descendants.
Memory before/after SQL-created temporary state is not attributed to connection
creation. The after-session-close observation includes retained engine state,
not a promise that allocations immediately shrink. This is readiness for later
pool dogfood, not an ORM compatibility test or an unlimited-session claim.

### C. Observable memory ownership

One separate ×1 diagnostic Fork collects the ordinary host/guest startup trace,
sampled process-tree memory progression and **one ready-state** mapping/thread
observation using the existing mapping tool (`vmmap -summary` or Linux smaps).
This avoids expensive mapping capture on every trial/DB. Go host and guest/runtime
process memory are distinguishable. Linux anonymous versus AOT/file mappings and
macOS mapping categories can support bounded ownership observations.

There is no aligned guest/host clock or OS counter hook at exactly restore-end
or MariaDB-init-end. Samples cannot be assigned to those boundaries by subtracting
independent clock offsets. Linear-memory capacity, allocator/mapping categories,
guest memory filesystem and MariaDB allocations can overlap; do not sum them
as disjoint physical owners. Report the remainder as unattributed. If the current
architecture cannot distinguish runtime-owned FS from linear memory, state that
limitation rather than adding protocol/runtime changes.

## Initial run diagnosis

[Run 36501655086](https://github.com/masahitojp/mariamem/actions/runs/36501655086)
passed all ten 16-session trials on each platform. Scaling attempts failed before
Fork timing: the new harness omitted the canonical runner's `WaitDisconnected`
after fixture SQL, so Snapshot correctly rejected active session cleanup as busy.
This was not an OOM or ×16 resource-envelope result. The harness now awaits the
existing acknowledgement with a bounded context before Snapshot; no product
precondition is relaxed. The corrected run below completes the scaling measurements.

## Verification before CI

Focused tests cover counter aggregation/CPU intervals, unavailable counters,
partial ×16 failures, marginal calculation and crash evidence retention.
The native helper is compiled and its local OS counters inspected. Canonical
Go/Python/public-source checks and relevant benchmark race tests are required.
Normal checks passed (316 Python tests, three skipped; Go tests/vet/public source),
with relevant race tests and workflow YAML parsing. The results below are fresh
production-setting observations, not an inference from the earlier Aria control.

## Completed evidence and environment

Exact measured host/harness: `0a0ee378b29e6c6c7049ef298b8b07a978bf2a7a`,
clean checkout. Go 1.26.8, Python 3.14.7, Wasmer 7.4.2, production guest settings.
macOS 15.7.9 arm64 has three reported CPUs; Ubuntu 24.04 x86_64 has four
(kernel 6.17.0-1022-azure, glibc 2.39, SSE2+SSSE3 AOT). Do not compare these
machines as equivalent hardware. Common guest-producing source remains `d44157a`,
with verified unchanged-input measurement reuse, not relabelled release provenance.

Downloaded common guest files were hashed against `reuse.json`; both AOT
manifest hashes and common WASM/handoff hashes were checked against provenance.
Summary and marginal-memory distributions were recomputed from raw trial records.
Every batch ready/after-close inventory and every session correctness result was
checked. Raw results remain in the workflow's `initialization-<platform>-0a0ee37...`
artifacts; AOT binary bytes are not in these result bundles and cannot be rehashed
locally. CI validates them before use.

- WASM: `41e3acfb51fe52ad13d9691de0bd3f05619266571e84dd1a0ddf263e082add7f`
- macOS AOT: `a74927f01e387f8d60fecb5e61a182e344b6a0d2b524d735817e5d632bcc6d4d`
- Ubuntu AOT: `e729fc07d7cb03de6b4bbf5334f0e1da460a8abfff56b0d3661b2688969e73fb`

Both platforms completed every warmup and all 20 measured trials at each count,
one attribution trial and ten session trials. No allocation/startup/cleanup
failure or observed OOM termination occurred. Cgroup memory-event counters were
unavailable, so no independent kernel OOM-counter claim is made.

## A. Independent database scaling

Primary memory is footprint accounting on macOS and PSS on Ubuntu.
All paired entries are p50 / p95; values are distributions from individual
batches, not sums of separate percentiles.

| Platform | DBs | Group-ready ms | Combined CPU-sec/DB | Incremental MiB/DB |
| --- | ---: | ---: | ---: | ---: |
| macOS | 1 | 444 / 516 | 0.458 / 0.514 | 239.9 / 248.0 |
| macOS | 4 | 752 / 1,061 | 0.480 / 0.611 | 244.7 / 250.5 |
| macOS | 8 | 1,420 / 1,765 | 0.462 / 0.502 | 245.1 / 247.1 |
| macOS | 16 | 3,352 / 3,877 | 0.445 / 0.488 | 259.2 / 261.7 |
| Ubuntu | 1 | 543 / 551 | 0.530 / 0.550 | 404.9 / 414.3 |
| Ubuntu | 4 | 831 / 850 | 0.565 / 0.575 | 343.7 / 347.2 |
| Ubuntu | 8 | 1,415 / 1,472 | 0.570 / 0.582 | 332.1 / 335.6 |
| Ubuntu | 16 | 2,633 / 2,695 | 0.561 / 0.571 | 326.8 / 328.1 |

| Platform / DBs | G(0) MiB p50 | G(n) MiB p50 | Incremental group MiB p50/p95 | Sampled group peak MiB p50/p95 | After Close MiB p50 |
| --- | ---: | ---: | ---: | ---: | ---: |
| macOS / 1 | 7.8 | 247.6 | 239.9 / 248.0 | 247.6 / 255.8 | 8.6 |
| macOS / 4 | 7.8 | 986.5 | 978.8 / 1,001.9 | 986.5 / 1,009.6 | 9.4 |
| macOS / 8 | 7.7 | 1,968.8 | 1,961.2 / 1,976.8 | 1,968.9 / 1,984.3 | 9.8 |
| macOS / 16 | 7.7 | 4,155.3 | 4,147.6 / 4,187.2 | 4,155.3 / 4,195.1 | 10.3 |
| Ubuntu / 1 | 14.6 | 419.6 | 404.9 / 414.3 | 419.6 / 427.8 | 16.0 |
| Ubuntu / 4 | 13.6 | 1,388.3 | 1,374.8 / 1,388.9 | 1,388.3 / 1,402.4 | 16.0 |
| Ubuntu / 8 | 14.6 | 2,671.2 | 2,656.7 / 2,684.6 | 2,671.2 / 2,700.1 | 16.3 |
| Ubuntu / 16 | 13.7 | 5,242.4 | 5,228.1 / 5,249.2 | 5,242.7 / 5,262.9 | 16.6 |

Incremental/marginal values subtract each trial's own G(0), not the median G(0).

| Added DB interval | macOS marginal MiB/DB p50/p95 | Ubuntu marginal MiB/DB p50/p95 |
| --- | ---: | ---: |
| 1→4 | 245.7 / 253.2 | 323.4 / 330.4 |
| 4→8 | 244.4 / 251.2 | 319.5 / 330.9 |
| 8→16 | 274.1 / 279.1 | 320.6 / 326.3 |

**Measured fact:** CPU per DB is nearly constant, rather than amplifying strongly.
Same-round CPU amplification CPU(n)/(n×CPU(1)) is macOS ×8 1.000/1.163 and
×16 0.974/1.108; Ubuntu ×8 1.078/1.106 and ×16 1.061/1.093 (p50/p95).
At ×16, host CPU is 2.34/2.46 sec macOS and 3.02/3.03 sec Ubuntu; runtime CPU
is 4.80/5.46 and 5.96/6.10. Their separate percentiles must not be summed.
Host work remains substantial; fewer milliseconds of wall time do not mean
less CPU. The bounded runner CPU capacity and near-linear batch CPU are
consistent with contention under parallel isolation, but do not establish its
specific scheduler/storage cause.

**Measured fact:** Ubuntu's marginal primary cost remains about 320 MiB/DB,
while average PSS/DB falls as file-backed pages become shareable/accounted across
more processes. Ready private group memory is 419/1,310/2,592/5,163 MiB p50;
raw group RSS is 424/1,633/3,226/6,425 MiB. The falling average is not evidence
that the per-instance anonymous state becomes cheap.

macOS raw group RSS is 351/1,387/2,757/2,907 MiB p50, but primary footprint
reaches 4,155 MiB at ×16. **Inference:** that divergence is consistent with memory
pressure/compression/accounting effects; no ×16 compressor/swap capture proves
which. It must not be described as successful sharing or a memory reduction.
Footprint is an accounting charge, PSS a sharing-weighted resident measure;
neither is globally unique physical memory, and the two cannot be compared as
identical quantities.

All after-Close inventories contain only the Go runner. Residual host footprint
above G(0) is macOS ×1/4/8/16 0.86/1.69/2.13/2.51 MiB p50 (×16 p95 2.74);
Ubuntu 0.52/0.94/1.15/1.35 MiB (×16 p95 3.49). Close plus final counter scan
at ×16 is 245/323 ms macOS and 615/687 ms Ubuntu. This harness closes DBs
sequentially; that is not parallel Close performance. Small host retention is not
proof of a leak, and fresh trial processes are not a long-lived-host soak test.

Observer limitations matter: macOS has 71 transient startup counter gaps across
80 measured batches; all required baseline/ready/after-close captures succeeded.
Ubuntu has none. Requested sampling interval is 50 ms, but worst collection is
0.931 s macOS / 0.454 s Ubuntu; sampled peaks can miss short peaks. Ready scan
p50 at ×16 is 17 ms / 67 ms. CPU includes the host's collection orchestration,
not the external helper's own CPU; diagnostic cost and pressure can affect measured
latency. These are resource-envelope measurements, not an uninstrumented latency
acceptance. Ubuntu ×1 remains above the 500 ms FAST target in this run; macOS
passing it here does not resolve cross-run variation.

## B. One DB with 16 simultaneous sessions

Both platforms passed ten full trials: 16 live connections, concurrent ordinary
SQL, independent variables and same-named temporary tables, recoverable MySQL
1040 on connection 17, original sessions still usable, acknowledged disconnect,
reconnect with no old variable/temp-table state, and database cleanup.

| Metric (p50 / p95) | macOS | Ubuntu |
| --- | ---: | ---: |
| Connection + Ping, 160 samples across ten DBs | 5.30 / 8.31 ms | 6.07 / 7.84 ms |
| Primary memory increase, 1→16 sessions | 41.12 / 41.86 MiB | 53.68 / 53.70 MiB |
| Combined CPU, 1→16 sessions | 0.094 / 0.109 sec | 0.105 / 0.130 sec |
| Host CPU, same interval | 0.017 / 0.020 sec | 0.010 / 0.020 sec |
| Runtime CPU, same interval | 0.075 / 0.093 sec | 0.090 / 0.120 sec |

Session memory deltas are computed per trial; do not subtract table medians.
The average marginal cost for 15 added connections is about 2.74 / 3.58 MiB per
connection (derived, not an individually measured per-session allocation).
These are sequential establishment timings, not simultaneous connection bursts.
After connection close and SQL checks, the DB's primary memory remains around
348/482 MiB macOS/Ubuntu; after DB Close only the runner remains at 6.9/15.6 MiB.
Session capacity is returned, but allocator/engine memory need not immediately
shrink. The session workload uses an ordinary Start DB, unlike the Fork fixture;
its absolute base memory must not be directly compared to prepared Fork G(1).

## C. Observable memory ownership

One diagnostic Fork on Ubuntu gives runtime PSS **397.6 MiB**: anonymous PSS
319.5 MiB, file PSS 78.2 MiB, no shmem or swap at capture. The AOT file mapping
contributes 64.2 MiB PSS; runtime executable mappings about 14.4 MiB. Go host
ready PSS is about 16.0 MiB, versus 15.5 MiB baseline. Thus most incremental
cost is in the runtime/guest process, not host heap.

Large mappings include an anonymous RW region with 96.0 MiB resident, another
with 81.6 MiB resident inside 642 MiB virtual space, and an anonymous executable
region with 21.1 MiB resident. **Unknown:** anonymous regions cannot be assigned
unambiguously to restored filesystem buffers, WASM linear memory, MariaDB heap,
thread stacks or generated runtime code from these records alone. The 96 MiB
mapping's similarity to redo size is a hypothesis, not ownership evidence.
The 256 MiB initial WASM capacity is a source/configuration fact, not 256 MiB of
proven committed/RSS memory and not additive to these mapping counts.

The separate macOS ready mapping records runtime physical footprint 235.0 MiB,
mapped-file resident 62.2 MiB, VM_ALLOCATE resident 96.6 MiB, MALLOC_LARGE
54.2 MiB, reusable large malloc 58.3 MiB and medium malloc 53.7 MiB resident.
These are allocator/mapping categories, not semantic component owners; do not
add the table to physical footprint or treat reusable/virtual bytes as uniquely
physical. Stack resident is about 0.6 MiB. Host footprint is about 8.4 MiB versus
7.7 MiB baseline. Runtime/guest dominates on this platform as well.

OS ready-thread inventory is 17 macOS / 21 Ubuntu runtime threads in this one
capture; thread roles are not identified. No initialized-state/quiescence claim
follows. Sampling shows runtime memory growing during startup (Ubuntu about
76→178→218→254→298→387 MiB group, then 414 MiB at ready; macOS about
62→104→151→222→244 MiB). The distinct guest clock cannot align those samples
exactly with restore-end or MariaDB-init-end. No precise per-stage ownership or
CPU allocation is invented. We can separate host from runtime, and some file
from anonymous mappings; the remaining runtime/FS/linear/MariaDB split is unknown.

### Memory scaling verdict

Practical ×16 **PASS in this hosted environment**, with no configuration tuning
and clean process teardown. It costs roughly **4.05 GiB incremental footprint on
macOS / 5.11 GiB incremental PSS on Ubuntu**, with group-ready p95 3.88/2.69 sec.
This establishes a tested envelope, not support on every machine with less memory.
Incremental/marginal memory remains hundreds of MiB/DB and mostly runtime/guest;
no strong CPU amplification is observed. Cleanup works, with small runner retention.
These results do not meet the provisional Ubuntu <256 MiB/DB memory budget and
do not establish an uninstrumented Ubuntu ≤500 ms latency KPI. No budgets or
architecture are changed based on this probe.

### 16-session readiness

**PASS on both platforms** for the current 16-slot server/resource boundary.
It is ready to be exercised by later ORM pool dogfood: bounded capacity failure,
session isolation, disconnect/reset/reconnect and cleanup behave correctly.
This is not SQLAlchemy/GORM compatibility, full-authentication or unlimited-pool
acceptance. A 16-session pool is substantially cheaper than 16 isolated databases,
but those workloads provide different isolation semantics and are not substitutes.

### Architecture decision inputs

- Marginal independent-DB memory is about 245–274 MiB footprint on macOS and
  319–323 MiB PSS on Ubuntu; ×16 completes but is resource-heavy.
- Ubuntu has about 319 MiB anonymous runtime PSS at ×1, with file-backed sharing
  explaining much of the falling average PSS/DB. Sharing only AOT file pages does
  not remove the large private/anonymous floor.
- Host memory is small; host verification/startup CPU is still material. Removing
  a process layer alone is not established as a memory or latency solution.
- Session incremental memory is far smaller and current 16-slot behavior is clean;
  this does not eliminate per-DB isolation costs or change product semantics.
- Exact FS/linear-memory/engine ownership, ×16 memory-pressure effects and
  long-lived-host retention remain unknown. Any larger memory architecture review
  must preserve independent state, session cleanup and interrupted-query semantics.

No architecture change is recommended or implemented in this analysis.
