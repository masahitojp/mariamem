# mariamem project status

This document owns the current product hypothesis, released architecture and
roadmap. Detailed experiments belong in linked reports; implementation tasks
belong in issues. Version themes define direction, not implementation approval.

## 1. Product hypothesis / current architecture

> mariamem should make a real MariaDB cheap to create, safe to throw away,
> and cheap to reclaim.

The product hypothesis is **Disposable isolation**: fresh-instance isolation can
be cheap enough that users choose disposal over cleanup discipline. It moves
reset responsibility from test code into the database lifecycle, reducing
rollback/truncate/schema-reset discipline, test-to-test state leakage and failure
cleanup burden. Clients and owned DB/Snapshot handles still require normal Close.
Simpler tests and reviews, including tests written by coding agents, remain a
hypothesis rather than a demonstrated AI productivity claim.

mariamem runs real MariaDB SQL/InnoDB for Go/Python integration tests. v0.4.0
provides evidence for cheaper creation and ordinary isolated disposal. The
accepted v0.4.2 candidate adds evidence for cheap reclamation across bounded
sustained generations, with final release verification pending. Hard failure
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
Prepared files use private file-backed mappings, allowing OS sharing of clean
pages and child-private modified pages. This OS-level CoW is distinct from
runtime-state cloning or a custom CoW filesystem and is not a memory-usage
guarantee. See [Copy-on-Write terminology](copy-on-write.md).
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
native-bundle dependency. **Cheap to create improved materially**: Start, Fork
and parallel CPU improved against the fixed Wasmer reference. Snapshot
preallocation recovered the migration regression; slower tails remain recorded
in the reports. This milestone is released and complete, but does not establish
cheap reclamation across sustained generations.

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
- **Resource accounting remains boundary-specific.** The accepted v0.4.2 candidate
  removes repeated 2 GiB Go backing allocation and explicitly releases linear
  memory after cooperative worker join. Go filesystem/metadata heap remains
  GC-managed; live heap, RSS and OS physical accounting are different measures.
  The earlier [Snapshot lifetime investigation](../benchmarks/v04-snapshot-memory-lifetime.md)
  remains historical evidence. No GC/FreeOSMemory policy was added.
- **Go1.27.0/1.27.1 arm64 are unsupported** because of upstream compiler issue
  #81036 (`LDPSW: constant is not in pool`). An upstream-fixed toolchain was
  verified previously; no mariamem compiler/generated-source workaround is used.
- **Approximately one-second startup tails remain observable.** Earlier tracing
  established legal guest-side condition-variable behavior; the latest campaign
  does not prove the cause of each individual slow run. No timeout shortening or
  forced wakeups suppress the tail.
- **Legacy Wasmer fallback remains.** Its bundle/provisioning/notices infrastructure
  is retained but does not participate in ordinary direct-link startup.

## 4. v0.4.1 — Distribution polish

