# mariamem project status

This document summarizes the current product, verified candidate, release work
and roadmap. Detailed experiments and historical measurements belong in their
linked reports, not in a chronological changelog here.

## 1. Current product / architecture

mariamem provides disposable, isolated **real MariaDB** instances for Go and
Python integration tests. It preserves MariaDB SQL/InnoDB semantics rather than
reimplementing them. Its value is ordinary MySQL clients, inexpensive lifecycle
and per-test isolation; it does not emulate production-scale database performance.
The guest builds on `shyim/lite4mariadb`. The project remains GPL-2.0-only with
pinned corresponding-source inputs and preserved third-party notices.

On `v0.4/generated-go-integration`, normal Go
`mariamem.Start(ctx, mariamem.Options{})` directly links generated-Go MariaDB
into the consumer process. Normal startup does not provision a per-DB executable,
spawn a guest subprocess, download/discover Wasmer, or require NativeDir/cache.
Generated Go is a normal Go dependency/build input. Explicit NativeDir/runtime
bundle overrides retain isolated legacy Wasmer compatibility.

```text
Build time:
MariaDB / WASIX → pinned WASM intermediate → wasm2go → generated Go source

Go runtime:
consumer → Go API / mariamem host → MySQL wire → linked generated-Go MariaDB
Python runtime:
Python API → packaged Go host process → MySQL wire → linked generated-Go MariaDB
                                                         ↓
                                             WASIX compatibility layer
                                                         ↓
                                           isolated / prepared database files
```

**WASM is a build intermediate.** Each DB has fresh execution/thread/TLS/FD state
and private writable filesystem state. Snapshot/Fork reuses prepared files and
restarts execution; it does not clone ready heaps, live workers or waiter state.
Ready-state reentry was rejected for v0.4. No OS fork of the Go runtime is used.
Execution architecture is an implementation detail, not a public process-isolation
contract. See [architecture](v04-generated-go-architecture.md).

Public Go/Python workflows and Snapshot/Fork semantics are preserved: successful
Snapshot consumes its source; precondition rejection keeps the source usable;
Fork children remain independent. Normal Close is idempotent. Multiple SQL
sessions and ordinary pools work; current capacity is 16, not a permanent API
promise or evidence of high-connection-count scalability. Ordinary SQL errors
and idle disconnects do not invalidate a DB. Interrupted active SQL can invalidate
the entire DB; this does not guarantee forced guest reclamation.

Supported scope remains macOS15+ arm64 and Ubuntu24.04 x86_64. Canonical acceptance
uses Go1.26.8 and Python3.14. Module/package minimum versions do not establish a
broad tested-version matrix. Other platforms are not release support.

## 2. v0.4.0 integrated candidate / verified results

The integrated direct-link candidate passes local normal Go/Python, core SQL,
MySQL protocol, authentication, CLIENT_FOUND_ROWS, sessions/MaxSessions, reconnect,
repeated/concurrent lifecycle and Snapshot/Fork fixture/write/schema isolation.
External dogfood passes **SQLAlchemy44/44** and **GORM32/32**, including repeated
AutoMigrate/schema discovery. Focused handwritten FD/MemFS/thread/TLS/futex
runtime race tests pass.

The closed-handle pipe-FD fix is integrated: Close releases the drained response
reader even when closed DB/Snapshot-source handles remain retained. Directory-FD
identity/rename-name-reuse and MemFS grow/truncate regressions remain covered.
Known-size cold filesystem copying pre-sizes its private destination; Snapshot
TotalAlloc fell **69.6%**, from ~914.83 to ~278.17 MiB. This is allocation-churn
reduction, not CoW or a Snapshot format/API change.

Canonical integrated measurements: Apple M1 / 16 GiB, macOS27.0.1 arm64,
Go1.26.8; 30 startup/Snapshot/Fork trials, 10 scaling trials per size, three ORM
suites per mode. No slow trials are removed.

