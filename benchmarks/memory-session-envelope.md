# Production memory scaling and 16-session readiness probe

Status: harness prepared; both-platform CI measurements pending. No product,
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
precondition is relaxed. Scaling distributions still require a fresh successful run.

## Verification before CI

Focused tests cover counter aggregation/CPU intervals, unavailable counters,
partial ×16 failures, marginal calculation and crash evidence retention.
The native helper is compiled and its local OS counters inspected. Canonical
Go/Python/public-source checks and relevant benchmark race tests are required.
Real both-platform numbers and session verdict remain pending CI; no result is
inferred from the earlier ×8 Aria control.

### Memory scaling verdict

Pending CI: report practical ×16 completion/failure, group-ready distributions,
CPU, incremental/marginal costs, sampled peaks, cleanup and host retention.
Do not tune the environment or omit a failed count. Distinguish process sharing
accounting from unique physical pages and explain remaining ownership unknowns.

### 16-session readiness

Pending CI: require all 16 independent session checks, recoverable 1040 and cleanup
on both platforms before concluding that this server boundary is ready for later
ORM pool dogfood. No framework support claim follows from this probe alone.

### Architecture decision inputs

Pending CI: independent-DB versus session marginal cost, file-backed/anonymous
sharing observations, host/runtime split, CPU amplification, ×16 resource failures
and cleanup retention. These are inputs, not a recommendation for sharing,
VFS/CoW/continuation or any other architecture change.
