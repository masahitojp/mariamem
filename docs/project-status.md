# mariamem project status

This document owns the current product hypothesis, released architecture and
roadmap. Detailed experiments belong in linked reports; implementation tasks
belong in issues. Version themes below are tentative, not implementation approval.

## 1. Product hypothesis / current architecture

> mariamem makes a real MariaDB cheap to create, safe to throw away,
> and cheap to reclaim.

The product hypothesis is **Disposable isolation**: fresh-instance isolation can
be cheap enough that users choose disposal over cleanup discipline. It moves
reset responsibility from test code into the database lifecycle, reducing
rollback/truncate/schema-reset discipline, test-to-test state leakage and failure
cleanup burden. Clients and owned DB/Snapshot handles still require normal Close.
Simpler tests and reviews, including tests written by coding agents, remain a
hypothesis rather than a demonstrated AI productivity claim.

mariamem runs real MariaDB SQL/InnoDB for Go/Python integration tests. v0.4.0
provides evidence for cheaper creation and ordinary isolated disposal; cheap
reclamation across sustained generations still needs validation. Hard failure
containment is not guaranteed. The guest derives from `shyim/lite4mariadb`; GPL
corresponding source and upstream notices remain required.

Normal Go `mariamem.Start(ctx, mariamem.Options{})` directly links generated-Go
MariaDB into the consumer process. Generated Go is ordinary module source/build
input. Normal startup does not provision a per-DB executable, spawn a guest
subprocess, download/discover Wasmer or require NativeDir/cache. Python's
host-only platform wheel runs the same linked guest inside its packaged Go host.
Explicit legacy Wasmer overrides remain separate.

```text
Build: MariaDB / WASIX → pinned WASM intermediate → wasm2go → generated Go
Go: consumer → Go API / host → MySQL wire → linked generated-Go MariaDB
Python: Python API → packaged Go host → MySQL wire → linked generated-Go MariaDB
                                                     ↓
                                          WASIX compatibility layer
                                                     ↓
                                       isolated / prepared database files
```

**WASM is a build intermediate.** Each DB reconstructs fresh execution/thread/
TLS/FD state and private writable files. Snapshot/Fork reuses prepared files,
not ready heaps, live workers or waiter state; no Go process fork is used.
Successful Snapshot consumes its source, precondition rejection keeps it usable,
and children remain independent. Normal Close is idempotent; ordinary SQL errors
and idle disconnects leave a DB usable. Current session capacity is 16, not a
permanent API or throughput guarantee. See [architecture](v04-generated-go-architecture.md).

Supported scope is macOS15+ arm64 and Ubuntu24.04 x86_64. Canonical acceptance
uses Go1.26.8/Python3.14; package minimums do not imply a broad tested matrix.
The 0.x API may change.

## 2. Released v0.4.0 milestone

