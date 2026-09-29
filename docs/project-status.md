# mariamem project status

This document records the current state, important design decisions, release
direction, and roadmap for mariamem.

It is not an API reference or detailed task tracker.

Its purpose is to let a future contributor, coding agent, or discussion recover
the important project context quickly without relying on past chat history.

---

## Project goal

mariamem aims to make a real MariaDB instance as convenient and disposable as
a test double.

It does not reimplement MariaDB SQL semantics.

The core idea is:

> Use a real MariaDB engine for integration tests while avoiding the startup
> and lifecycle cost normally associated with running a full external database
> server.

The current high-level architecture is:

```text
Go / Python application
        ↓
MySQL client / wire protocol
        ↓
mariamem host
        ↓
Wasmer / WASIX
        ↓
MariaDB compiled to WebAssembly
```

For Python, `mariamem-host` currently runs as a separate Go child process.

For Go, the public Go API calls the host implementation in-process, while the
MariaDB/Wasmer guest remains external.

Core properties:

- real MariaDB SQL and InnoDB semantics
- Go and Python APIs
- ordinary MySQL client compatibility
- disposable lifecycle suitable for tests
- Snapshot / Fork support
- multiple independent SQL sessions
- native runtime distributed as release artifacts
- GPL-2.0-only project with corresponding source and third-party notices

---

## Release state — v0.2.0 preparation