**Make the generated-Go distribution match the actual direct-link architecture.**
[v0.4.1](https://github.com/masahitojp/mariamem/releases/tag/v0.4.1) is released.
It removed unused platform executable images and directly related dead metadata,
preserving explicit legacy fallback, Python host-only packaging and
corresponding source/notices/provenance.

The completed experiment measured comparable local complete module zips of
roughly **115 MiB → 31 MiB (~73% reduction)** with unchanged normal generated
MariaDB code and passing consumer/package smoke. See the
[distribution report](https://github.com/masahitojp/mariamem/blob/022011d724b6114a842b0996ed358dbb2f2d4c95/benchmarks/v041-distribution-cleanup.md).
The exact distribution candidate passed [both-platform Release CI verify](https://github.com/masahitojp/mariamem/actions/runs/37211034305);
publication is complete. No mmap or unrelated runtime change was included.

## 5. v0.4.2 — Disposable memory lifecycle

**Make repeated create/use/Close cycles remain cheap in a long-lived process.**
The human-approved production candidate preserves released pure-memory32 semantics
and uses mmap on macOS arm64 / Ubuntu 24.04 x86_64. Shared memory still starts at
256 MiB, grows without relocating its base, and has a 2 GiB maximum. Generic
non-wrapping, width-aware bounds checks and atomic alignment produce controlled
WASM traps; host imports see the logical range. Linear memory is released after
cooperative worker join, including tested initialization/startup/guest-failure
paths and repeated Close.

Native contract, focused race and product/ORM acceptance pass on both platforms.
Bounded macOS create/use/Close and Snapshot/Fork measurements show materially
lower sustained CPU/latency and plateauing resources, with a modest accepted
fresh-start correctness cost. See the
[accepted candidate report](https://github.com/masahitojp/mariamem/blob/dc939de87087cadf229f017c1a5942496aae45da/benchmarks/v042-production-candidate.md).
The design is selected for integration; v0.4.2 is not yet released. Exact-final-SHA
Release CI verify, source/notices/provenance and separate publication remain.
Memory64, non-cooperative forced termination, Fork optimization and Wasmer
retirement are outside this release.

In or around v0.4.2, compare **mariamem fresh**, **mariamem Snapshot/Fork**,
**Testcontainers fresh**, and **shared real MariaDB + reset/rollback** under
repeated disposable workloads. Include fixture/migration preparation, amortization
and failure cleanup, not only one-shot startup. Define concurrency, disk/resource
budgets and stop conditions before runs; measure generation latency/CPU, live
heap, RSS/physical footprint, FDs and goroutines. Keep different isolation
contracts explicit. Existing [suite comparisons](../benchmarks/practical-suite-comparison.md)
are reference evidence, not acceptance of a new memory implementation.

## 6. v0.4.3 — Architecture consolidation + Product validation

**Retire legacy Wasmer if generated-Go is proven sufficient, and validate the
product value of Disposable isolation.** Wasmer is no longer a normal
user-selectable product runtime; the still-supported explicit fallback is mostly
migration/development residue, not a second long-term product architecture.

Once the sufficiency/removal decision is made, retire unneeded NativeDir and
bundle resolver/cache, Wasmer startup, legacy bundle packaging, and
Wasmer-specific tests/gates/docs/licenses. Preserve required upstream licensing
and historical tags/reports as comparison references rather than maintaining a
second live runtime indefinitely. This roadmap does not remove today's fallback
contract by itself.

Product validation asks whether **fresh-instance isolation becomes cheap enough
that users choose disposal over cleanup discipline**. Compare wall time together
with isolation contract, cleanup/reset responsibility, test coupling, failure
aftermath, resource cost, review complexity, Docker/runtime dependency and
first-use/build cost. Any benefit for coding-agent authored tests remains a
hypothesis to validate, not a product claim derived from latency alone.

Results guide future priorities. They do not block release merely because an
alternative is faster under a different isolation model.

## 7. v0.5.0 — Stable guest

Move MariaDB from the current alpha lineage to a deliberately selected
**stable/LTS release**, refreshing compatible guest/WASIX/toolchain inputs as
needed and preserving reproducible generation. No target version is selected
here. Prefer doing this after architecture consolidation so the upgrade does not
need to maintain both generated-Go and legacy Wasmer paths.

Rerun SQL/protocol/auth/session/lifecycle, Snapshot/Fork/isolation and consumer
compatibility. Rerun the full shared-memory race census and reduced patterns on
the new guest/toolchain; an upgrade is not assumed to fix the known race set.
Record a new performance/resource baseline rather than carrying old results
across changed inputs.

## 8. v0.6.0 — Real workload breadth

Expand actual consumer/workload evidence: **Django**, **Alembic/migrations**,
metadata-heavy clients and dbt-like workloads. Retain SQLAlchemy/GORM as
regression anchors. Use real preparation, isolation, migration and failure costs
to decide whether further Fork/resource optimization is justified. Do not promise
compatibility before running the consumers on supported platforms.

## 9. Maintainer / tooling direction

Experiment workspaces should themselves be disposable. Preserve compact reports,
JSON/CSV evidence, checksums and selected unique profiles; retain reusable
expensive caches instead of unlimited raw outputs, regenerated sources and build
residue. Use explicit disk budgets, free-space/resource guards and safe cleanup
of completed worktrees and failed-run scratch.

Script repeated benchmark mechanics: workload/trials, fresh-process boundaries,
environment capture and comparable baselines. Turn repeated deterministic
workflows into repository skills where useful; hypotheses and product decisions remain
human/model work. Audit migration-only tests/gates/docs and release toil while
preserving current product coverage and exact-source → immutable-artifact →
external-acceptance → guard invariants, including corresponding source/notices.
These are maintainer practices, not extra v0.4.1 runtime scope.

## 10. Longer-term options

Runtime-state CoW, custom filesystem CoW/stronger immutable Snapshot ownership,
mutable execution-state sharing, stronger hard failure containment,
higher session capacity and broader platforms remain evidence-driven options.
These are additional mechanisms, not the prepared-file OS CoW already in use.
They are not selected version goals. The selected mmap lifecycle design and its
validated limits belong to the v0.4.2 section above. Ready-heap/live-worker reentry
was rejected for
v0.4; preserve the [reentry boundary](../benchmarks/reentry-feasibility.md),
[CoW evidence](../benchmarks/cow-feasibility.md) and
[prepared-files findings](../benchmarks/prepared-clone-feasibility.md).

Toward 1.0, stabilize lifecycle/isolation/compatibility contracts through workload
evidence. Keep **Explore → Challenge → Human decision → Implement → Verify**.
This document defines direction; issues own concrete tasks and linked reports
own detailed experiments. Version themes do not authorize implementation.