[v0.4.0](https://github.com/masahitojp/mariamem/releases/tag/v0.4.0) was published
on October 3, 2026 from `39537e9bb2fbbc28315e1ff672960ad734a9e399`.
[Release CI](https://github.com/masahitojp/mariamem/actions/runs/37109036059)
passed both platforms, aggregate guard, publication and both public smokes.
Go source/module, host-only Python wheels, corresponding GPL source, notices,
provenance and hashes are published. PyPI remains unavailable; use Release wheels.

Generated-Go/direct-link became the normal runtime, removing the normal Wasmer/
native-bundle dependency. **Cheap to create improved materially**: the fixed
reference measured Start p50 38.4 ms, Fork p50 104.6 ms and ×16 CPU p50
2.814 CPU-sec versus Wasmer's 308.5 ms, 288.7 ms and 9.463 CPU-sec.
Snapshot preallocation recovered the migration regression: p50 399.9 ms is
approximately unchanged from the Wasmer reference; its p95 remains slower.
Diagnostic Snapshot TotalAlloc fell 69.6%. The closed-handle pipe-FD fix is
integrated. These observations do not establish cheap sustained reclamation.

Compatibility was preserved: core SQL/transactions/constraints, auth,
CLIENT_FOUND_ROWS, sessions/MaxSessions, reconnect, repeated/concurrent lifecycle
and Snapshot/Fork fixture/write/schema isolation pass. External acceptance
includes **SQLAlchemy44/44** and **GORM32/32**, including repeated AutoMigrate.
Directory-FD identity/rename-name-reuse, MemFS grow/truncate and focused
handwritten/runtime race regressions remain covered.

For exact boundaries, p50/p95, slow runs and source identities, see
[canonical integrated measurements](../benchmarks/v04-integrated-candidate.md),
[Wasmer reference](../benchmarks/v04-baseline.md),
[consumer build measurements](../benchmarks/direct-link-consumer-experience.md) and
[release notes](../release/NOTES-v0.4.0.md). Historical readiness/migration audits
are evidence, not pending release work or a second roadmap.

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

## 4. v0.4.x purpose / decision gates

**Prove that Disposable isolation is practically viable, and fix only the
resource/performance problems that materially prevent users from choosing it.**
This is not a goal to make Fork faster or implement CoW/mmap.

Three questions guide the work:

- **Cheap to reclaim:** generational create/use/Close soak in a long-lived
  consumer, with fresh-process controls. Check resource and latency plateaus
  rather than accumulation: live heap, RSS/physical footprint, FDs, goroutines
  and successive-generation latency. Preserve the distinction between reachable
  objects and OS accounting.
- **Prepared-state value:** compare Fresh Start + preparation against
  Snapshot/Fork with realistic fixture and migration costs, including preparation
  and amortization. Determine whether Fork latency actually limits choosing
  disposal; a faster microbenchmark alone does not answer this.
- **Generated-Go consumer cost:** use existing evidence and representative
  consumers to assess cold build/CI time, module/source size, binary size,
  compiler RAM/disk cost and warm/incremental behavior. Source size alone is
  not an acceptance criterion.

Define workloads, concurrency, resource/latency budgets and stop conditions
**before optimization**. If resources plateau and behavior is practical, stop;
do not pre-optimize. If a demonstrated blocker has a small, bounded remedy,
a v0.4.2 may be justified after correctness and workload validation. If the
improvement requires broad CoW/mmap/storage redesign with uncertain return,
defer until real workload evidence justifies it. These are implementation
options, not roadmap goals or selected architectures.

## 5. Tentative v0.4.1: direct-link polish + Disposable viability measurement

Low-risk implementation candidates, subject to evidence and a separate decision:

- Evaluate whether `caching_sha2_password_auto_generate_rsa_keys` is unnecessary
  for the test guest and can be disabled without changing supported auth behavior.
- Remove clearly dead embedded-executable/provisioning/spawn machinery left by
  direct-link migration, preserving required legacy fallback and public behavior.

**Migration / release toil cleanup:** audit migration-only tests, obsolete
Wasmer/native-bundle gates, duplicated verify/release work, stale architecture/
release documentation and old packaging paths. Preserve equivalent product
coverage and exact-source → immutable-artifact → external-acceptance → guard
invariants, including corresponding source/notices. Remove historical migration
ceremony, not required fallback checks or release trust.

**Experimentation tooling:** build on the existing dry-run cleanup and measurement
scripts. Standardize cache/work/evidence retention, trials, fresh-process
boundaries where appropriate, environment capture, raw evidence and baseline
comparison. Add repository skills only where they reduce repeated agent/human
toil. Spend reasoning on hypotheses and decisions rather than repeated mechanics.

## 6. Product validation before v0.5

Compare mariamem fresh, mariamem Snapshot/Fork, Testcontainers fresh and a shared
real MariaDB with rollback/schema reset where practical. Use representative
workloads and explicit isolation contracts; shared reset and fresh instances
are different choices, not equivalent guarantees.

Evaluate wall time and resource cost alongside cleanup/reset responsibility,
test coupling, failure aftermath and review complexity. Include preparation and
failed tests, not only successful steady-state SQL. The question is whether
fresh-instance isolation is cheap enough to choose disposal over cleanup
discipline. Any simpler-test/review or coding-agent benefit must be validated,
not advertised from latency measurements alone.

## 7. v0.5.0: stable/LTS MariaDB

Migrate the guest from its alpha lineage to a deliberately selected **stable/LTS
MariaDB** revision; no target version is chosen yet. Refresh compatible WASIX/
toolchain inputs as needed, preserving traceable reproducible generation.

Rerun SQL/protocol/auth/session/lifecycle, Snapshot/Fork/isolation and ORM
compatibility, plus the full shared-memory race census and reduced patterns.
An upgrade is not assumed to fix the race set. Decide adaptation scope from the
new evidence and record a new performance/resource baseline.

## 8. v0.6: broader consumer / workload evidence

Broaden real workloads after the stable-guest migration: Django,
Alembic/migrations, metadata-heavy clients and dbt-like workloads. Retain
SQLAlchemy/GORM as regression anchors. Use these consumers and their preparation,
isolation and failure costs to decide whether further Fork/resource work is
justified; do not promise compatibility before running them on supported platforms.

## 9. Longer-term options

CoW/immutable Snapshot views, mmap, runtime sharing, stronger hard failure
containment, higher session capacity and more platforms remain evidence-driven
options. They are not version goals or selected production designs. Ready-heap/
live-worker reentry was rejected for v0.4; preserve the
[reentry boundary](../benchmarks/reentry-feasibility.md),
[CoW evidence](../benchmarks/cow-feasibility.md) and
[prepared-files findings](../benchmarks/prepared-clone-feasibility.md).

Toward 1.0, stabilize lifecycle/isolation/compatibility contracts through workload
evidence. Keep **Explore → Challenge → Human decision → Implement → Verify**.
This document defines direction; issues own concrete tasks and linked reports
own detailed experiments.
