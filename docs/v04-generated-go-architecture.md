# Current mariamem architecture

This document explains current main after D/shared-host adoption on 2026-10-17.
These adopted changes are not in published v0.5.0. For the released file-backed
architecture, use the [v0.5.0 document](https://github.com/masahitojp/mariamem/blob/v0.5.0/docs/v04-generated-go-architecture.md).
The [product contract](decisions/snapshot-product-contract.md) records WHY;
[changes since the release](changes-since-v050.md) records API migration.

## Execution and distribution

Generated-Go is the only supported production runtime. MariaDB 12.3.3 / WASIX
is built into pinned Wasm, translated by pinned patched wasm2go, and compiled
as ordinary Go source. Wasm is a build intermediate. Ordinary startup needs no
Wasmer runtime, native-bundle provisioner or runtime download.

```text
Build:
MariaDB / WASIX → pinned Wasm intermediate → patched wasm2go → generated Go

Go:
consumer process → public API / host → independent MariaDB execution per DB

Python:
wrapper → packaged Go host per root lineage
            ├─ setup DB → immutable baseline
            ├─ child DB → private changes
            └─ child DB → private changes
```

Python host executable identity remains checked. The host is automatically
managed; users do not run a daemon. Independent root starts and xdist workers
use separate hosts. Each DB has its own MariaDB runtime, SQL endpoint, MemFS,
thread/session state and 16-connection capacity. The Snapshot uses no SQL
connection. Sharing a host does not share mutable DB contents.

Provenance binds guest/source patches, toolchains, Wasm identity, converter
patches, translated inventory, handwritten runtime owners and final artifacts.
See [guest reproducibility](v04-guest-reproducibility.md),
[licenses](v04-license-inventory.md) and [source provenance](guest-source-provenance.md).
No guest or converter update accompanied D adoption.

## Cold baseline acquisition

Snapshot rejects busy/transaction preconditions while preserving the source.
Accepted capture cooperatively stops MariaDB and joins all guest workers before
freezing the completed datadir. Success consumes the source. Failure after
acceptance can also consume it. This captures schema/data, not running threads,
TLS, locks, stacks, waiters, connections or active transactions.

`internal/generatedgo/code/base/heap_snapshot.go` seals the same FileStore
backing; `internal/prepared/root.go` owns immutable 16 KiB blocks and inventory.
Mutable byte slices are not exposed. Ordinary acquisition validates the bound
source, guest identity, state and structure without rereading contents. Strict
Heap imports, private transfers and borrowed-mapping copies retain content/digest
checks, including logical zero-filled regions. `internal/host/heap_snapshot.go`
and `internal/snapshot/root.go` connect capture to the public owned Snapshot.

Ordinary capture does not copy into guest snapshot-out and then materialize
host files. It owns process-local prepared blocks. Public persistence, external
import and path-based acquisition are removed; migration/seed recreates the
baseline in each test process. The ownership path also removes repeated content
scans while retaining explicit ownership and the required transfer checks.

## Fork and private child state

Go pins the owned baseline through startup. Python routes requests by ID to the
same shared host, whose registry owns baseline and DB handles. Admission pins
the backing while the independent child starts. Baseline Close prevents new
Forks and waits for already admitted launches; started children retain their
own references and remain usable.

`base/block_storage.go` and `base/memfs.go` create independent child metadata,
locks and dirty-block maps over immutable inherited blocks. A first write
privatizes the affected block. Sparse regions read as zero; shrink/regrow must
not expose truncated inherited bytes. File size, seek, truncate, allocate,
rename/unlink and open-handle semantics remain tested boundaries. Allocate
extends logical size; it does not promise physical storage reservation.

Each child reconstructs execution, anonymous linear memory, threads, TLS, FD
tables, offsets, clocks and sessions. Fork does not clone a running runtime.
Writes cannot change a parent or sibling. A changed child can become a new
baseline while its parent remains unchanged.

Fork uses cheap structure/lifetime/guest checks on owned backing rather than
rehashing all content. Ordinary capture binds the source before execution, joins
workers, seals the same FileStore backing and validates root identity/state/layout.
It does not rebuild or rescan payload for acquisition. It is not a detector for
arbitrary changes to private memory bytes. Strict Heap imports and private
transfer receivers still copy/verify content; borrowed mappings detach and compare
source/target before leaving their instance. See the approved
[ownership contract](decisions/snapshot-product-contract.md). Human Review
approved main adoption of candidate `52c078b`; release remains a separate decision.

An explicit different development host binary is an exception to the shared
host route. `internal/snapshot/handoff.go` materializes a private temporary
handoff, independently copies/verifies expected inventory/digests and requires
matching protocol/guest identity. Its file-backed private mappings remain an
internal compatibility route, not a public save/import API.

## Lifetime and resources

Close releases handle ownership. Child and derived-baseline references retain
blocks they still need, so closing a parent does not revoke a live child.
Go reachability/GC, retained heap and OS RSS have different timing; immediate
RSS reduction is not the definition of successful Close.

Ordinary baselines do not retain one backing FD per prepared file. Historical
137-file/FD-limit results describe the released file-backed implementation,
not the normal D path. Logs, control directories/sockets and linear-memory mmap
remain. Default logs and owned scratch are cleaned up; explicit user log paths
are preserved. The private cross-binary handoff has its own temporary-file cost.

Python `mariamem/_session.py` and `internal/control/shared.go` manage request
routing, per-owner operations/cancellation, late-success cleanup and final host
reaping. The host exits after the last owner and admitted operation finish.
A child's normal Close, ordinary SQL error or individual request cancellation
does not kill other live owners. Host crash invalidates that root lineage's
DBs and baselines. Separate roots continue independently; recreate lost setup.
This shared failure domain was accepted at main adoption.

## Guest memory and known limits

The memory32 runtime uses a stable 2 GiB anonymous reservation, initially enables
256 MiB, and grows the logical range without relocating it on the supported
platforms. Bounds/width/alignment checks produce controlled guest traps. Close
releases linear memory after cooperative worker join; metadata remains GC-managed.
A fatal worker trap notifies the linked transport owner before join and marks
that DB unusable. Its cooperative atomic/futex waits are cancelled, pending calls
retain the original cause, and later commands are refused. Completion and memory
release still wait for every worker; non-cooperative execution retains ownership
until it exits. Independent DBs have separate failure state.
Physical accounting differs from reachable heap or sampled host RSS.

The page-cleaner startup ordering correction is adopted on main and passed
bounded Fresh comparisons and related regression on both native platforms.
It does not promise a universal latency bound. See its
[source correction report](reviews/v050-startup-tail-source-fix-integration.md).

The full generated guest is not Go race-detector clean. The bounded v0.5.0
current-guest investigation closed its identified corrections; focused checks
and mmap race-detector silence do not establish general race correctness.
Non-cooperative execution cannot be individually forcibly reclaimed in the Go
process. Query interruption invalidates the DB; it is not hard containment.

## Validation boundaries

D/shared-host ownership, I/O, lifecycle, SQL/isolation, failure cleanup,
installed consumers and ORM checks passed on macOS arm64 and Ubuntu x86_64.
Canonical guest builds and Go regeneration/provenance checks also passed.
The [implementation/adoption report](reviews/d-heap-shared-host.md) records exact
source identities, oracles, SKIPs, platform scope and the accepted failure domain.
Its [approved design](reviews/d-heap-productization-design.md) preserves the
scope change removing public persistence.

The limited benefit comparison is macOS-only. The unexplained slow
resource-observed trial remains for final release validation.
[Final Qualification](reviews/main-storage-qualification.md) passed for combined
source `c97e55fc065f6ee7b560325077726da53e5d95d7` with fresh builds and both-native
acceptance in verify run 38935990860. Broader Product Validation remains pending;
that technical READY result does not authorize publication or qualify later SHAs.
[Development verification](development.md#local-verification) defines check
selection; [releasing](releasing.md) defines exact-source publication gates.

### Unimplemented WASIX host imports

[release/wasix-host-stubs.json](../release/wasix-host-stubs.json) classifies the
unimplemented host imports as `fail-closed`.
[tests/test_generated_runtime_inventory.py](../tests/test_generated_runtime_inventory.py)
checks the classification against non-test Go sources in `internal/generatedgo`.
When adding, removing or implementing a stub, review its disposition and update
this classification in the same change. Preserve the explicit failure boundary
for remaining stubs; update canonical source owners and regenerate where needed
rather than editing generated output alone.

Run `python -m pytest tests/test_generated_runtime_inventory.py -q` for the
inventory/classification check, then select any additional checks required by
the changed runtime boundary using [local verification](development.md#local-verification).
The current guard checks marked stubs and immediate host-method panics; it does
not establish that every panic is classified. An unmarked panic preceded by
another statement can escape detection. [#24](https://github.com/masahitojp/mariamem/issues/24)
tracks that gap and the required negative controls, separately from the adopted
[#13](https://github.com/masahitojp/mariamem/issues/13) detection net.

## Historical evidence

Historical file-backed ownership, FD/mapping limits and import behavior are
preserved in the [v0.4.4 implementation review](reviews/v044-implementation-review.md)
and the released architecture linked above. Earlier build/runtime work is in
[v0.4 integration](../benchmarks/v04-integrated-candidate.md),
[v0.4.3 retirement](../benchmarks/v043-retirement-current.md),
[v0.4.3 characterization](../benchmarks/v043-characterization.md) and the
[historical integration audit](v04-integration-audit.md). Their source identities,
measurements and API contracts are not current operational instructions.

### macOS platform-check lifetime

The Go platform checker keeps a successful macOS15+ arm64 result for the life
of its process. Initial concurrent checks share one active probe; waiting
callers retain independent cancellation. Failures are not cached. Once success
is recorded, later changes to the sw_vers executable or its answer are not
re-detected by that process. A new Go process checks again. Python siblings
reuse their shared Go host’s result; a new root host starts with no cached result.
Linux detection and Python wheel/hash verification retain their existing paths.
