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

## Current public release

Current public release:

```text
Git / Go: v0.1.0-alpha.3
Python:   0.1.0a3
```

Release:

```text
https://github.com/masahitojp/mariamem/releases/tag/v0.1.0-alpha.3
```

The accepted artifacts were published unchanged. Clean artifact acceptance and
post-publication public Go tag/native-bundle consumer smoke passed. The release
tag points to
`1c97b7bda65bffa66abcf751bddd6bbc10132304`; main has continued development.

Go:

```text
fresh module
→ go get public tag
→ public native bundle
→ database/sql
→ SELECT 1
```

Python:

```text
fresh virtualenv
→ install public wheel
→ start MariaDB
→ SQL
→ Snapshot / Fork
```

The alpha.3 release targets:

```text
macOS 15+ / Apple Silicon arm64
```

Alpha.3 includes multi-client support (the current guest capacity is 16
independent sessions), ordinary connection-pool use without
`SetMaxOpenConns(1)`, canonical verification commands, baseline GitHub Actions,
single-source versioning, and exact artifact/acceptance-evidence binding.
The session capacity is not a permanent public API guarantee.

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

## 0.1 — Works enough

Goal:

> A developer can use a real disposable MariaDB locally and in CI using normal
> database clients, and failures are understandable enough to diagnose.

The most important product requirements are:

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
Linux / x86_64
```

Linux x86_64 is important because CI environments commonly use Linux and it
makes mariamem useful beyond the maintainer's local Mac.

Not currently required:

- Linux arm64
- Windows
- macOS Intel
- broad Linux distro compatibility
- Alpine / musl

### Minimum viable failure UX

0.1 should avoid opaque failures where possible.

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
the intended 0.1 release model. Post-build evidence must stay external to
candidate bytes and should not require a new source commit for publication:

```text
build inputs → immutable candidate → candidate SHA256
             → external acceptance evidence → release guard
```

The canonical guest build boundary is Linux x86_64 WASIX guest build → exact
WASM handoff → macOS arm64 AOT/package. Docker and Tart are not dependencies
of the canonical release path. This Linux build capability does not yet mean
Linux product/runtime support.

CI must retrieve the exact candidate source/ref through its remote trigger,
without a permanent manual push step or build/tag diff inspection. Clean macOS
acceptance belongs in CI. Tart is not part of the canonical local development
or release path; local/Codex work should not download VM images, maintain Tart
VMs, or run clean-platform acceptance locally. Tart remains available for
explicitly requested debugging. Missing CI acceptance infrastructure is a
release-infrastructure gap, not a reason to silently fall back to Tart.

---

## Remaining 0.1 direction

```text
v0.1.0-alpha.3  DONE
        ↓
release publication mechanics (implemented)
READY → exact tag → GitHub Release → exact assets → public smoke
        ↓
v0.1.0-alpha.4 end-to-end release rehearsal
        ↓
failure diagnostics foundation
        ↓
Linux x86_64 product support
        ↓
minimum failure UX
        ↓
v0.1.0 rehearsal / correctness
        ↓
