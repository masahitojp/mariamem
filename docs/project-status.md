# mariamem project status

This document owns current state and future direction. The
[user guides](../README.md) own usage, [architecture](v04-generated-go-architecture.md)
owns current HOW, [decisions](decisions/snapshot-product-contract.md) own
continuing product constraints, and reports preserve historical evidence.
Version themes are direction; they are not release approval.
The current published release and later main changes are distinct sources.
Changing version metadata does not itself publish a release.

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

The maintainer approved D block storage plus one automatically managed Python
host per root lineage on 2026-10-16, and then removed public persistence/loading
from the implementation scope. Baselines become process-local; preparation inputs
remain migrations/seed. Child independence and consuming Snapshot are retained.
The maintainer approved main adoption on 2026-10-17 for reviewed candidate
`f55bd3a91073e9f80b8a816055acf0983b8b2e79`. Its runtime matches the bounded
macOS arm64 verification and native Ubuntu CI, which passed on source
`4282cba73f12c772942b72c2f020b3ec1228be11` in
[run 38908979283](https://github.com/masahitojp/mariamem/actions/runs/38908979283).
The shared-host crash domain and intentional public save/load API removal are
accepted for this use. That v0.5.1 performance comparison remained macOS-only;
the later [native Ubuntu campaign](reviews/ubuntu-product-performance-results.md)
confirmed the Snapshot gain on Ubuntu x86_64 (see the Snapshot stopping point
below). The earlier
slow resource-observed small-fixture trial is preserved; the later bounded
comparison did not reproduce it in 30 ordinary and 30 resource-observed candidate
repeats. Its cause remains unknown, rather than classified as noise or a defect.
Skipped probes remain explicit. The later authorized final configuration
Qualification passed for exact source `c97e55fc065f6ee7b560325077726da53e5d95d7`
in [verify run 38935990860](https://github.com/masahitojp/mariamem/actions/runs/38935990860).
Both native platforms and the aggregate guard returned READY after full builds,
regeneration and external acceptance. The [Qualification review](reviews/main-storage-qualification.md)
retains receipts/SKIPs. The subsequently authorized
[user-workflow/performance check](../benchmarks/main-product-verification.md)
completed 274 executions on those exact runtime inputs. Typical fixture reuse
and memory improved, while 100 MiB Go Fresh retains adverse results (all four
observations: median +7.2%). The [Product Verification Human Review](reviews/main-product-verification.md)
recommended accepting that tradeoff. The maintainer accepted the performance
review and authorized preparation/release as **v0.5.1** on 2026-10-17, explicitly
deferring the 100 MiB Go Fresh investigation until after release. Release CI
owned acceptance of the exact final-version source and its publication;
neither the earlier READY nor these measurements are relabelled as that source.
See the
[implementation results and Human Review](reviews/d-heap-shared-host.md) and
[approved design and scope change](reviews/d-heap-productization-design.md).

## Routine support adopted on main — unreleased

On 2026-10-20 the Human approved main adoption after the
[Human adoption review](reviews/routine-canonical-ci-review.md). Main fast-forwarded
to `429492fd35bc48948576b21cb3804726ced3c03a`, which contains the tested routine/text
candidate `03184a61a63b1977a1d05ed378404f59d57cf68e` plus evidence and build-ledger
updates. The subsequent documentation commit records this decision; runtime,
guest/converter inputs and generated provenance remain identical to the tested
candidate. No exploratory history was merged.

Procedures/functions and bounded DEFINER are included, together with the
product-managed mysql.proc structure boundary and necessary text multiple-result /
option paths. Packages/package bodies remain outside support/testing; events
remain an embedded restriction (1235). DEFINER metadata is retained, but account
existence/privileges are not enforced under skip-grant-tables. See the
[scope decision](decisions/routine-support-scope.md) and
[candidate report](reviews/routine-canonical-adoption.md).
Binary prepared productization and its unapproved prototype limits were not
adopted; that product requirement remains open.

[CI39406398732](https://github.com/masahitojp/mariamem/actions/runs/39406398732)
passed independent two-source-build reproduction, all99 generated files on macOS
arm64 and Ubuntu x86_64, required Connector/Python26.7.0, J1 failure/control
oracles and existing ORM consumers on exact candidate03184a6. These are candidate
receipts, not Qualification of a later main/release SHA. Target version, final
Qualification and publication remain separate Human decisions and were not
started by main adoption. Published v0.5.3 below does not include this work.

## Current published release: v0.5.3 — Reuse successful macOS platform checks

[v0.5.3](https://github.com/masahitojp/mariamem/releases/tag/v0.5.3) was published
on 2026-10-18 (JST) from source `4f7b18bfc00965974fcbb16ac49cbf00d9fb2b0e`.
[Release CI 39115376954](https://github.com/masahitojp/mariamem/actions/runs/39115376954)
completed independent guest builds/generated-Go reproduction, both-platform
acceptance, aggregate guard, publication and public Go/wheel smoke successfully.
The product runtime change since v0.5.2 is the macOS platform-check success
cache (`internal/artifacts/platform_cache.go`). Public APIs, guest and Snapshot
ownership remain unchanged. See [release notes](../release/NOTES-v0.5.3.md).
The macOS product comparison against v0.5.2 remains on
`experiment/product-main-macos` at `94f13e6`; integrating that measurement report
is a separate decision. v0.6 planning follows this published boundary.

## Previous release: v0.5.2 — Snapshot ownership without repeated content scans

[v0.5.2](https://github.com/masahitojp/mariamem/releases/tag/v0.5.2) was published
on 2026-10-17 (JST) from source `47f297cc7498625e076abb93322eb616c9560bb8`;
annotated tag object `2e98dee0ca94abe95dcef8351b71f7726320bf12`.
It seals the source's same private backing instead of reconstructing the ordinary
heap baseline and repeatedly reading all file contents, reducing Snapshot
creation work. Public Go/Python API signatures, MariaDB 12.3.3, supported
platforms and minimum Go version are unchanged from v0.5.1. Ordinary heap
acquisition no longer performs a full content scan to detect faults that directly
alter private bytes between freezing and acquisition; it validates identity,
state and structure instead, while strict digest-bearing imports, cross-host
transfer and borrowed-mapping lifetime detachment retain their content checks.
See [released notes](../release/NOTES-v0.5.2.md) and
[changes since v0.5.1](changes-since-v051.md). The adoption history below records
the main integration that preceded this release.

## Previous release: v0.5.1 — In-memory baselines and shared host

[v0.5.1](https://github.com/masahitojp/mariamem/releases/tag/v0.5.1) was published
on 2026-10-17 (JST) from source `7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`;
annotated tag object `089b32e09608902f6d46e7ab9527d09922dcf065`.
The [typed baseline pin](../release/baselines/v0.5.1.json) separates these identities.
It includes the startup ordering correction, D block backing, Python shared host
and public save/load API removal. See [released notes](../release/NOTES-v0.5.1.md)
and [API migration](changes-since-v050.md). The ownership optimization recorded
below was subsequently released in v0.5.2; v0.5.1 evidence does not qualify it.

## Previous release: v0.5.0 — MariaDB 12.3.3

[v0.5.0](https://github.com/masahitojp/mariamem/releases/tag/v0.5.0) was published
on 2026-10-13 from source `44100ec676c8c9064f32f3a01bd9a990d487bb61`;
annotated tag object `bfd854da1cecbe71ad761d1578b3f2c710a1c07f`.
It adopts MariaDB 12.3.3, dynamic handshake version and the bounded correctness
repairs. Its public Go/Python APIs and file-backed Snapshot persistence were
retained. See the [released notes](../release/NOTES-v0.5.0.md).

The startup ordering correction, D block backing, Python shared host and public
save/load API removal were subsequently released in v0.5.1. The earlier v0.5.0
preparation history below does not qualify later main commits.

## Adopted ownership optimization — released in v0.5.2

On 2026-10-17 the maintainer explicitly accepted the limited Snapshot ownership
contract and authorized the minimal FileStore/Root/capture-binding implementation,
adapters, independent byte reference/substitution/lifetime/generation tests.
Normal API immutability, same backing, child isolation, strict Heap/transfer
validation and mapped lifetime detachment remain required. Ordinary heap
acquisition does not promise full-scan post hoc detection of private-byte faults.
The maintainer subsequently approved main integration in Human Review.
The separate release decision followed and published the optimization as v0.5.2
above. See the [contract](decisions/snapshot-product-contract.md) and
[productization report](reviews/snapshot-owned-root-productization.md).
The experiment history is not merged into this branch. Productization development
verification passed on exact source `890f770eee36c004036826104229f9269138775b`
for macOS15 arm64 and Ubuntu24.04 x86_64 in
[run39000948512](https://github.com/masahitojp/mariamem/actions/runs/39000948512):
canonical check and integration on both, including the mapped-child derived baseline.
After the [integration review](reviews/snapshot-owned-root-productization.md),
the Human approved the fixed candidate. Main was fast-forwarded from
`7a82f338cf111d5d52538b5a3f7bf129c12e2dbb` to
`52c078ba2fd5a38340ec5eb42a83853b258d7435`, with Git tree object ID
`02da8809cd9aa76ff3769af268134b90675a68a7`. The review-only head was not merged.
The [integration identity record](reviews/snapshot-owned-root-productization-evidence/integration-target.json)
pins that candidate's commit and tree, the CI source it builds on and the exact
difference set. Relative to CI source 890f770, that candidate changes
documentation/evidence and Go line comments only (four Go files); executable
behavior, tests and build inputs are unchanged. This follow-up records adoption,
corrects the published-release status and stale architecture/Acquire wording
without changing executable code, and adds one more comment-only Go file
(`internal/snapshot/owned.go`); the current runtime source therefore differs from
CI source in five comment-only files. The full Git tree differs from both the
integration candidate and CI source. Historical review/CI evidence remains under
its original source identity.
The v0.5.1 baseline pin is retained as a separate release ledger entry.
The narrowed detection guarantee recorded in [changes since v0.5.1](changes-since-v051.md)
is published in the v0.5.2 notes above. Prior Qualification and spike
regeneration results are not relabelled as the final v0.5.2 source. Release
Qualification and independent regeneration for the exact final source were
CI-owned and separate; the CI development PASS recorded here is not itself
release readiness.

**Snapshot optimization stopping point:** the observed Light Snapshot median
fell from 204.8ms on v0.5.1 to 2.85ms on the ownership candidate in the same
macOS comparison. No further Snapshot speed optimization is planned.
This is an investment decision for the measured workflow, not a claim of a
universal lower bound. Remaining Light serial time is mostly child startup/use:
child Fork median 59.4ms (40 child observations), 4-test total median 364.0ms.
The approximately 3.08ms diagnostic capture is from the candidate, not v0.5.1;
measured/diagnostic cohorts are not combined. These medians are quoted from the
adoption-source macOS measurements and remain macOS investment figures, not a
cross-platform lower bound. The separately authorized
[native Ubuntu campaign](reviews/ubuntu-product-performance-results.md), now
integrated on main, independently confirmed the Snapshot gain on Ubuntu x86_64
and recorded the mixed large-Python whole-workflow results.

## Previous release: v0.4.7 — Upstream converter migration

[v0.4.7](https://github.com/masahitojp/mariamem/releases/tag/v0.4.7) was published
on 2026-10-11 from source `e0be06f3a20c72cbb5a9be27971280c80a3ec357`;
annotated tag object `c201bf577440440253155e665def9c25ac5064f0`.
It adopts pinned goccy/wasm2go plus nine maintained patches on the unchanged
13.1.0 guest. Its published source is the A–D execution baseline; the former
candidate notes below preserve preparation scope. A–D changes were unqualified at that stage; later Qualification and
Product Verification are recorded below.

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

In that released file-backed implementation, creation/import validates the complete Snapshot, then mariamem owns the exact
backing used by Fork. Supported operations do not mutate it. Fork does not fully
rehash content; silent storage corruption arising after ownership is not promised
to be re-detected on each Fork. External source edits/deletion after import do
not affect the owned baseline. Live Snapshots retain one FD per prepared file.
Python uses `snapshot()`, `snapshot_to(path)`, `load_snapshot(path)` and `fork()`.
See the [then-current contract](https://github.com/masahitojp/mariamem/blob/v0.4.4/docs/decisions/snapshot-product-contract.md),
[implementation review](reviews/v044-implementation-review.md),
[architecture](v04-generated-go-architecture.md) and
[release notes](../release/NOTES-v0.4.4.md).

Generated-Go is the only supported production runtime since v0.4.3. Snapshot is
cold prepared state; Fork starts fresh MariaDB execution rather than cloning
running heap/threads/TLS/locks/stacks. The file-backed release used private
mappings and OS page CoW; main now uses immutable blocks and private changes.
Historical measurements and release repairs remain evidence, not instructions
for the current user lifecycle.
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
  checks do not prove general race correctness. The census is complete for its
  old pinned inputs. The [post-v0.5 evidence reconciliation](reviews/shared-memory-post-v05-reassessment.md)
  distinguishes the later R1–R5 investigation and repairs from a new census or
  general shared-memory model; those scopes must not be counted as one task.
  The [scalar/SIMD static follow-up](reviews/shared-memory-scalar-simd-reassessment.md)
  records 36 historical signatures and current candidate access sites. It identifies
  a concrete purge-state protection question and proposes a bounded original-Wasm/Go
  comparison for Human Review. No new execution or runtime fix is included, and
  candidate-site correspondence is not a complete semantic or exact-PC proof.
  The Human then approved that bounded purge head/view comparison and accepted its
  [macOS fixture result](https://github.com/masahitojp/mariamem/blob/424172f017a0ec42c01407300f08411e9d480348/docs/reviews/purge-wasm-go-comparison.md):
  torn Go heads occur inside the Wasm-permitted set (0 forbidden observations
  across 10,980,000 reads), and no mixing occurs under the common-lock or
  completed-handoff controls. This is not grounds for a Go-conversion fix. The
  purge-specific protection premise (reader `purge_sys.latch` vs writer
  `end_latch`) remains unverified. The Human accepted it as a stated limitation
  on 2026-10-17 and did not authorize a real-guest order observation; it is not
  established as harmless. Ubuntu x86_64 was not executed, and no runtime change
  follows. This is not a general shared-memory guarantee.
- Forced timeout/hard-failure containment is not guaranteed. Normal cooperative
  cleanup and non-cooperative reclaim are distinct boundaries.
- v0.5.0 had an observed approximately one-second startup mode. The
  [page-cleaner source correction](reviews/v050-startup-tail-source-fix-integration.md)
  is released in v0.5.1 and retained in v0.5.2, after bounded Fresh comparisons
  and related regression passed on both native platforms. The exact final source
  that contains it, `7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`, passed
  [v0.5.1 Release CI](https://github.com/masahitojp/mariamem/actions/runs/38959312232),
  so the earlier pending exact-final-source validation is satisfied. This does
  not establish a universal latency bound.
- External consumer checks passed on macOS arm64 with Go 1.26.8 and
  1.27.0/1.27.1/1.27.2. See [compatibility](go-compatibility.md); minimum Go
  and driver versions are unchanged.
- Physical footprint, RSS and reachable heap are different resource measures.
  The v0.4.2 lifecycle releases linear memory after joined workers; filesystem
  metadata remains GC-managed.
- Published file-backed Snapshots retain roughly one FD per prepared file.
  The adopted D memory path removes this ordinary backing-FD requirement;
  both-native verification is recorded above. The historical 64-table fixture
  had 137 files and released its backing FDs after Close on both platforms.
  Many simultaneously retained baselines, especially file-heavy schemas, may
  approach process FD limits. The Human decision places that observation in the
  v0.6.0 dogfood scope below: gather real workload evidence there and improve
  the resource model only if pressure is demonstrated. This item is therefore
  out of 0.5.x; it is not an approved 0.5.x task and not a reason by itself to
  create another 0.5.x patch release.
- The 0.x API may change. Corresponding guest source, licenses, notices and
  reproducible generation remain required.

## Performance evidence and pending optimization questions

**Moved to v0.6.x dogfood: per-DB connection-count tuning.** The current contract
keeps a fixed 16-connection limit per DB. The Human placed connection-count
optimization in the 0.5.x scope on 2026-10-17; on 2026-10-18 the Human moved it to
v0.6.x so that actual demand and resource effect are confirmed during dogfood
before changing the limit. This is distinct from the FD/resource-model pressure
observation, also assigned to v0.6.0 dogfood above. The current active and closed
items are listed in the [v0.5.x remaining-item snapshot](reviews/v05x-remaining-items.md).

**Evidence reuse scope — assessment accepted, expansion deferred (2026-10-18).**
The Human approved the [limited dependency/rejection-condition assessment](reviews/runtime-evidence-trust-scope-plan.md),
including a timing check of the previous long verify/release runs. The
[results](reviews/runtime-evidence-trust-scope-results.md) distinguish runtime
dependencies from qualification's benchmark test/vet and source inventories.
The prior approximately 91-minute verify and 94-minute release used different
source commits/versions; their intervening paths were already permitted by the
current path/version comparison, but no authenticated reusable runtime intent
connected them. Exact-SHA READY reuse also could not bridge different commits.
The recommendation is to retain current reuse rules and use the existing
one-shot release, or verify the final versioned candidate and release the same
SHA. No new exclusions or runtime/workflow changes were implemented. The Human
accepted deferring the wider redesign on 2026-10-18. This closes the bounded
assessment and removes scope expansion from active v0.5.x work; it does not
establish a new reuse contract. Revisit if benchmark-only changes repeatedly
block otherwise eligible evidence reuse. The Human separately approved main
integration of the assessment, evidence and acceptance records on 2026-10-18;
source `779ad55babaef2fab6875846e63d2d984f5a16d8` was fast-forwarded without
runtime, verifier or workflow changes. Any actual release remains a separate decision.

**Child Fork startup and child Close attribution — accepted 2026-10-18.** The
[bounded attribution](https://github.com/masahitojp/mariamem/blob/bbf5d1c27f3cea3e2135e8fae053f875ceb234b5/docs/reviews/child-lifecycle-attribution.md)
completed 40 fixed executions on each native platform (macOS local; Ubuntu source
`e4a5522ca475f73b56f23b08a725354eafb81b19` in
[run 39083277771](https://github.com/masahitojp/mariamem/actions/runs/39083277771),
artifact identity and all cells/traces/aggregates independently reconciled).
Guest server initialization dominates Fork on both platforms; the repeated OS
check adds material cost only on macOS. Actual DB Close is separate from SQL
disconnect waiting and is mainly guest shutdown and linear memory release.
Investigation #2 met its exit criteria and the Human accepted it on 2026-10-18.
Acceptance does not itself approve an optimization or main integration.

**Human-approved child-lifecycle optimization scope — 2026-10-18 (order
revised 2026-10-18):** for this workstream, v0.5.x is limited to these two
actions, in order:
1. Implement and measure reuse of successful macOS platform checks, preserving
   unsupported-platform rejection, cancellation/failure behavior and concurrent
   startup correctness. Keep DB internals unchanged. Implemented, verified and
   accepted for main integration on 2026-10-18.
2. Then investigate Ubuntu 10MiB parallel startup: distinguish startup
   contention from overlap with other children’s SQL/cleanup and identify the
   principal cause. Observed guest open-to-ready is 65.84ms serial versus
   133.95ms with four workers (60.62ms is the different Light case). Compare
   per-child latency and whole-suite elapsed time. This bounded investigation
   also supplies measurement evidence for the v0.7.x selection; it does not
   authorize guest-initialization optimization implementation.

Guest-initialization improvement candidate selection is scheduled for v0.7.x,
using the investigation evidence; it is not a v0.5.x task. Main integration and
release remain separate decisions. The Human approved the
[success-cache design](reviews/macos-platform-cache-design.md) for implementation
and bounded measurement on 2026-10-18, with review gaps to close first. The
[implemented candidate and bounded macOS results](reviews/macos-platform-cache-results.md)
record passing unit/race and lifecycle checks, 32 measured executions, faster
subsequent Forks and child-suite medians, plus initial-Python/parallel-Close
uncertainty. Native focused CI passed on exact source dc183e438a65c13aa532e16e38e31e3378d0a1dd
in [run39091145992](https://github.com/masahitojp/mariamem/actions/runs/39091145992);
both artifact digests, source receipts and focused logs were reconciled. The
Human approved main adoption/integration on 2026-10-18. Canonical
`scripts/verify.py integration` now includes `./internal/artifacts` in its race
set, so main CI retains the new concurrency oracles on native macOS. Product
runtime matches the reviewed CI source; this follow-up adds CI wiring and
adoption records. The first main Development CI passed check and all race
packages, but its integration job hit the 15-minute job limit before completing
later acceptance. Following Human approval, the job budget is 30 minutes with
individual test deadlines unchanged. The manual full-development
[run39094406383](https://github.com/masahitojp/mariamem/actions/runs/39094406383)
passed scope, full check and canonical integration on exact source
`8907a4e19da104fd9cd110a91e36543097e43ba4`; the artifacts race set, later Go
acceptance, Python18 tests and Snapshot33 checks completed. This closes the
post-integration development check, not release qualification. The linked
results retain the original timeout and the successful rerun. Release remains
a separate decision. Item 2 completed its bounded measurements on the isolated
[Ubuntu parallel-startup study](reviews/ubuntu-parallel-startup-study.md):
matched serial/pipeline/barrier conditions plus separate bounded diagnostics.
[run39099563649](https://github.com/masahitojp/mariamem/actions/runs/39099563649)
passed all 32 executions on source `4e73abe126672869ad03575e84706b5ab2cb557c`.
The [result and Human Review](reviews/ubuntu-parallel-startup-results.md) finds
that preventing early SQL/Close overlap does not remove slower per-child Forks;
startup execution-resource sharing is the main supported cause category.
Ordinary process-level medians are 43.50ms serial versus 84.03ms parallel per
child, while four-child elapsed time improves from 541.23ms to 263.47ms.
CPU scheduling versus cache/bandwidth contributions remain unseparated; a slow
post-ready SQL trial is retained separately. The Human accepted the bounded
investigation results on 2026-10-18 after clarification of the GOMAXPROCS
diagnostics. Keep automatic GOMAXPROCS selection: 4 was fastest among the
tested 1/2/4 settings and also matched the native default; no better setting
has been demonstrated. This closes item 2a, not the unseparated mechanisms.
The result acceptance did not authorize guest optimization or main integration.
The Human separately approved main integration on 2026-10-18. Integrate the
measurement harness/workflow, compact evidence and reports from
`791108e` as one commit; product runtime, guest, generated sources and public
contracts remain unchanged. The successful native campaign binds to the original
measured source above, not to a claim of rerunning it on the integration commit.
Guest-initialization candidate selection remains scheduled for v0.7.x.
Other previously recorded roadmap items are not cancelled by
this workstream decision.

The Human prioritized native Ubuntu performance measurement next. The
[fixed-scope campaign](reviews/ubuntu-product-performance.md) completed 246
executions on the released v0.5.0/v0.5.1/v0.5.2 inputs in
[run 39073990176](https://github.com/masahitojp/mariamem/actions/runs/39073990176).
The [result review](reviews/ubuntu-product-performance-results.md) reconciles
all cells and identities: Snapshot gains also appear on Ubuntu, while large
Python whole-workflow results remain mixed. The Human accepted these results
on 2026-10-18, closing this performance check. The large Python regressions and
their unresolved cause remain recorded. Acceptance does not reopen the closed
100 MiB Go Fresh investigation or authorize additional cause profiling, main
integration, runtime changes, Qualification or publication.
The Human separately authorized main integration and push on 2026-10-18.
The integrated scope is measurement tooling, preserved evidence and documentation;
no runtime change or further measurement is included.

**Closed until recurrence: 100 MiB Go Fresh.** The
[completed paired comparison](../benchmarks/main-product-verification.md#adverse-100-mib-go-case-and-bounded-repeat)
retains the original +29.0% wall-time trial, the three additional pairs (+1.9%
median), and all four observations (+7.2% wall / +6.3% CPU median). Preparation
and SQL account for the adverse intervals; storage overhead versus execution
conditions remains unresolved. The maintainer accepted this tradeoff for
v0.5.1; it was not an additional release gate. The subsequent bounded
[released-source investigation](https://github.com/masahitojp/mariamem/blob/7068dd045f10c2772535fccca73c040c387e5b0b/docs/reviews/go-large-fresh-investigation.md)
and [allocation attribution](https://github.com/masahitojp/mariamem/blob/7068dd045f10c2772535fccca73c040c387e5b0b/docs/reviews/go-heap-reuse-attribution.md)
are complete on `experiment/go-large-fresh`; their experiment history is not merged.
The additional runs did not reproduce persistent Fresh slowdown. The original
slow trial's cause and the allocation origin of heap-reuse CPU remain unresolved.
The original Human decision to close the investigation on 2026-10-17 is recorded
in `7068dd045f10c2772535fccca73c040c387e5b0b`.
Reopen only if similar slowdown recurs in normal use or
measurement, using the saved evidence. Further profiling or runtime repair is
not pending approved work; do not start additional measurements while waiting
for recurrence, call the old result noise, or claim the cause was fixed.

Current storage routing follows the adopted D/shared-host contract and
[implementation/adoption report](reviews/d-heap-shared-host.md) above. The v0.4.x
decision and research handoff below record earlier investigation context; their
retain-MAP_PRIVATE and unperformed-measurement statements are not the current
implementation or instructions to restart that work.

The [Go 1.26.8 / 1.27.2 comparison](benchmarks/go126-vs-go127.md) retains
same-source macOS arm64 suite/resource results and reproduction evidence.
No consistent practical speedup was demonstrated; these observations do not
change the supported toolchain policy or qualify the current main SHA.

The [memfs Architecture Decision](reviews/memfs-architecture-decision.md) was the
v0.4.x routing reference: retain memfs + MAP_PRIVATE pending limited measurement,
and defer broader replacement. The D adoption above supersedes that storage
choice. Its [memfs/pglite](reviews/memfs-optimization-discovery.md),
[pgmem](reviews/pgmem-vfs-design-review.md) and
[block-storage](reviews/block-storage-design-discovery.md) reports are historical
inputs with pinned source hashes. The observed ~4.62 GiB is cumulative allocation
across 20 Fresh DBs including fixture work; it is not retained memory or an
estimate of removable allocation. The [benchmark index](../benchmarks/README.md)
already owns measurement navigation; no duplicate report is introduced.

### Historical research handoff — before D/shared-host adoption

The following paragraphs preserve the scope handed off before the later storage
exploration and implementation. Their prospective language describes that stage,
not today's remaining tasks. Current remaining work is recorded in the adoption
report and the published-release/main distinction above.

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

**Snapshot direct-copy — Human decision, 2026-10-14:** the maintainer accepted
stopping this investigation and its spikes at the present stage, retaining the
current product implementation and deferring adoption of the prototype. The
approved local spike and eight-run follow-up are complete; no further measurement,
cause investigation or prototype work continues automatically. Resuming this
specific optimization requires a new agreed scope and exit conditions.

The [completed follow-up and evidence](https://github.com/masahitojp/mariamem/blob/b6d371232f613425b066049bb3e6f873cfee4e37/docs/reviews/snapshot-direct-copy-recheck.md)
record a roughly 0.43-second Snapshot saving and approximately 264 MiB less
cumulative allocation on macOS arm64, but mixed 100 MiB / 16-Fork whole-suite
results: ordinary timing 2.2% slower, resource-observed timing 2.9% faster.
Extra child-phase GC recurred; changed allocation/GC pacing remains a hypothesis,
not an established cause of delay. This decision defers the current prototype
without rejecting direct copying in general. Runtime source remains isolated on
`experiment/snapshot-direct-copy`; its ownership/failure tests, raw measurements
and reproduction scripts are preserved in the linked reports. Disposable build
and measurement state has been cleaned. No release decision follows.

**Storage documentation after main adoption — 2026-10-17:** use the Product
contract and adoption report for current behavior, validation and remaining work.
The following older materials have distinct roles; none starts another experiment.

| Material | Continuing use |
| --- | --- |
| [Storage design map](reviews/storage-design-directions.md) | Reference for A–F alternatives, product value and reference-project differences. Historical assumptions are labelled; D/shared-host is now adopted. |
| [D productization design](reviews/d-heap-productization-design.md) | Approved design/scope-change history supporting the implementation. The older local draft lacking the save/load removal decision was redundant and removed. |
| [Direct-copy investment reassessment](reviews/storage-investment-reassessment.md) | Archived reasoning and measurements from the earlier comparison. Its pending-decision wording, four-hour proposal and estimates are not current tasks. |

The 2026-10-15 exploration preserved library convenience and independent real
DBs while reopening storage/clone methods. That direction led to the D/shared-host
adoption; it no longer represents an unselected backend or pending Human Review.

## v0.4.7 — Upstream converter migration (candidate)

The released scope replaces the pinned shibukawa converter fork with pinned
`goccy/wasm2go` plus nine maintained patches. MariaDB guest identity, public APIs,
Snapshot format and minimum Go version remain unchanged from v0.4.6. Independent
regeneration, runtime/consumer checks and same-scenario product/resource comparisons
must precede the Human release decision. Native macOS/Ubuntu artifact qualification
remains CI-owned. No guest upgrade, handshake experiment or VFS optimization is
part of v0.4.7. Historical candidate measurements qualify only their recorded inputs.

## v0.5.0 — Stable guest preparation history

This release is now published; its final source/tag identity is recorded above.
The following records the successive preparation inputs and decisions at the
time. Statements that a branch was unqualified or a decision was pending refer
to that historical stage, not a new outstanding correction or release gate.

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
The [Human Review](reviews/v050-human-review.md) recommends adoption. The
maintainer accepted that recommendation and authorized v0.5.0 release submission;
Release CI must qualify the final integrated source before publication.

The maintainer authorized the limited J1 completion/reclamation repair after the
paired counterexample. The [implemented candidate](reviews/v050-join-lifetime-fix.md)
binds worker map reclamation to final agent access, covering delayed wake,
detached self-exit and unwind. Guest/raw converter inputs remain unchanged;
owned generated edits are independently reproduced. T1/T2/J1 close the identified
corrective items in the agreed current-guest investigation. Candidate adoption and Qualification were separate from the subsequent release
authorization, as recorded in the [Human Review](reviews/v050-human-review.md).

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
does not qualify the new macOS-only protocol fixtures. At that stage the branch work did not qualify main or establish general
shared-memory correctness. The later Qualification and Product Verification are
recorded above. The roadmap below retains its historical scope.

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

These earlier A–D checks alone did not qualify a release. Their follow-up
correctness work, both-native Qualification and Product Verification are linked
above. Full shared-memory race census and startup-tail improvements remain
separate work; no general performance improvement is claimed.

## v0.6.0 — Dogfood and fixture ergonomics

**North-star discussion recorded with the Human, 2026-10-18:** reduce the work
of establishing and growing database tests in both new applications and existing
systems without tests, so developers can focus on features and their behavior.
Aim for use without learning special conventions (for example, one added line
redirecting existing connections), understandable import of existing preparation
data, independent reusable test workflows across frameworks, accessible official
MariaDB compatibility references, and failures that explain the known context
and next action to humans and coding assistants. Evaluate first-test setup,
next-test authoring and execution time separately. The intended niche is a
Docker-free library that reduces environment setup, test-authoring and cleanup
work compared with assembling a container-based workflow. This is not a claim
of universal superiority over Testcontainers: existing container infrastructure
or a need for exact production MySQL behavior may favor that approach. See
[the north star, principles and objections](reviews/v06x-kickoff-notes.md#11-north-star-and-capability-coverage-matrix-ideal-driven).
This records product intent, not current support or implementation approval.
Enumerate the capability space before choosing representative tests; tests
prioritize gaps rather than define the whole scope. Version-specific acceptance
and any public-contract changes still require their own decision.

The [v0.6 capability map](reviews/v06x-capability-map.md) expands that intent into
existing foundations, gaps, unverified coverage and dependencies. It proposes
connected designs for entry/routing/lifecycle, preparation/import and
compatibility/actionable failures. The Human agreed to this planning direction
on 2026-10-18; implementation scope and API choices are not yet approved.
All capability axes remain visible before selecting tests.
The [connected workflow design options](reviews/v06x-workflow-design-options.md)
compare connection injection/adapters/interception, preparation paths and
actionable diagnostics under one lifecycle. The Human approved this comparative
design direction on 2026-10-18; source investigation proceeds with the existing
Snapshot contract in the cross-check basis. Mechanisms remain alternatives,
not approved implementations.
The [first routing/preparation source findings](reviews/v06x-routing-source-findings.md)
pin the pgmem reference and distinguish new, idle-pooled and active connections,
including the different scope of its Python and Go helpers. The
[MySQL workflow continuation](reviews/v06x-mysql-workflow-source-review.md) records
pinned driver/framework seams, concrete upstream dump/migration input inventory,
and diagnostic/official-reference requirements. Source investigation now supports
a bounded prototype proposal; runtime validation, mechanism selection and broader
driver coverage remain unfinished. No routing compatibility support is established by that source investigation.

**Prepared Statements — implementation approved, in progress.** Python
`cursor(prepared=True)` and Go explicit DB/Tx/Conn Prepare remain required for the
one-line-switching goal; interpolation or application SQL changes are not a
substitute. The original [prepared alternatives/spike decision](reviews/v06x-prepared-design.md)
led to the [positive feasibility result](https://github.com/masahitojp/mariamem/blob/9250ff5/docs/reviews/v06x-prepared-multi-spike.md)
with the public embedded mysql_stmt APIs, default multi-statement capabilities
and Connector/Python26.7.0. That experimental prepared implementation is not
adopted; its fixed capacities, incomplete type/result codec and named consumer
error/import differences remain explicit.

Main now supplies routine bootstrap, text multiple results and COM_SET_OPTION;
those prerequisites are complete, not work to repeat. The
[prepared production design](reviews/v06x-prepared-product-design.md) proposes a
separate versioned guest path, typed dynamic buffers, prepared CALL multiple
results, no-response lifecycle and finite P1–P6 acceptance. It distinguishes the
native-parity C-extension syntax-error exception proposal from the unchanged
original1064 FAIL. The Human approved production implementation after that design review.
[Staged implementation](reviews/v06x-prepared-implementation.md) has P1 owners,
protocol, lifecycle dispatch and unit coverage. Its source compilation and
both-OS unit CI passed; expanded native12.3.3 PREPARE controls passed. The subsequent
development gate passed the new-guest smoke and exact installed binding checks
on both OSes. Its actual wire/native metadata comparison exposed a C API numeric
flag leaking onto the wire; the host-serializer repair passed the corrected
[both-OS gate39540250744](https://github.com/masahitojp/mariamem/actions/runs/39540250744)
at3496095, including actual P1 lifecycle and native metadata equivalence.
P2 typed-value/client decoder and binary-row components passed both-OS units in
[CI39548803322](https://github.com/masahitojp/mariamem/actions/runs/39548803322)
at0ceca7c. EXECUTE source compilation and both-OS units passed in
[CI39554451701](https://github.com/masahitojp/mariamem/actions/runs/39554451701)
at00962f8; that run intentionally skipped development runtime execution.
The new guest has now been translated with the fixed converter/13 patches and
its three allocation/lifetime functions and TLS data reviewed for a single exact
binding. [Binding evidence](reviews/v06x-prepared-p2-binding-evidence/reproduce.md)
records50 local input/guard checks PASS. The first full P2 development gate
[39561037019](https://github.com/masahitojp/mariamem/actions/runs/39561037019)
passed generation/compile/SQL smoke and exact installed bindings on both OSes,
but a new mutation test changed an earlier unrelated literal instead of its
target function. The [test-only repair](reviews/v06x-prepared-p2-mutation-fix/receipt.json)
scopes the mutation to that function and passes12 focused checks, including an
earlier-same-literal regression. The corrected
[gate39565377640](https://github.com/masahitojp/mariamem/actions/runs/39565377640)
passed those12 mutations and actual P1 comparison on both OSes. Actual P2
comparison now exposes one TIME column-length difference (16 vs native23), with
all22 cases' binary rows/terminals matching. The [bounded internal-source proposal](reviews/v06x-prepared-p2-time-metadata.md)
was approved by the Human on2026-10-21 after the upstream-history investigation.
The2011 change redefined MAX_TIME_WIDTH23→16 while the embedded call retained
that name; the ordinary call switched to the newly introduced full-width23
constant. The one-line repair is now staged only in guest/experimental.patch
with complete source pre/postimage and patch hashes. [Repair evidence](reviews/v06x-prepared-p2-time-repair/receipt.json)
records61 local checks and13 additional native TIME cases PASS, plus an unchanged
22-case native replay. [Source preflight39572844101](https://github.com/masahitojp/mariamem/actions/runs/39572844101)
passed source and both-OS units at4f41be8. The patched guest's exact allocation/
lifetime bodies, full data and TLS match the previous reviewed output; only
one raw generated part changes. [TIME binding evidence](reviews/v06x-prepared-p2-time-binding/receipt.json)
records the new single identity and62 local checks PASS. The full
[gate39577305621](https://github.com/masahitojp/mariamem/actions/runs/39577305621)
atf498396 passed all5 jobs. [Result evidence](reviews/v06x-prepared-p2-time-result/receipt.json)
confirms actual P1, original22-case P2 and extra13-case TIME/native comparison
PASS on macOS arm64 and Ubuntu x86_64, plus smoke and13 binding tests per OS.
The bounded TIME repair is verified for that matrix. The
[additional P2 matrix](reviews/v06x-prepared-p2-matrix.md) now defines20 independent
DML/warnings/schema-reprepare/type/SQL-mode controls, all PASS against fixed
native12.3.3. Actual [gate39582653522](https://github.com/masahitojp/mariamem/actions/runs/39582653522)
passed original probes on both OSes but exposed a BIT16 timeout/DB termination;
only the first2 scenarios matched, while the next17 were not independently
assessed after that shared DB died. The [test-isolation repair](reviews/v06x-prepared-p2-isolation-evidence/receipt.json)
uses a fresh root DB/host for each of the same20 scenarios and captures logs/
teardown errors;6 local controls PASS. The isolated
[gate39585983268](https://github.com/masahitojp/mariamem/actions/runs/39585983268)
atd11f4ff independently matches12 scenarios on both OSes and fails8: seven raw
parameter type inputs time out; schema-add returns2057 and leaves following SQL
out of sync. Previous P1/original22/TIME13 and smoke/binding gates still PASS.
[Failure assessment and bounded repair proposal](reviews/v06x-prepared-p2-blockers.md)
preserve exact captures and separate observed harm from source inference.
The Human approved the bounded two-part repair continuation. The
[source candidate](reviews/v06x-prepared-p2-repair.md) preserves raw parameter
types and rebuilds changed result metadata without SQL retry. Its91 focused
macOS component checks and15 added fixed-native controls PASS. The
[source preflight39596726209](https://github.com/masahitojp/mariamem/actions/runs/39596726209)
passes source/both-OS units at68fb5c2. The
[new guest binding review](reviews/v06x-prepared-p2-repair-binding/reproduce.md)
verifies guest41ab4076 through the fixed converter/13 patches: all3 lifetime
function bodies, full data and TLS match the previous guest; memory initialization
is checked/pinned too. Local94 checks PASS.
[CI39601636017](https://github.com/masahitojp/mariamem/actions/runs/39601636017)
passes installed bindings/smoke/P1/22/TIME13/additional20 on both OSes; those former
eight failures no longer reproduce. The final15-case gate fails seven unsigned
NULL metadata cases, with values/termination/following SQL matching. The
[parameter-order continuation](reviews/v06x-prepared-param-order.md) fixes the
descriptor assignment before conversion/NULL handling in both embedded paths,
within the approved binding scope. Local102 checks and extra2 native controls
PASS. [Source CI39607505031](https://github.com/masahitojp/mariamem/actions/runs/39607505031)
passes guest-source and both-OS units at a342f30. The
[parameter-order binding review](reviews/v06x-prepared-param-order-binding/reproduce.md)
verifies new guest4dad84d0 with unchanged converter/13 patches, full lifetime
bodies, data/TLS and memory initialization; local103 checks PASS. Both-OS actual
runtime/native confirmation now [PASSes at5146d8a](reviews/v06x-prepared-p2-pass.md)
in [CI39616628715](https://github.com/masahitojp/mariamem/actions/runs/39616628715):
all72 typed scenarios per OS, P1, smoke and17 installed binding mutation tests.
The specified P2 development acceptance row is satisfied; P3–P6 and full
production acceptance remain unfinished. The [minimal P3 source candidate](reviews/v06x-prepared-call-minimal.md) now adds
owned binary result chains and an OUT+two-results native reference. Local106
Python/C checks, three Go race packages and native replay PASS.
[Source preflight39624071363](https://github.com/masahitojp/mariamem/actions/runs/39624071363)
passes guest-source and both-OS units at46f5c2c. The
[P3 binding review](reviews/v06x-prepared-call-binding/reproduce.md) records new
gueste6d6021a, its64-byte data/BSS layout shift, exact complete functions/init,
unchanged TLS content and107 local ownership checks PASS. Only that new guest
is accepted. [CI39631360824](https://github.com/masahitojp/mariamem/actions/runs/39631360824)
now [passes the minimal CALL](reviews/v06x-prepared-call-pass.md) on both OSes at42be2b5,
including exact native metadata/rows/status, OUT, terminal OK, following SQL and
Close/PING. P1/all72 P2 controls and18 installed mutations also PASS per OS.
The minimal P3 feasibility gate is closed. The [full P3 candidate](reviews/v06x-prepared-p3-matrix.md)
then matches11/13 baseline cases and exposes two unnegotiated-OUT differences.
A bounded Go bridge negotiation fix now passes all14 native/guest cases on macOS,
including paired flag states and advertisement; P1/all72 P2 and smoke remain PASS.
Local112 Python/C and3 non-race Go package checks PASS. Fresh exact-candidate
[CI39686154515](https://github.com/masahitojp/mariamem/actions/runs/39686154515)
now [passes the full P3 row on both OSes](reviews/v06x-prepared-p3-pass.md)
at6fc594a: all14 cases match native, negotiated capability states and following
QUERY/CLOSE/PING PASS, and previous P1/all72 P2 controls, smoke,112 Python/C
checks, three Go race packages and18 installed mutations PASS per OS.
P3 development acceptance is complete; P4–P6 and production acceptance remain unfinished.
The [first P4 lifetime slice](reviews/v06x-prepared-p4-lifetime.md) adds native-controlled
Go DB/Tx/Conn/pool, RESET/transaction/type reuse, malformed lifecycle adjacency,
engine quota recovery and idle QUIT/EOF cleanup. Native capture/replay7/7 and
local114 Python/C plus3 Go race packages PASS. A bounded handwritten-host
CLOSE/RESET length repair leaves guest/converter/generated identities unchanged.
[CI39699613828](https://github.com/masahitojp/mariamem/actions/runs/39699613828)
now confirms all7 cases on both OSes at ecfea4a with no native differences:
active connections return0, temporary directories are removed, and the Go
consumer restores native statement counts/open connections to0. P1/all72 P2/
all14 P3/minimal CALL, smoke,114 Python/C checks,3 Go race packages and18 binding
mutations also PASS per OS. The first lifetime slice is complete. LONG_DATA,
executing-query cancellation/disconnect and the remaining resource/failure
matrix are still P4 work; this first slice does not close or narrow P4.
The [LONG_DATA source candidate](reviews/v06x-prepared-long-data.md) now forwards
chunks to the public embedded API, retains only parameter-presence/deferred-error
state in the bridge, and adds omission/NULL/type reuse plus reset/close handling.
Native25-case capture/replay PASS, including1MiB aggregate crossing, index64 and
native1105 capacity/error recovery. Local118 Python/C checks and3 Go race
packages PASS. Source CI39714836816 passes guest build and both-OS units at425c821.
The [exact new guest binding](reviews/v06x-prepared-long-data-binding/reproduce.md)
passes local source-only checks: three lifetime functions, full initializer and
TLS remain identical; data identities and the single guest pin are updated, and
prior P3 input is explicitly rejected. Actual both-OS runtime acceptance remains
pending; source/unit success is not LONG_DATA/P4 completion.
[Runtime CI39718930329 failure analysis](reviews/v06x-prepared-param-metadata.md)
now confirms both-OS generation/previous regressions PASS and LONG_DATA strict
comparison FAIL: aliased parameter names were incorrectly fixed to `?`.
The engine-owned metadata extension now passes source CI39724676227 at ab8c350.
Its [new exact binding](reviews/v06x-prepared-param-metadata-binding/reproduce.md)
records the BSS+64 layout, unchanged TLS and complete function/init/data pins;
local122 checks and the formal source-only adapter PASS.
[CI39729456821](https://github.com/masahitojp/mariamem/actions/runs/39729456821)
now [closes LONG_DATA and parameter-metadata development acceptance](reviews/v06x-prepared-long-data-pass.md)
at fba09f6 on both OSes: all25 native comparisons match including parameter names,
connections return0 and temporary areas are removed. Previous P1/all72 P2/all14
P3/first7 P4 gates, smoke,122 Python/C checks,3 Go race packages and20 installed
mutations also PASS per OS. Native fixtures/comparator remain unchanged.
Full P4 still requires executing-query cancellation/timeout/disconnect and the
remaining resource/failure matrix; P5/P6 and production acceptance remain pending.
The next [P4 active-exit candidate](reviews/v06x-prepared-p4-active.md) adds
execution-witnessed cancellation/deadline/TCP exits and Close with independent
Fork/baseline cleanup controls. Native5-case controls PASS; actual both-OS7-case
guest acceptance now PASSes on macOS15 arm64 and Ubuntu24.04 x86_64 at
[CI39747013913](https://github.com/masahitojp/mariamem/actions/runs/39747013913),
source_commit fbe419613cc0cc99657d39543c37df7b4dfe5d4a. Execution witnesses,
target invalidation, healthy sibling/baseline reuse and final cleanup all PASS;
134 Python/C checks,4 Go race packages and prior runtime gates also PASS.
Full P4 still needs the remaining failure/resource matrix; P5/P6 are open.
A bounded shared-control status classification
repair preserves unusable for fatal deadlines while keeping request timeout
classification. No guest/converter/Generated Go input is changed.
The [P4 failure/resource closure candidate](reviews/v06x-prepared-p4-failures.md)
now maps every finite P4 obligation to existing actual runtime evidence and
focused component controls. Local macOS134 Python/C checks and4 Go race packages
PASS, including16,884 injected owner-allocation/serializer failures and two
negative oracle mutations. Both-OS component CI now PASSes at86b89d8 in
[CI39752222349](https://github.com/masahitojp/mariamem/actions/runs/39752222349):
134 Python/C checks,4 Go race packages, canonical inventory and public sources
PASS on each OS. With the existing actual-guest/native evidence, the finite P4
row is complete. Guest-source/runtime jobs were explicitly SKIP for this
tests-only candidate; no new actual guest campaign or real-engine OOM injection
is claimed. P5 real consumers/regressions and P6 canonical/J1/independent
generation remain open.
The [P5 real consumer candidate](reviews/v06x-prepared-p5-consumers.md) adds
fixed Go explicit/implicit Prepare and Connector26.7.0 pure/default/C observations,
private source-bound wheel staging, current integration/routine/auth and existing
SQLAlchemy/GORM anchors. Local native Go modes and Python CRUD/typed binary/text
controls PASS, but native Python prepared CALL result traversal and C untyped
NUL projection expose new functional failures. Their original FAIL oracles are
retained; separate native-matching diagnostics cannot grant functional acceptance.
[CI39760963205](https://github.com/masahitojp/mariamem/actions/runs/39760963205)
passed the fresh Linux Python3.14 native control, both-OS units/source build,
and Ubuntu actual guest consumer matching plus installed/ORM regressions.
Mac guest observations were captured, but matching failed because Linux lacked
a native C-extension control; subsequent Mac regressions were skipped.
The [comparison-gate diagnosis](reviews/v06x-prepared-p5-ci-diagnosis.md) supplies
a separate Mac Python3.14 native control with client binary/source/ABI binding;
[corrected CI39769591459](https://github.com/masahitojp/mariamem/actions/runs/39769591459)
now passes all six jobs on exact source_commit
`c5dddf36aac2d62cfe8d4edd22b41fb8da7fdd9b`: both-OS native matching,
installed regressions and existing SQLAlchemy/GORM anchors. Mac C client
binary/source/ABI binding passes; Ubuntu's additional C mode remains an explicit
OpenSSL import SKIP, with required pure/default executed.
After the [P5 Human Review](reviews/v06x-prepared-p5-human-review.md) and
additional MariaDB-driver replay below, the Human explicitly accepted the two
precise Oracle Connector/Python26.7.0 limitations on 2026-10-22.
The [decision](decisions/prepared-consumer-exceptions.md) records **P5 evidence
complete with accepted consumer exceptions**, permitting continuation to P6.
Prospective functional FAILs remain FAIL; no unconditional functional PASS,
main adoption, release version or publication is approved.
P6 canonical independent generation/J1/provenance and permanent edge/consumer
CI placement remain unfinished. The Human requested an additional
[MariaDB Connector/Python replay](reviews/v06x-prepared-mariadb-replay.md)
before continuing the exception decision. Fixed stable1.1.14 passes both exact
case purposes against native12.3.3 using Linux/arm64 Python3.14/ConnectorC3.4.9;
[CI39776208952](https://github.com/masahitojp/mariamem/actions/runs/39776208952)
now passes all six jobs at exact source_commit
`4ce9422e8b5a49727f9a1e3ee81706545e4a8f0d`. Both real-guest Mac/Ubuntu
replays preserve all NUL bytes, drain both prepared CALL results, execute
subsequent SQL and close cleanly; server counters confirm binary execution.
The [results](reviews/v06x-prepared-mariadb-results.md) retain native comparison,
actual Python/ConnectorC versions and driver hashes. The original Oracle
Connector/Python26.7.0 functional FAILs remain; their later Human acceptance is
recorded separately in the decision above, not rewritten into the CI receipts.
The replay establishes the two tested MariaDB-driver paths, not general driver
support. Runtime/guest/converter/canonical generation inputs remain
unchanged, and no default connection is forced to pure mode.


Apart from the explicitly accepted consumer exceptions above, no further
scope reduction is accepted. Main adoption, target version, Qualification and
release remain separate decisions. The MariaDB/lite4mariadb/converter/toolchain pins remain fixed.

**Approved documentation backlog — v0.6.x, 2026-10-17:** explain serial and
parallel Snapshot/Fork usage in the Go/Python guides. Lead Python test usage
with pytest fixtures: prepare migrations/seed once per worker, acquire an
independent DB per test, and let fixture teardown close it. Show ordinary
pytest versus pytest-xdist (`pytest -n 4`) and explicitly state that each xdist
worker owns its own session baseline. Separately show manual parallel Fork
calls sharing one live baseline in one process (Python ThreadPoolExecutor /
Go goroutines), with per-child SQL connections, errors propagated, and all
children joined before baseline Close. Label serial versus parallel benchmark
examples and compare elapsed time rather than overlapping operation sums.
This is documentation of existing behavior, not new cross-worker sharing,
automatic scheduling or a new public API. Implementation is deferred to v0.6.x.

Use real consumer/workload evidence, including Django, Alembic/migrations,
metadata-heavy and dbt-like workloads. Retain SQLAlchemy/GORM regression anchors.
Evaluate actual preparation, per-test isolation, resource and failure costs.
This scope also observes whether many simultaneously retained file-heavy
baselines produce process FD/resource pressure; a dedicated resource-model
change is reopened only if that evidence shows pressure.
This scope also decides per-DB connection-count tuning (currently fixed at 16)
from observed demand and resource effect.

New run-wide baseline fixture ergonomics are deferred here. Existing session
fixtures remain worker-local under xdist. Do not promise new framework/platform
compatibility or introduce automatic cache policy before use-case evidence.

**Wire practical coverage (v0.6.x scope):** main now serves text COM_QUERY,
COM_INIT_DB, COM_PING, COM_QUIT and COM_SET_OPTION, including text multiple
statements/results and the required handshake flags. Published v0.5.3 remains
the earlier text-only baseline. Server-side prepared commands are the current
implementation gap, with production implementation now approved and in progress.
COM_RESET_CONNECTION/pool session reset and other optional commands/flags remain
separate capability-map items; COM_STMT_RESET is not a session reset. Host framing
and guest semantics both need acceptance. No broader protocol implementation is
approved by this status entry.

The [v0.6.x kickoff notes](reviews/v06x-kickoff-notes.md) consolidate the wire gap
inventory, fixture/test UX findings, dump/binlog assessment, the stable-endpoint
verification theme, additional scope candidates and the suggested priority order.
Discovery notes only; not approval.

The [wire-relay feasibility memo](reviews/v06x-wire-relay-feasibility.md) records
an unverified question: whether the embedded guest can expose a real MySQL
endpoint that the host relays, as pgmem relays PostgreSQL's wire. It is not part
of the approved prepared spike, and no test has run.

## v0.7.x — Guest initialization optimization candidate selection

The Human scheduled selection of guest-initialization improvements for v0.7.x
on 2026-10-18. Reuse the child-lifecycle attribution and the v0.5.x bounded
Ubuntu parallel-startup investigation. Potential directions include guest
allocation/growth and collation initialization; no method, expected saving or
implementation is approved yet. The Human also scheduled large-scale tuning here,
specifically the 100MiB case and other preparation-heavy workflows where guest
initialization dominates. Config/host levers come before guest patches. This work
is outside the two v0.5.x actions above.

The [v0.6.x kickoff notes](reviews/v06x-kickoff-notes.md) record the strategy of
using pgmem only as a matched floor reference (after a matched measurement) and
the v0.6/v0.7 split.

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


## Prepared P6 canonical ownership — in progress

Candidate branch `experiment/prepared-canonical` starts from main source_commit
`22a8c64305e706408ebcd54cfd7ecc45426802ad`. It imports tested authored files from
`5d729eff7bd64aa5de3d2b5464e728c3a52fb7ed` without merging the experimental
commit history. Existing preparation/source patch management carries the exact
three-file prepared repair as the next version-specific guest/input.json entry;
recipe guest/source.patch remains unchanged. No new engine behavior or converter
patch is introduced. The incoming Wasm identity is explicitly the reviewed
8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40.
Canonical inventories/generated source, exact J1/data/TLS binding, retained-library
attribution, selected normal-CI consumers and precise public-guide exceptions are
implemented. Local regeneration matched all99 files; J1 failure/protected controls
and the selected Go/Python consumer comparison passed, retaining the accepted
functional FAILs. Full canonical two-source-build and both-platform replay are
still pending new candidate CI; P6 is not complete and no main adoption is claimed.
See the [P6 candidate report](reviews/v06x-prepared-p6-canonical.md) for source
identities, local proof limits, generation steps and pending gates. Existing
release guards remain enabled; no Qualification or release is started.