| Boundary | p50 | p95 |
| --- | ---: | ---: |
| public Start → first SQL | 38.4 ms | 593.7 ms |
| Start → 1,000-row fixture | 52.7 ms | 55.4 ms |
| prepared Fork → COUNT | 104.6 ms | 251.6 ms |
| Snapshot | 399.9 ms | 570.8 ms |
| ×16 group-ready | 0.574 s | 0.775 s |
| ×16 CPU | 2.814 CPU-sec | 2.954 CPU-sec |
| SQLAlchemy100 Start | 34.025 s | 34.038 s |
| SQLAlchemy100 Fork | 20.430 s | 20.705 s |

Start/Fork/CPU and ORM Fork improve materially over the fixed Wasmer reference.
Snapshot median is approximately unchanged versus Wasmer; its p95 remains slower.
Start's p95 includes two approximately one-second runs. Fork p95 is slower than
in the previous direct-link campaign; this is recorded, not optimized away.

Prepared-scaling physical footprint is a separate boundary: ×16 incremental
p50/p95 **197.4/265.6 MiB per DB**, ready total **3664.7/4755.1 MiB**, immediate
post-Close **3665.4/4755.1 MiB**. These are not exclusive active-DB allocations.

See [integrated candidate and both baseline comparisons](../benchmarks/v04-integrated-candidate.md),
[original Wasmer baseline](../benchmarks/v04-baseline.md) and
[pre-integration direct-link baseline](../benchmarks/v04-direct-link-baseline.md).
The [release audit](release-readiness-v0.4.md) adds representative graceful-error
and installed-wheel cleanup acceptance: malformed inputs/SQL/Snapshots return
errors, reconnect and subsequent Start work, retained handles leave FD6→6 and
observed goroutines2→2. This is local evidence, not exhaustive failure containment
or final supported-platform release approval.

## 3. Known limitations

- **Full generated guest is not Go `-race` clean.** The investigation verdict is
  **GENERAL SHARED-MEMORY MODEL WORK REQUIRED**. Conflicts are not claimed
  harmless; signature counts are not independent bug counts. No race suppression
  or generated function/address patches are used. Full-guest `-race` is not a v0.4 release gate;
  focused handwritten/runtime race checks remain mandatory. Preserve the
  [race census and reduced reproducers](../benchmarks/direct-link-race-scope.md).
- **Forced query-timeout / hard failure containment is not guaranteed.** Normal
  cooperative Close passes; the retained forced-timeout diagnostic fails its
  cleanup deadline. Non-cooperative in-process execution cannot currently be
  forcibly reclaimed. Ordinary-error acceptance does not resolve this limitation.
- **Post-Close physical footprint remains a resource concern.** The
  [lifetime investigation](../benchmarks/v04-snapshot-memory-lifetime.md) concluded
  **OS PHYSICAL ACCOUNTING DOMINATES**. Snapshot owns ~138 MiB of cold files,
  not the exited guest/MemFS; large temporary Go allocations become unreachable
  after diagnostic GC. macOS anonymous/dirty/compressed accounting is distinct
  from live Go heap. Do not call it harmless, a demonstrated live-object leak,
  or immediately reclaimable. No production GC/FreeOSMemory policy was added.
- **Go1.27.0/1.27.1 arm64 are unsupported** because of upstream compiler issue
  #81036 (`LDPSW: constant is not in pool`). An upstream-fixed toolchain was
  verified previously; no mariamem compiler/generated-source workaround is used.
- **Approximately one-second startup tails remain observable.** Earlier tracing
  established legal guest-side condition-variable behavior; the latest campaign
  does not prove the cause of each individual slow run. No timeout shortening or
  forced wakeups suppress the tail.
- **Legacy Wasmer fallback remains.** Its bundle/provisioning/notices infrastructure
  is retained but does not participate in ordinary direct-link startup.

## 4. Remaining v0.4.0 release work

The integrated product is verified locally. The release-system migration now
uses the **generated-go-v1** contract: ordinary Go source/module, two host-only
Python wheels, common corresponding source, provenance and SHA256SUMS.
WASM is a build intermediate. Legacy AOT/native bundles are not acceptance
inputs for the normal path. See [releasing](releasing.md) and the
[migration validation/boundaries](v04-release-ci-migration.md).

