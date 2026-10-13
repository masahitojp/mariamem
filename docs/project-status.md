# mariamem project status

This document owns current state and future direction. The
[user guides](../README.md) own usage, [architecture](v04-generated-go-architecture.md)
owns current HOW, [decisions](decisions/snapshot-product-contract.md) own
continuing product constraints, and reports preserve historical evidence.
Version themes are direction; they are not release approval.

## Product contract

mariamem provides disposable real MariaDB databases for tests. Each test normally
owns one mutable DB, uses normal connections and commits/rollbacks, then discards
the DB. Expensive migrations/fixtures may be prepared once and reused as a fixed
Snapshot baseline. What is shared is the initial state, not previous tests'
mutations. Fork creates an independent mutable DB; a modified child can create
a new baseline without changing its parent.

Normal user entry points are acquisition functions and test-per-database fixtures.
Successful Snapshot consumes its source; rejected busy/transaction preconditions
preserve it. Close boundaries remain explicit.

Persisted baselines are advanced derived artifacts. mariamem does not manage
cache freshness, regeneration or deletion. Diagnostics do not define the normal
Snapshot lifecycle. These are product choices independent of reference-project
APIs. See the [adopted contract](decisions/snapshot-product-contract.md).

## Current published release: v0.4.7 — Upstream converter migration

