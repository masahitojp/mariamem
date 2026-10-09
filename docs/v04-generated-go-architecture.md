# Current mariamem architecture

This document explains HOW the unreleased v0.4.4 candidate implements the
[user contract](../README.md). It is not a user prerequisite.
The [continuing product decision](decisions/snapshot-product-contract.md)
records WHY; historical experiments are evidence rather than current requirements.

## Execution and distribution

Generated-Go is the only supported production runtime. The MariaDB guest is
translated at build time and compiled as ordinary Go source. WASM is a build
intermediate; no Wasmer runtime or native-bundle provisioner is used.

```text
Build:
MariaDB / WASIX → pinned WASM intermediate → wasm2go → generated Go

Go:
consumer → public API / host → directly linked MariaDB

Python:
wrapper → packaged Go host process → linked MariaDB
                                      ↓
                              WASIX compatibility layer
                                      ↓
                             per-database MemFS state
```

Go runs the guest inside the consumer process. Python has one packaged host per
DB and no long-lived Snapshot manager. The host process is not a promise of
general hard-failure containment. Ordinary startup needs no runtime download.
Python host executable identity remains checked.

Build/source provenance includes pinned inputs and overlays, toolchains,
intermediate identity, converter patches, translated inventory and final
platform artifacts. See [guest reproducibility](v04-guest-reproducibility.md),
[licenses](v04-license-inventory.md) and [source provenance](guest-source-provenance.md).
Required guest/sysroot/notices obligations remain even though Wasmer is retired.

## Cold baseline acquisition

Snapshot drains sessions, shuts down the source guest and exports committed
database files. Success consumes the source DB; rejected active-client or
transaction preconditions preserve it. Files are cold database state, not a
captured running heap, thread, TLS, lock, stack or waiter.

The private acquisition implementation is in
`internal/snapshot/owned.go` and `python/mariamem/snapshot.py`.

- Temporary capture: take over newly created implementation-owned output after
  producer writers have stopped.
- Persisted capture or external import: copy the external output into private
  backing. Preserve expected manifest hashes; do not replace them with newly
  calculated hashes from a possibly changed source.
- Open backing read-only, remove ordinary path aliases, and completely validate
  inventory, format, size, guest identity and content through retained FDs.
- Successful acquisition retains those exact resources until Close.
  Verification success is not a boolean cache associated with a pathname.

The independent copied backing makes later source replacement, truncation,
editing or deletion irrelevant to the acquired Snapshot. Import does not edit
the input. Persisted capture leaves the caller's requested output intact.

Acquisition verifies the state actually used by children. It is not a complete
security protocol against an adversary with control of the same user account
and process resources. Silent media corruption after acquisition is explicitly
outside the every-Fork detection contract.

## Fork and private child state

Go pins the owned backing through startup. Python passes retained FDs and a
handoff description to the packaged child host; the host verifies cheap
structure/guest/read-only-descriptor constraints before accepting ownership.
No original source pathname is reopened for Fork.

`internal/generatedgo/code/base/owned_prepared.go` creates independent MemFS
nodes and writable `MAP_PRIVATE` mappings from these FDs. The verified object
and the mapped object are the same backing resource. Clean file-backed pages
may be shared by the OS; writes are private. This is OS page-level CoW, not a
custom CoW filesystem or Unix `fork()`.

A child reconstructs MariaDB execution, anonymous linear memory, threads, TLS,
FD tables, offsets, clocks and session state. No live connections or transactions
are inherited. File growth can allocate/copy into child-owned Go storage
(`memfs_growth.go`). Existing grow/truncate, rename/unlink and directory/file
identity semantics remain required boundaries.

Fork performs cheap structural/lifetime/guest checks, not full inventory-content
rehashing. It does not guarantee rediscovery of later silent media corruption.
Child changes never modify a parent or sibling baseline; snapshotting a changed
child creates another independently acquired baseline.

## Lifetime and resources

Snapshot Close blocks future starts and releases owned FDs after admitted startup
operations. Already-started children hold their own mappings/resources and remain
usable. Each child must be closed independently. Ordinary Close is idempotent.
Failure paths must reclaim partial FDs, mappings, workers and wrapper resources.