v0.1.0
```

This is a roadmap direction, not a rigid task tracker. Alpha.4 is the proof that
the new release path works end-to-end, rather than a product-feature release.
Publication mechanics have focused verification; the real release rehearsal
still needs to exercise the complete transaction. A failure diagnostics
foundation follows so CI failures expose their stage and useful evidence before
more product work. Linux x86_64 and minimum failure UX remain 0.1 product
requirements, distinct from maintainer/release infrastructure.

The pre-release validation matrix remains intentionally narrow:

```text
Python 3.14
Go 1.26
```

This is a validation choice, not a statement that other versions cannot work.

Broad version compatibility is not currently worth slowing early development.

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

For example:

```text
major  = 0
minor  = 1
patch  = 0
stage  = alpha
serial = 3
```

From this, tooling derives:

```text
v0.1.0-alpha.3
0.1.0a3
native metadata
artifact names
release metadata
```

`python3 scripts/verify.py check` checks the derived forms. Native candidate
packaging and the release guard reject stale package metadata, preventing a
repeat of the alpha.2 release's accepted native artifact referring to alpha.1.

---

## Linux x86_64 before 0.1

Linux x86_64 is planned as a 0.1 product capability.

The intended scope is deliberately narrow:

```text
Linux x86_64
Go
Python
Start / SQL
Snapshot / Fork
multi-client
timeout / cleanup
release artifact smoke
```

Do not expand this into a Linux compatibility matrix during 0.1.

Once Linux integration is reliable, normal CI should prefer Linux where
practical, while macOS remains a platform-specific acceptance target.

---

## 0.2 — Fast

Goal:

> Creating an isolated MariaDB from prepared state should be cheap enough that
> tests do not need to conserve database instances.

0.2 is outcome-driven.

Possible implementation techniques such as COW, runtime sharing, or embedded
WASM runtimes are means, not the release goal.

Candidate product metrics include:

- Fork-to-ready latency
- p50 and p95 latency
- 1 / 4 / 8 parallel forks
- incremental memory per fork
- incremental storage per fork
- latency scaling with fixture size
- no major steady-state SQL latency regression
- no isolation or correctness regression

The primary end-to-end metric should measure:

```text
Fork()
→ database ready
→ client connection succeeds
→ first SQL query succeeds
```

rather than an internal runtime-ready event.

Initial exploratory targets may be around:

```text
warm fork-to-ready p50 < 250 ms
warm fork-to-ready p95 < 500 ms
```

These are investigation targets, not yet public performance promises.

Fixtures should remain representative of test workloads rather than
production-scale datasets.

Small / medium / moderately large fixtures are sufficient to understand scaling
behavior.

---

## 0.2 architecture exploration

Before choosing an optimization strategy, inspect the current execution path.

Current conceptual path:

```text
client
  ↓
MySQL wire
  ↓
Go host / mysqlwire
  ↓
Wasmer process
  ↓
WASIX
  ↓
MariaDB WASM guest
```

For every boundary ask:

```text
Why does this boundary exist?
What does it cost?
Does it duplicate another layer?
Can it be removed or merged?
What compatibility value does it provide?
```

Relevant reference projects include:

```text
shyim/lite4mariadb
moriyoshi/pglite-go
```

`pglite-go` is particularly interesting because it demonstrates a different
execution architecture:

- PostgreSQL/PGlite WASM
- Go host
- embedded WASM runtime
- Wasmtime by default
- optional wazero backend
- no external database-server process

The purpose is not to copy `pglite-go`.

The useful question is:

> Which execution boundaries has pglite-go removed, and could mariamem remove
> similar boundaries without losing its MariaDB, multi-client, and
> Snapshot/Fork properties?

Possible architectural directions may include:

```text
A. keep external Wasmer and optimize current architecture

B. embed a WASM runtime in the Go host

C. move toward a pglite-go-style host/runtime architecture

D. redesign guest/host responsibilities more substantially
```

The current `lite4mariadb` guest depends on WASIX, so alternative runtime
feasibility must be investigated rather than assumed.

Measure first, then choose the architecture.

Breaking internal architecture or public `0.x` APIs is acceptable if justified.

---

## 0.3 — Easy / zero-setup

Goal:

> A user can install mariamem and start a database without understanding or
> manually managing its native runtime.

The desired user experience approaches:

```text
install mariamem
↓
Start()
```

Potential techniques include:

- platform detection
- native artifact resolution
- automatic download
- integrity / provenance verification
- local runtime cache
- offline behavior
- explicit runtime override
- package/runtime compatibility checking

Automatic download is one possible implementation, not the product goal.

The product goal is to make native-runtime complexity invisible during normal
usage.

0.3 should initially target already-supported platforms.

Do not combine zero-setup work with broad platform expansion unless evidence
justifies it.

---

## 0.3+ backlog

Possible later themes include:

### Platform expansion

- Linux arm64
- Windows
- additional macOS targets if still relevant

### Ecosystem coverage

Possible representative consumers:

- SQLAlchemy / Alembic
- Django
- golang-migrate
- GORM
- ent
- goose
- Atlas

Ecosystem integrations should be added because they expose useful real-world
compatibility problems, not to collect framework badges.

### Connection scalability

Possible future work:

- runtime-configurable session capacity
- connection counts beyond the current guest capacity
- high-concurrency performance
- memory-efficiency improvements

Supporting ordinary connection pools is a 0.1 concern.

Supporting very high connection counts is not.

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

With alpha.3 published, multi-client support provides a useful milestone for
leaving a concrete downstream usage note on the original lite4mariadb
announcement:

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