The branch remains unpublished; canonical version metadata still identifies
v0.3.0. Required before v0.4.0 publication:

1. Submit the exact pushed candidate to **Release CI verify mode** and obtain
   both macOS arm64 and Ubuntu24.04 x86_64 final-artifact acceptance/aggregate
   READY. Local checks do not replace hosted-runner evidence.
2. Review the candidate's collected corresponding source/notices/provenance,
   preserving exact hashes and MariaDB/lite4mariadb GPL-derived obligations.
   The migrated guard checks LLVM23/legacy-EH→wasm2go generation and offline
   source preparation; historical Wasmer approval does not approve new bytes.
3. Prepare the explicitly human-selected version/current examples/tracked notes
   from `python/mariamem/_version.py`, then reverify that exact final-version SHA.
   Do not tag or publish before the separate release instruction.

The [prior release-readiness audit](release-readiness-v0.4.md) remains a historical
record of the old CI mismatch and local graceful-failure acceptance.

## 5. v0.4.x follow-ups

- Own **prepared-scaling / memory-lifetime work**: non-monotonic physical/RSS
  measurements, post-Close accounting and avoidable allocation/ownership costs.
  Establish attribution and comparable boundaries before choosing an allocator,
  mapping or storage change.
- Own **direct-link cleanup**: unused encoded platform executables, provisioning,
  obsolete bundle/cache machinery and packaging/documentation residue. Preserve
  explicit legacy compatibility until a separate removal decision.
- Investigate bounded Snapshot publish and Fork/Start tail regressions using the
  existing phases and fixed workload. Do not reopen the selected execution
  architecture merely because an upper quantile regresses.

These follow-ups are not v0.4.0 release blockers by themselves and are not an
approval to implement CoW, runtime sharing, mmap or a new Snapshot format.

## 6. v0.5.0 stable-MariaDB plan

Move the guest to a deliberately selected **stable MariaDB source/revision**, with
compatible WASIX/toolchain inputs and traceable reproducible generation. No target
version is chosen by this status document.

Re-run SQL/protocol/auth/session/lifecycle, Snapshot/Fork/isolation, SQLAlchemy
and GORM acceptance on that new guest. **Re-run the full shared-memory race
census and reduced patterns after the MariaDB/WASIX/toolchain update**; compare
ownership and semantic classes before deciding the adapter work. The known race
set is not assumed fixed by an upgrade, and no broad shared-memory redesign is
part of v0.4.0 preparation. Record a new performance/resource baseline rather
than carrying old measurements across changed guest inputs.

## 7. v0.6+ compatibility / dogfood

Broaden actual consumer evidence after the stable-guest migration: dbt's MySQL
connector, metadata/introspection-heavy clients, additional ORM/framework
workloads, pools and non-ORM connection/lifecycle patterns. Retain SQLAlchemy/GORM
as regression anchors. Exercise ordinary migration and test-failure paths, not
special semantics that favor Snapshot/Fork. Do not advertise compatibility before
running the real consumer on the supported platforms.

## 8. Longer-term work

Evidence-driven options include immutable Snapshot backing/CoW views, mmap-backed
linear memory, runtime sharing, stronger cancellation/hard failure containment,
higher/configurable session capacity and broader platforms. None is a selected
production design or release-support promise. Ready-heap/live-worker reentry was
rejected; see [reentry boundary](../benchmarks/reentry-feasibility.md),
[CoW evidence](../benchmarks/cow-feasibility.md) and
[prepared-files evidence](../benchmarks/prepared-clone-feasibility.md) before
revisiting assumptions. Windows/Linux arm64/other distro support is not current
release scope.

The goal toward 1.0 is stable public lifecycle/isolation/compatibility contracts
informed by workload evidence. The 0.x series does not imply 1.0-level API
stability; changes still require an explicit decision. Keep the development loop
**Explore → Challenge → Human decision → Implement → Verify**. Mechanical checks
belong in scripts/CI; architecture and release choices remain human decisions.
Actionable tasks belong in issues, detailed evidence in reports, and this file
should remain a concise account of current truth and roadmap ownership.