[v0.4.7](https://github.com/masahitojp/mariamem/releases/tag/v0.4.7) was published
on 2026-10-11 from source `e0be06f3a20c72cbb5a9be27971280c80a3ec357`;
annotated tag object `c201bf577440440253155e665def9c25ac5064f0`.
It adopts pinned goccy/wasm2go plus nine maintained patches on the unchanged
13.1.0 guest. Its published source is the A–D execution baseline; the former
candidate notes below preserve preparation scope. A–D changes are unqualified
until their own final native qualification and Human Review.

## Previous release: v0.4.6 — Product usability and validation

[v0.4.6](https://github.com/masahitojp/mariamem/releases/tag/v0.4.6) was published
on 2026-10-10 from source `b56be17206b6beef18f55c8ea39b254638da8590`;
annotated tag object `09d7b82e1900318dde45d08bebd9328ea35e6ef7`.
The [release run](https://github.com/masahitojp/mariamem/actions/runs/38040418075)
passed source reproduction, both native platform artifact/consumer qualification,
aggregate READY, publication and public smoke on macOS15 arm64 and Ubuntu24.04
x86_64. The released tag peels to that exact source; main matched it at this
post-release documentation review. These results qualify the released source,
not later documentation commits.

Go `LoadSnapshot(ctx, path, opts)` completes persisted-baseline acquisition.
Go/Python guides and [bounded product comparisons](../benchmarks/v046-product-validation.md)
cover Fresh, preparation reuse, optional persistence and independent children.
Go minimum 1.26.0, mysql client v1.9.3, guest, generated runtime and Snapshot format
remain unchanged. Release validation uses Go1.26.8 and Python3.14; accepted
Go1.27 consumer scope is documented in [compatibility](go-compatibility.md).
No Snapshot or filesystem optimization is included.

The earlier [integration verify run](https://github.com/masahitojp/mariamem/actions/runs/38033500776)
qualified source `8c07a9bd3278f7c8d2c633c38b7c41377d43100a` with private 0.4.5-labelled
artifacts. It is historical preparation evidence, not the final v0.4.6 artifact
identity. See [integration history](reviews/v046-release-qualification.md) and
[release notes](../release/NOTES-v0.4.6.md).

## Previous architecture baseline: v0.4.4

[v0.4.4](https://github.com/masahitojp/mariamem/releases/tag/v0.4.4) is released
from source `8ede4ad65def07436b64801076004ff80aec0799`; annotated tag object
`0a22ba1e02957b7bfd616836c65b72040698c617`. The
[release run](https://github.com/masahitojp/mariamem/actions/runs/37924209669)
passed final-artifact qualification, publication and both-platform public smoke.
Its runtime basis is `c5f43106a8054bb59a2da9184a1c2103fe1a1d9f`, qualified on
both platforms by [Product CI](https://github.com/masahitojp/mariamem/actions/runs/37898847164).
Final source and tested runtime source are intentionally distinct identities.

Creation/import validates the complete Snapshot, then mariamem owns the exact
backing used by Fork. Supported operations do not mutate it. Fork does not fully
rehash content; silent storage corruption arising after ownership is not promised
to be re-detected on each Fork. External source edits/deletion after import do
not affect the owned baseline. Live Snapshots retain one FD per prepared file.
Python uses `snapshot()`, `snapshot_to(path)`, `load_snapshot(path)` and `fork()`.
See the [contract](decisions/snapshot-product-contract.md),
[implementation review](reviews/v044-implementation-review.md),
[architecture](v04-generated-go-architecture.md) and
[release notes](../release/NOTES-v0.4.4.md).

Generated-Go is the only supported production runtime since v0.4.3. Snapshot is
cold prepared state; Fork starts fresh MariaDB execution rather than cloning
running heap/threads/TLS/locks/stacks. Private file mappings use OS page CoW;
there is no custom CoW filesystem or Unix fork. Historical measurements and
release repairs remain evidence, not instructions for the current user lifecycle.
See [v0.4.3 characterization](../benchmarks/v043-characterization.md) and the
[v0.4.4 review reports](reviews/v044-release-runtime-reuse-design.md).

## Previous release: v0.4.5 — Infrastructure stabilization and measurement

v0.4.5 is published from `d992e26a6d110ceeb54f69d71acd1358c72abb1b`.
The [public smoke recovery report](reviews/v045-public-smoke-recovery.md) records
macOS success and the corrected Ubuntu smoke success with distinct identities.

The [infrastructure audit](https://github.com/masahitojp/mariamem/blob/d7b1c0f60591843b0e72327fba7c62d26b7a3ee4/docs/reviews/development-infrastructure-audit.md)
and [bounded plan](reviews/v045-stabilization-plan.md) own the work sequence.
Restore wire coverage, detach ordinary development from expiring Product receipts,
extract live helpers before retiring historical infrastructure, and establish
clear runtime/artifact/measurement responsibilities. Release qualification remains
fail-closed. Source reproducibility and handwritten inclusion remain required.

Snapshot latency, suite crossover and bounded product measurements follow stable
verification infrastructure; no performance optimization is approved in advance.
No guest upgrade or new product feature is included. A reusable runtime-evidence
model or reduction of required checks needs a focused Human Review first.

Approved runtime-only qualification and identity-bound publication smoke have
been implemented on dedicated branches. Both-native qualification passed for
`34eaea1df86b57765a4d8b0840845a33d539065f`; exact tested and measurement harness
identities remain distinct. The [v0.4.5 Human Review packet](reviews/v045-human-review.md)
records restored wire ownership, canonical checks, CI feedback latency, source
reproduction scope and completed local Snapshot/crossover/product measurements.
Light preparation favors Fresh; expensive data preparation benefits from reuse.
Snapshot traversal reduction was deferred, not implemented. Release CI qualified
and published v0.4.5; the recovery report above records final public smoke.

The [final verification-economics review](reviews/v045-verification-economics.md)
keeps distinct source/runtime/artifact/publication guarantees and moves existing
source/license/mirror checks before expensive compilation. Generated output and
license records are unchanged; evidence trust-scope redesign is deferred to later
Fast Feedback work. The [measurement document](../benchmarks/v045-measurement.md)
owns exact conditions/reproduction. No Snapshot optimization is adopted.
The [agreed v0.4.6 handoff](reviews/v046-handoff.md) covers Go persisted-baseline
loading, comparable language documentation/examples and subsequent realistic
Product Validation; those changes are not part of v0.4.5.

## Supported scope and limitations

- macOS 15+ arm64 and Ubuntu 24.04 x86_64. Canonical acceptance uses Go 1.26.8
  and Python 3.14; minimum package versions do not imply a broad tested matrix.
- Full generated guest is not Go race-detector clean. Preserve the
  [race census](../benchmarks/direct-link-race-scope.md); focused handwritten
  checks do not prove general race correctness.
- Forced timeout/hard-failure containment is not guaranteed. Normal cooperative
  cleanup and non-cooperative reclaim are distinct boundaries.
- Approximately one-second startup tails remain observable; do not suppress
  them or infer their cause from earlier individual traces.
- External consumer checks passed on macOS arm64 with Go 1.26.8 and
  1.27.0/1.27.1/1.27.2. See [compatibility](go-compatibility.md); minimum Go
  and driver versions are unchanged.
- Physical footprint, RSS and reachable heap are different resource measures.
  The v0.4.2 lifecycle releases linear memory after joined workers; filesystem
  metadata remains GC-managed.
- Live Snapshots retain roughly one FD per prepared file. The 64-table fixture
  had 137 files and released its backing FDs after Close on both platforms.
  Many simultaneously retained baselines, especially file-heavy schemas, may
  approach process FD limits. Gather real workload evidence and improve the
  resource model if pressure is demonstrated; this is accepted and non-blocking
  for v0.4.4, not a reason by itself to create v0.4.5.
- The 0.x API may change. Corresponding guest source, licenses, notices and
  reproducible generation remain required.

## Performance evidence and pending optimization questions

The [Go 1.26.8 / 1.27.2 comparison](benchmarks/go126-vs-go127.md) retains
same-source macOS arm64 suite/resource results and reproduction evidence.
No consistent practical speedup was demonstrated; these observations do not
change the supported toolchain policy or qualify the current main SHA.

The [memfs Architecture Decision](reviews/memfs-architecture-decision.md) is the
single decision/routing reference. Retain current memfs + MAP_PRIVATE, defer full
VFS replacement and mmap-prefix/tail, and consider growth-factor or sparse/chunk
PoCs only after its limited-measurement gates. This is technical direction,
**not Human implementation approval**. Its [memfs/pglite](reviews/memfs-optimization-discovery.md),
[pgmem](reviews/pgmem-vfs-design-review.md) and
[block-storage](reviews/block-storage-design-discovery.md) reports are historical
inputs with pinned source hashes. The observed ~4.62 GiB is cumulative allocation
across 20 Fresh DBs including fixture work; it is not retained memory or an
estimate of removable allocation. The [benchmark index](../benchmarks/README.md)
already owns measurement navigation; no duplicate report is introduced.

### Research handoff — independent of v0.5.0 guest migration

**MemFS limited measurement:** use the existing Decision's §7 as the sole scope
and acceptance reference: file/phase initial allocations, reallocations/copied
bytes, unique write coverage, child-only mapped detach and corresponding
wall/CPU/Peak RSS. This work remains unperformed and needs separate authorization;
do not create a second measurement plan or backend implementation here.

**Snapshot lifecycle/shutdown:** pgmem stops its server, clones VFS state, then
restarts the original; mariamem consumes the source on successful cold Snapshot.
The [existing Snapshot characterization](../benchmarks/v045-measurement.md#snapshot-lifecycle-research-boundary)
already measures the public operation, host/export envelope, materialization,
read/hash, copying and owned acquisition. Reuse those traces first. Remaining
questions are pure shutdown versus guest snapshot-copy inside that envelope,
read versus hashing CPU in combined intervals, and any decision-relevant
unattributed manifest/cleanup residual. Fork startup/recovery is a separate
operation. The pgmem ~10 ms reference has different lifecycle/storage boundaries
and is not a comparable mariamem performance result. Restarting the source or
changing InnoDB shutdown mode is not approved.

Neither research item blocks v0.5.0. Performance PoCs, if later authorized,
require their own correctness and product-benefit decision; stable-guest behavior
must be rechecked before integrating an optimization selected on the old guest.

## v0.4.7 — Upstream converter migration (candidate)

The released scope replaces the pinned shibukawa converter fork with pinned
`goccy/wasm2go` plus nine maintained patches. MariaDB guest identity, public APIs,
Snapshot format and minimum Go version remain unchanged from v0.4.6. Independent
regeneration, runtime/consumer checks and same-scenario product/resource comparisons
must precede the Human release decision. Native macOS/Ubuntu artifact qualification
remains CI-owned. No guest upgrade, handshake experiment or VFS optimization is
part of v0.4.7. Historical candidate measurements qualify only their recorded inputs.

## v0.5.0 — Stable guest

Final Qualification passed for exact candidate source
`bb637c49e6d6b50ec6761dead172a35f0b051f7e` in
[verify run 38366609671](https://github.com/masahitojp/mariamem/actions/runs/38366609671).
Independent guest builds/Go regeneration, both native platform suites, external
consumers and aggregate source/license/artifact guards passed; CI returned READY.
The [qualification report](reviews/v050-final-qualification.md) preserves exact
receipts and distinguishes the workflow source from the tested candidate.
After that Human Review, the maintainer authorized Product Verification.
The [approved 80-cell campaign](../benchmarks/v050-product-verification.md)
is complete: SQL/isolation oracles and bounded cleanup pass; timing is mixed,
including an adverse Go parallel-Fresh median under the existing startup tail.
Candidate acceptance/integration and the release decision remain in the
[review](reviews/v050-human-review.md).

The maintainer authorized the limited J1 completion/reclamation repair after the
paired counterexample. The [implemented candidate](reviews/v050-join-lifetime-fix.md)
binds worker map reclamation to final agent access, covering delayed wake,
detached self-exit and unwind. Guest/raw converter inputs remain unchanged;
owned generated edits are independently reproduced. T1/T2/J1 close the identified
corrective items in the agreed current-guest investigation. Candidate adoption
and the later qualification evidence remain separate from release approval.
Completed Product Verification is the next
[candidate acceptance handoff](reviews/v050-human-review.md).

The bounded [R1–R5 investigation](reviews/v050-semantic-audit.md) supplied the
per-target access/lifetime and supporting-protocol review: 65 functions, 147
narrow writer sites, 28 target records and all 14 original families. Its original
result supported the reviewed mappings while identifying T1/T2 and leaving J1
unresolved. The [subsequent paired comparison](reviews/v050-boundary-join-fixes.md)
confirmed premature allocation reuse in original Wasm and Go under a forced
schedule. No Go-only forbidden outcome or natural SQL harm was established.
Those historical findings led to the authorized repair above. Coverage and local
repair verification do not replace final release qualification.

The [assessment review](reviews/v050-access-review.md) preserves why the earlier
investigation and progression recommendation were incomplete, and the finite
contract used to finish this investigation. No scope reduction was made; the
five-hour cap was a stopping budget, not a completion test. Hourly reporting was
cancelled by the Human. Prior exact-width fixes remain; the investigation itself
changed no product implementation. The later owner fixes are recorded separately
above. Final Qualification has subsequently passed for the exact candidate
recorded above; the subsequently approved Product Verification is complete as
recorded at the top of this section.

On the dedicated v0.5.0 experiment branch, the maintainer approved formal
exact-width narrow atomic writer integration after bounded design verification.
The [integration report](reviews/v050-exact-writers-integration.md) records the
unchanged accepted 12.3.3 guest, independently regenerated runtime, retained
failure oracles and local regression/consumer results. Native Ubuntu focused development
verification subsequently passed in the linked Development CI receipt; this
does not qualify the new macOS-only protocol fixtures. This branch work does not qualify main or
establish general shared-memory correctness; final Qualification, Product
Validation and the Human release decision remain separate. The roadmap and
earlier management-stage statements below retain their historical scope.

Fast Feedback phase timing and task-local Go cache reuse were integrated at
`70ac70ce0a4ccda403aa290dffa1d0bac0d8728b`. The approved single-pass development
guest route was integrated at `ee48a2a50fe71e79564ab1dde42c45594f220438`.
It builds into isolated external outputs, records actual source/tool/artifact
identities and runs a freshly generated host smoke. Results remain UNQUALIFIED;
independent Release builds and qualification guards are unchanged. The current
guest passed Linux arm64 build and macOS arm64 native smoke; this does not qualify
a new guest or native Ubuntu runtime. See [validation and exact measured identities](reviews/v05-dev-guest-build-validation.md)
and [development commands](development.md#single-pass-unqualified-guest-development).

The maintainer authorized A–D integration of exactly MariaDB **12.3.3** on
2026-10-12, retaining the v0.4.7 goccy converter pin and nine patches. Selection
is an exact source input, not an LTS classification or a multi-series promise.
The [A–D integration report](reviews/v050-ad-integration.md) owns adopted inputs,
reproduction, local checks and remaining work. This branch is not release-qualified.

The approved [common portability plus minimal source-specific hunk policy](decisions/guest-patch-management.md)
is implemented for the single 12.3.3 input: ordered hash-bound patches with
preimage/postimage verification. The handshake reads the running guest's VERSION()
without an old-version fallback. Saved old-guest Snapshots require recreation.

The [bounded correctness judgment](reviews/v050-correctness-judgment.md)
reproduces fd_allocate data loss, zero-length bulk trap omissions and load-only
subword CAS writes. Three bounded corrections are recommended before qualification;
no production fix was applied in that judgment. The maintainer subsequently
authorized the [three bounded corrections and feasibility study](reviews/v050-correctness-fixes.md).
Those owner changes, independent regeneration and local checks are complete;
no general shared-memory guarantee or RELEASE READY status follows.
Human review chooses whether to retain the stated limits or require a broader
design before final Qualification and Product Validation. The same conflicting
accesses report races on Go heap and none on production mmap backing under the
observed Go1.26.8 macOS arm64 detector. Shared-memory semantics and acceptance of
that documented observation limit require a separate Human decision.

Follow-up correctness decisions, both-native final qualification, Product
Validation and Human Review remain. Shared-memory race census/semantics and
observation limits remain separate work; a guest upgrade is not assumed to fix
existing races. No release-ready or performance claim follows from A–D checks.

## v0.6.0 — Dogfood and fixture ergonomics

Use real consumer/workload evidence, including Django, Alembic/migrations,
metadata-heavy and dbt-like workloads. Retain SQLAlchemy/GORM regression anchors.
Evaluate actual preparation, per-test isolation, resource and failure costs.

New run-wide baseline fixture ergonomics are deferred here. Existing session
fixtures remain worker-local under xdist. Do not promise new framework/platform
compatibility or introduce automatic cache policy before use-case evidence.

## Development discipline

Keep **Explore → Challenge → Human decision → Implement → Verify**.
Verification scope follows the changed boundary; explain a concrete dependency
before broadening. See [development](development.md#local-verification).

Experiments are disposable by default. Preserve compact measurements, reports,
hashes and reproduction inputs rather than recreatable caches, completed
worktrees/builds or source copies. Completion includes cleanup and a retained-path
audit. See the [workspace policy](experiment-workspace.md).

CI owns exact-source build, acceptance and release qualification after handoff;
a submitted verification run does not publish or approve a release.
See [release workflow](releasing.md).