Approximately **one read-only FD per prepared file** is retained for the Snapshot
lifetime. Multiple Snapshots add their file counts; concurrent child startup adds
transient descriptors. Practical limits depend on the caller's soft/hard FD
limits and prepared schema/file inventory. Measure realistic counts rather than
assuming data MiB predicts descriptor count. See the production review evidence
for qualified counts/limits; no numeric capacity promise is made here.

The local candidate resource check used 64 InnoDB tables: 137 prepared files,
so one Snapshot retained 137 FDs and sixteen retained 2,192 backing FDs.
A Python soft limit of 256 allowed one such baseline, but a second import
failed with EMFILE and reclaimed its partially opened files. Applications with
low limits must budget their other descriptors and simultaneous baseline count.
This is distinct from creating many children from one baseline. See the
[production review](reviews/v044-implementation-review.md) for measurements and
qualification status; both-platform CI is still pending.

Temporary capture names and private import staging are recreatable storage and
are removed. Explicit persisted outputs belong to the user and survive handle
Close. Close releases child mappings after cooperative guest/worker shutdown.

## Guest memory and known limits

The unchanged v0.4.2 memory32 contract uses a stable 2 GiB anonymous reservation,
initially enables 256 MiB, and grows the logical range without relocating it on
macOS arm64 and Ubuntu x86_64. Bounds/width checks and atomic alignment preserve
controlled guest traps. Close releases linear memory after cooperative worker
join; Go metadata remains GC-managed. Physical accounting is not reachable heap
and OS page sharing is not a zero-incremental-memory promise.

The full generated guest is not Go race-detector clean. The
[race census](../benchmarks/direct-link-race-scope.md) remains a documented general
shared-memory problem; focused handwritten checks do not prove otherwise.
Non-cooperative execution cannot be forcibly reclaimed in a Go process.
Query interruption invalidates the DB but does not establish hard containment.
No guest/version upgrade or guest race redesign is included in v0.4.4.

## Qualification boundaries

Correctness/isolation/lifetime checks precede performance evaluation.
Acceptance covers acquisition rejection, source detachment, sibling DML/DDL/
growth/transaction isolation, repeat generations/orderings, concurrent startup,
Close and failed initialization. Both macOS arm64 and Ubuntu x86_64 are required.

Performance must measure the production implementation and exact v0.4.3 control,
including creation/import, Fork-ready, suite SQL, cleanup, CPU and resources.
Historical hash percentages are not measured speedups. Broad COUNT scans remain
query cost; they must not be presented as ready latency. Measurements and pending
CI qualification belong to the implementation review, not to an architecture
claim of release readiness.

[Development verification](development.md#local-verification) defines mechanical
check selection. No new filesystem durability or security guarantee is added.

## Historical evidence

These links preserve historical results rather than current operational recipes:

- [v0.4 integration](../benchmarks/v04-integrated-candidate.md):
  generated-Go feasibility, preallocation and acceptance.
- [v0.4.2 memory candidate](https://github.com/masahitojp/mariamem/blob/dc939de87087cadf229f017c1a5942496aae45da/benchmarks/v042-production-candidate.md):
  disposable memory lifecycle.
- [v0.4.3 retirement](../benchmarks/v043-retirement-current.md):
  removal of Wasmer runtime/plumbing.
- [v0.4.3 characterization](../benchmarks/v043-characterization.md):
  per-Fork verification, mapping, initialization and recurring scans under the
  earlier path-based acquisition contract.
- [Historical integration audit](v04-integration-audit.md) and
  [ready-runtime reentry investigation](../benchmarks/reentry-feasibility.md):
  migration gates and rejected live-runtime reuse.
- The pre-cleanup architecture narrative is available at the
  [released v0.4.3 source](https://github.com/masahitojp/mariamem/blob/v0.4.3/docs/v04-generated-go-architecture.md).

Historic statements about no runtime-state CoW do not negate the current OS
page CoW of private prepared-file mappings.