The current public release is [v0.2.0-alpha.1](https://github.com/masahitojp/mariamem/releases/tag/v0.2.0-alpha.1),
with Python distribution `0.2.0a1`. **v0.2.0 is being prepared, not yet released.**
The [readiness audit](release-readiness-v0.2.md) found no known blockers and
concluded READY AFTER RELEASE PREP. Close v0.2 after version preparation and
final two-platform Release CI acceptance/aggregate READY and publication.

Supported native platforms:

- macOS 15+ / Apple Silicon arm64
- Ubuntu 24.04 LTS / x86_64, requiring SSE2 + SSSE3

Release CI clean-accepts macOS 15 arm64 and Ubuntu 24.04 x86_64 independently.
The canonical toolchains are Go 1.26.8 and Python 3.14. Go's module minimum is
1.26.0 and Python package metadata allows >=3.9; these are not evidence of a
broad tested-version matrix. Other OS/architecture/distro combinations are
unsupported; future platform experiments are not release support.

Go uses the public module and an explicitly supplied native bundle; Python
wheels include their runtime. Artifacts have corresponding source, notices,
exact hashes and separate clean-platform acceptance. Multi-platform Release CI,
the release skill and startup failure UX are complete enough for this milestone.
Release initiation is one human decision; CI owns execution after Codex hands off.

---

## Current development state

### Multi-client support

Task 2e was completed in commit:

```text
d314147
```

A single `Database` now supports multiple simultaneous SQL connections.

The existing guest protocol already had the required session model, so no guest
protocol redesign was needed.

The guest currently advertises:

```text
MaxSessions = 16
```

These are 16 independent MariaDB sessions.

Each guest slot has its own worker and thread-local `MYSQL*` connection.

The host now:

```text
client connection
    ↓
allocate free guest slot
    ↓
open MariaDB session
    ↓
run queries
    ↓
close session
    ↓
wait for guest close acknowledgement
    ↓
release slot for reuse
```

Verified behavior:

- session variables are isolated between SQL connections
- temporary tables are isolated
- transactions are isolated
- queries on different slots may execute concurrently
- slot reuse does not retain state from the previous session
- multiple connections may remain open while the database is closed
- guest process cleanup still works correctly
- the 17th connection returns recoverable MySQL error `1040`
- ordinary connection-pool usage no longer requires `SetMaxOpenConns(1)`

Concurrent execution is supported, but mariamem does not currently promise
performance scaling from concurrent queries.

`16` is the current guest capacity.

It should not be treated as a permanent mariamem product limit or public
contract.

If connection capacity becomes user-configurable in the future, the public
concept should likely be connection-oriented (`max_connections`) rather than
exposing the guest implementation term `max_sessions`.

---

## Lifecycle semantics

### Normal Close

After a normal close:

```text
Closed() == true
Err() == nil
```

The Python equivalent reports a normal closed state.

### Successful Snapshot

A successful Snapshot consumes the source database.

After Snapshot succeeds, the source database is closed.

If Snapshot is rejected because its preconditions are not satisfied, the source
database remains usable.

With multiple SQL sessions, Snapshot is rejected if any session has an
unfinished transaction.

### Interrupted active SQL

There is currently no safe per-query cancellation mechanism inside the guest.

Therefore, if an actively executing SQL query is interrupted by:

- host query timeout
- Go context deadline / cancellation
- client disconnect during execution

the entire `Database` becomes unusable.

This remains true with multiple SQL connections.

If one active query invalidates the database, other connections to the same
database also become unusable.

Go exposes this using:

```text
db.Closed() == true
errors.Is(db.Err(), mariamem.ErrUnusable)
```

Ordinary SQL errors and normal idle client disconnects do not invalidate the
database.

---

## Product scope

mariamem is primarily intended for:

- integration tests
- migration tests
- SQL / database semantics tests
- tests requiring isolated MariaDB instances
- small to medium representative fixtures
- local development and CI

mariamem is not intended to reproduce production-scale database performance.

Explicit non-goals include:

- production-scale dataset emulation
- tens or hundreds of millions of rows as a normal test fixture
- production-like storage / buffer-pool performance
- replacing staging or performance-test environments
- benchmarking production MariaDB throughput through WASM

The value proposition is real MariaDB semantics with cheap lifecycle and
isolation, not production-equivalent performance.

---

## Pre-1.0 compatibility philosophy

mariamem is still early-stage software.

Current users are primarily the maintainer and CI.

Therefore, the project intentionally prioritizes learning speed over API
stability during the `0.x` series.

Breaking changes to:

- Go APIs
- Python APIs
- Snapshot representation
- runtime architecture
- host / guest boundaries

are acceptable when they materially improve the design.

Strong long-term compatibility guarantees should be considered when the project
approaches `1.0`, not prematurely during `0.x`.

---

# Roadmap

## 0.1 — Works enough (released)

Goal:

> A developer can use a real disposable MariaDB locally and in CI using normal
> database clients, and failures are understandable enough to diagnose.

The completed product requirements were:

### Ordinary database usage

- multi-client support
- independent MariaDB sessions
- normal connection pools without mariamem-specific single-connection settings
- predictable lifecycle semantics

Multi-client support is now complete.

### Local and CI usage

Target platforms for 0.1:

```text
macOS 15+ / arm64
Ubuntu 24.04 LTS / x86_64
```

Ubuntu 24.04 x86_64 is important because CI environments commonly use Linux and it
makes mariamem useful beyond the maintainer's local Mac.

Not currently required:

- Linux arm64
- Windows
- macOS Intel
- broad Linux distro compatibility
- Alpine / musl

### Minimum viable failure UX

The implemented failure UX avoids opaque failures where practical.

Users should be able to distinguish at least:

- unsupported platform
- missing native runtime
- package/native incompatibility
- guest startup failure
- connection-capacity exhaustion
- database invalidation after interrupted SQL

The goal is not to build a comprehensive diagnostic framework.

The goal is:

> When CI fails, the user should usually know what failed and what to inspect
> next.

### Release correctness and maintainer requirements

0.1 release artifacts should satisfy:

- versions are consistent
- the exact public artifacts can actually start and run MariaDB
- corresponding source is correct
- third-party notices / provenance are correct
- a minimal clean consumer smoke test succeeds

Release CI is a 0.1 maintainer requirement, separate from the product
requirements above. Alpha.3 showed that the manual happy path repeatedly
coordinated the human, ChatGPT, Codex, and local release state for deterministic
steps. This costs approval attention, handoff effort, coding-agent capacity,
and depends unnecessarily on the local environment. Happy-path release
mechanics belong in CI. Codex/local development should change the product or
release system, run focused checks, prepare notes where useful, and diagnose
`NOT READY` or unexpected failures, not orchestrate a defined release by hand.

The intended boundary is **one manual decision, automated mechanics**:

```text
human: "release this exact candidate"
→ Codex: submit Release CI and hand off
→ CI: exact remote checkout, immutable artifacts and hashes
→ clean-platform acceptance and external evidence
→ release guard
    NOT READY → stop
    READY → derived Git tag, GitHub Release and exact assets
          → post-publication smoke
```

Starting the release workflow is the human publication decision for the whole
transaction. There is no second human approval gate after READY and no repeated
approval of Git, hashing, packaging, or upload operations. CI does not choose
whether or when to release: the human authorizes that by requesting the release.
Codex returns the run URL and exact candidate SHA after successful submission;
it does not poll, wait, or supervise the workflow. It re-enters for an explicit
status request, requested failure diagnosis, or an unexpected engineering
decision. Candidate verification can reach READY from an exact remote source
commit, and publication mechanics are implemented. The workflow defaults to
verification only; an explicit `operation=release` dispatch authorizes
READY → exact-source tag, accepted assets, and public consumer smoke. Publication
failures never move tags or replace assets.

The release tag should identify the **exact source commit used to build the
published host/package artifacts**. Alpha.3 accepted a binary build commit
different from its final tag commit because post-build review/evidence was
committed afterward; that relationship was reviewed for alpha.3, but is not
the current release model. Post-build evidence must stay external to
candidate bytes and should not require a new source commit for publication:

```text
build inputs → immutable candidate → candidate SHA256
             → external acceptance evidence → release guard
```

The canonical guest build boundary is Linux x86_64 WASIX guest build → exact
WASM handoff → macOS arm64 and Ubuntu 24.04 x86_64 AOT/package. Docker and
Tart are not dependencies of the canonical release path. Release CI builds the
common guest once, accepts each platform independently, and requires aggregate
READY before one tag/release can publish either platform. Ubuntu AOT records
the fixed SSE2+SSSE3 CPU requirement. Retries restore paired immutable platform
artifacts/evidence; public smoke runs on each platform after publication.

CI must retrieve the exact candidate source/ref through its remote trigger,
without a permanent manual push step or build/tag diff inspection. Clean macOS
acceptance belongs in CI. Tart is not part of the canonical local development
or release path; local/Codex work should not download VM images, maintain Tart
VMs, or run clean-platform acceptance locally. Tart remains available for
explicitly requested debugging. Missing CI acceptance infrastructure is a
release-infrastructure gap, not a reason to silently fall back to Tart.

---

## v0.2.0 — FAST completion state

The north star remains:

> Creating an isolated real MariaDB should be fast and cheap enough that tests
> do not need to conserve database instances.

Production changes remove per-startup RSA generation using public test keys,
carry verified native identity within one startup call and use bounded
**2-worker verification** for independent hash work. Integrity checks, plugin
selection, default grant bypass and lifecycle semantics remain intact. No
restore, cache-size or runtime-sharing experiment was integrated.

The established fixed-local reference is a **MacBook Air M1 / 16 GiB /
macOS 27.0 arm64**, measuring 30 independent trials of Fork through the first
successful SQL against a prepared 1,000-row fixture, with diagnostics OFF:

| Metric | Reference result |
| --- | ---: |
| p50 | 374.2 ms |
| p95 | 417.7 ms |
| max | 446.1 ms |

This met the final fixed-reference p95 <500 ms milestone. These numbers are
reference measurements, not hardware-independent guarantees or an Ubuntu
latency promise. Hosted CI hardware has substantial between-job variation and
is used for correctness/regression monitoring, not an absolute 500 ms release
gate. See [reference method and exact identities](../benchmarks/final-v02-local-reference.md)
and [verification comparison](../benchmarks/two-worker-verification.md).
Earlier 250/500 ms targets remain longer-term stretch goals; historical
600/900 ms red lines were diagnostics, not a definition of FAST completion.

Both platforms completed ×16 isolated DBs. One DB with 16 simultaneous sessions
passed session isolation, reconnect, cleanup and recoverable MySQL 1040 rejection
of the 17th session. Current capacity is 16, not a permanent public API guarantee;
ordinary Go pools do not require `SetMaxOpenConns(1)`. No runtime residue was
observed after teardown in the measured scenarios.

Memory efficiency is **not solved**: measured ×16 average incremental ready cost
was approximately **259 MiB/DB on macOS** (physical footprint) and
**327 MiB/DB on Ubuntu** (PSS). These counters differ and are not raw RSS or exact
allocation ownership. CPU and incremental/private memory remain first-class
metrics, with numeric budgets provisional rather than release promises.
See [memory/session envelope](../benchmarks/memory-session-envelope.md).
The Aria 128→16 MiB probe was rejected: ordinary ready savings were only 5–6
MiB/DB, while heavy workloads regressed wall/CPU by 6–11%. No further cache tuning
or memory architecture work is required for v0.2.

### Product value and practical comparison

mariamem offers Docker-free MariaDB testing, disposable server-level isolation
and prepared-state reuse. Per-test DB disposal can avoid application test code
having to perform rollback, schema reset or data cleanup to isolate tests.
Connections and owned DB/snapshot handles still need deterministic Close/context
manager cleanup; failed tests do not make resource ownership optional.

In the [fixed-reference practical comparison](../benchmarks/practical-suite-comparison.md),
fresh Testcontainers server/container isolation was much slower in measured
suites; sharing one container and resetting schemas was much faster for repeated
tests. Schema reset shares global/engine/server state and is a different isolation
contract. Snapshot/Fork did not materially beat fresh mariamem Start for this
small 1,000-row fixture. This does not establish universal superiority or the
benefit for larger/application fixtures. MariaDB versions/defaults differed.
Two fresh-container 100-test attempts failed in that benchmark environment;
the cause is unresolved and no general Testcontainers reliability claim follows.

**Future v0.3 dogfood hypothesis:** disposable per-test databases may reduce
cleanup/reset/transaction-lifecycle reasoning when humans or coding agents
produce CRUD tests. This is unvalidated, not a product claim. Real pools,
transactions, application migrations and test failure paths must test it.

The remaining v0.2 work is release preparation and final release CI. Further
latency/resource work is deferred, not abandoned; ORM/usability evidence comes
before larger architecture exploration.

---

## Verification state

The verification/toil audit consolidated local checks into canonical `check`,
`integration`, `release-check`, and `bench` entry points. Baseline GitHub
Actions runs normal and real-guest integration checks. Release candidate CI
builds immutable candidates, clean-accepts them, and evaluates READY using
external evidence. It supports `full`, `acceptance-only`, and `guard-only` modes.
Retries reuse immutable artifacts/evidence and verify source identity and hashes;
missing, expired, corrupted, or mismatched inputs fail instead of silently
rebuilding. Acceptance-only avoids rebuilds; guard-only also avoids re-acceptance.
An explicitly authorized release proceeds from READY to exact-source tag,
GitHub Release, exact assets, and public smoke without another approval.
Codex submits and hands off rather than polling or supervising CI.
Release-facing documentation/version consistency is mechanically checked against
the canonical version. Release-path GitHub Actions use Node 24-compatible releases
pinned by immutable SHA. Benchmarks remain performance-work only. See
[local verification](development.md#local-verification) for commands and boundaries.

---

## Version single-source

The release version is single-source in `python/mariamem/_version.py`.

Go and Python require different textual version formats, so the source of truth
represents semantic components rather than reusing one ecosystem-specific
string.

For the intended stable v0.2.0 preparation (not yet applied):

```text
major  = 0
minor  = 2
patch  = 0
stage  = (empty)
serial = 0
```

From this, tooling derives:

```text
v0.2.0
0.2.0
native metadata
artifact names
release metadata
```

`python3 scripts/verify.py check` checks the derived forms. Native candidate
packaging and the release guard reject stale package metadata, preventing a
repeat of the alpha.2 release's accepted native artifact referring to alpha.1.

---

## Ubuntu 24.04 x86_64 support boundary

0.1 includes Ubuntu 24.04 LTS / x86_64 Go and Python artifacts, clean consumer
acceptance, Snapshot/Fork, multi-client, timeout/cleanup and startup diagnostics.
AOT requires SSE2 + SSSE3. This does not claim generic Linux, manylinux,
Linux arm64, Alpine/musl or other distro support. macOS remains an independent
platform acceptance target.

---

## Remaining roadmap

```text
v0.2.0 FAST: release preparation → final Release CI → release
    ↓
v0.3 ORM dogfood / usability
    ↓
v0.4 SCALE exploration, informed by dogfood
    ↓
v0.5 broader client workloads
    ↓
1.0 stable public APIs and semantics
```

### v0.3 — ORM dogfood / usability

Validate SQLAlchemy, GORM, connection pools, transactions/sessions, realistic
CRUD tests and disposable per-test DB ergonomics. Test whether cleanup-free
state isolation reduces reset/rollback boilerplate, including AI-generated test
dogfood; deterministic resource cleanup is still required. No broad framework
compatibility is established yet. Django and migration/introspection behavior
may provide additional evidence where relevant.

Do not combine this milestone with major performance architecture work.
Retain the usability direction: install/start should not require users to
understand native runtime management. Python already bundles it; Go still needs
an explicit native directory. Automatic download/cache is a possible technique,
not an accepted design or a required v0.2 feature.

### v0.4 — SCALE

Use v0.3 workloads to explore CoW, runtime sharing, guest filesystem/state
sharing, restore-path redesign, startup and per-DB memory improvements. These
are candidates, not committed designs. The current guest depends on WASIX;
embedding/replacing a runtime cannot be assumed viable. References such as
pglite-go inform questions, not a porting plan. Measure benefit, isolation and
platform implications before selecting an architecture.

### v0.5 — Broader client workloads

Validate the dbt MySQL connector, metadata/introspection-heavy clients and
non-ORM connection/lifecycle patterns. Do not claim support before exercising
the actual consumer and its semantics.

### 1.0 — Stable public APIs and semantics

Stabilize supported lifecycle, isolation and compatibility contracts using the
workload evidence. A stable semantic version in the 0.x series does not promise
1.0-level API compatibility.

### Unscheduled backlog

Broader platforms (Linux arm64, Windows, additional distro/macOS targets),
runtime-configurable or higher session capacity, offline/native artifact
resolution and wider ecosystem coverage remain evidence-driven follow-ups.
Ordinary pools are supported; high connection-count scalability is not claimed.

---

## AI-assisted development cycle

The project is also being used to refine an AI-assisted development workflow.

The current useful separation is:

```text
Explore
  ↓
Challenge
  ↓
Human decision
  ↓
Implement
  ↓
Verify
```

Typical model/tool roles:

```text
Explore / investigate
    → reasoning-oriented model, moderate effort

Challenge / compare trade-offs
    → higher reasoning effort when decisions are expensive

Final product / architecture decision
    → maintainer

Implementation
    → coding model at moderate effort

Mechanical verification
    → scripts / CI
```

When evidence is missing, use small implementation spikes:

```text
Explore
  ↓
identify uncertainty
  ↓
small spike
  ↓
measure
  ↓
reconsider options
  ↓
human decision
```

Do not build a complex autonomous multi-agent framework yet.

First run this development loop manually and observe which handoffs become
repetitive enough to automate.

The goal is to spend model intelligence on:

- architecture
- difficult diagnosis
- trade-offs
- implementation

rather than repeatedly spending it on deterministic mechanical checks.

---

## Upstream relationship

mariamem builds on `shyim/lite4mariadb`.

A concrete downstream usage note can reference multi-client and lifecycle
evidence on the original lite4mariadb announcement:

```text
https://www.linkedin.com/posts/shyim_lite4mariadb-mariadb-compiled-to-webassembly-share-7501126063813533698-LdJG/
```

The point is not to announce a finished product.

It is to report that lite4mariadb is being used as the MariaDB guest behind a
real Go/Python disposable database tool.

---

## Things intentionally not required for 0.1

Unless evidence changes the priority, these are not 0.1 blockers:

- COW / runtime sharing
- major execution-path redesign
- embedded WASM runtime
- pglite-go-style architecture
- production-scale fixture support
- native runtime auto-download
- Linux arm64
- Windows
- high connection-count scalability
- broad ORM/framework coverage
- perfect Go/Python API parity
- autonomous/unattended publication or release decisions
- automatic version bumps or release scheduling
- 1.0-level API stability

---

## Project-management direction

GitHub should eventually contain a lightweight roadmap.

Suggested structure:

```text
Project: mariamem roadmap

Milestones:
  v0.1.0
  v0.2.0
  v0.3.0
  v0.4.0
  v0.5.0
  v1.0.0
```

GitHub Issues should contain actionable work.

This document should contain:

- important context
- architectural decisions
- release philosophy
- roadmap boundaries
- important non-goals

Do not turn this file into the detailed task tracker.

---

## Updating this document

Update this document when one of these changes materially:

- public release state
- lifecycle semantics
- supported platforms
- major architecture
- release philosophy
- major roadmap boundaries
- important non-goals

Implementation details that are already obvious from the code do not need to be
duplicated here.

When detailed work becomes actionable, move it to GitHub Issues rather than
continuously expanding this document.
