# v0.3 ORM / zero-setup acceptance

This is correctness/usability acceptance, not a release or a performance gate.
The branch starts from `30dac13c115ed1d53e4a28e14f51dbec0d3571f0` on
`v0.3/go-zero-setup`; production Go/Python/guest behavior is unchanged in this
acceptance task. No merge, version bump or public fixture release is performed.

## Current evidence

Local macOS 27.0 arm64, Python 3.14.7, Wasmer 7.4.2: **PASS**. The orchestration
and host used installed Go 1.27.1; GORM and the tagged zero-setup fixture use
pinned Go 1.26.8. The real AOT SHA256 is
`90da311cbcaeec30705a73fe45629c7ede470d1094b3db7ca6e113de294b1d84`.
The locally built installed wheel uses the canonical development package version
`0.2.0`; it is not the published v0.2.0 wheel. Its SHA256 is
`fdcfa2e260086a5e7e6dd6c02dce6c625367edb6194a8515bae4a115d7e3283d`.
Production source is the starting commit; acceptance harness additions were
uncommitted during the local run. The CI run will record its exact committed SHA.

| Boundary | Local macOS | Clean macOS 15 CI | Ubuntu 24.04 x86_64 CI |
|---|---|---|---|
| Installed-wheel SQLAlchemy | 44/44 | Pending | Pending |
| GORM default pool / repeated AutoMigrate | 32/32 | Pending | Pending |
| Real CLIENT_FOUND_ROWS unchanged-row 0/1 | PASS | Pending | Pending |
| Commit → dispose → next test cannot observe data | PASS | Pending | Pending |
| Race/lifecycle, sessions, shutdown | PASS | Pending | Pending |
| Snapshot/Fork + actual corrupt/symlink/wrong-build rejection | PASS (50 snapshot checks) | Pending | Pending |
| Tagged-fixture Start(Options{}) → download → cache → real SQL | PASS | Pending | Pending |
| Exact runtime notice identity | PASS | Pending | Pending |

Ignored local evidence is in `tests/evidence/v03-local/` (including per-stage logs
and nested ORM/zero-setup JSON). Native and wheel hashes are recorded before
acceptance and must remain unchanged afterward. Normal verification passed:
Go tests/vet/race, Python 329 passed / 3 skipped, public-source check, fixture
preparation/workflow tests and `git diff --check`.

## SQLAlchemy

The official User/Address-style declarative ORM workload works with ordinary
Session, relationship loading/JOIN, commits, rollback and constraints. See the
[SQLAlchemy report](sqlalchemy-dogfood.md). The original CLIENT_FOUND_ROWS
handshake blocker was fixed generically: the requested capability reaches the
MariaDB guest and unchanged UPDATE reports 1 rather than 0. No flag removal or
SQLAlchemy-specific behavior is used. This acceptance runs the installed wheel
outside the checkout without a native override.

## GORM

Conventional User/Address CRUD and relationships, ordinary database/sql pooling,
transactions, constraint errors and repeat AutoMigrate pass without SQL rewrites,
a dialect override or a single-connection restriction. The original SCHEMATA
schema enumeration blocker was repaired in the generic MariaDB/WASIX path; see
the [GORM report](gorm-dogfood.md). The current untagged Go source is explicitly
substituted in a temporary consumer module and uses the supported environment
override with application `Options{}`. That development check is separate from
the tagged-module automatic-resolution check below.

## Disposable isolation

Both workloads run Start / Fork / Fork / Start suites. A test commits data and
ends without cleanup SQL; its successor sees only the expected seed state.
DELETE and rollback occur as application operations, not test reset machinery.
Pool/engine close and database disposal remain required resource cleanup.

## Go zero-setup: release-like fixture

`tests/consumer/run_zero_setup.py` packages the exact real runtime/AOT/sidecar
using existing native packaging functions. Only a copied fixture manifest's
package version becomes synthetic `0.3.0a999`; the runtime/AOT bytes remain
unchanged. A private file Go proxy serves current Go implementation and embedded
input lock as `v0.3.0-alpha.999`, with **no module replace**. This is test identity,
not a published/requested release. Production versions and release assets are
never edited. Go checksum-database bypass is scoped only to that private fixture
module; public dependencies retain their normal verification.

An ordinary `go build` executable verifies its actual module build information
and calls **Start(ctx, Options{})**. A test-only HTTP transport sends the resolver's
canonical GitHub requests to a local HTTP server while keeping the production
exact URL/tag selection, checksum/version/input-lock validation and atomic
installation path unchanged. No production endpoint/version override is added.
`go test` binaries do not carry the required module identity, hence the ordinary
consumer executable runs the bounded cases with Go's testing library.

Required cases: first download and real SQL; cached/offline startup with no HTTP
request; three concurrent first startups; corrupt cache rejected without
redownload; corrupt archive; interrupted transfer; unavailable release/asset;
correctly checksummed but incompatible package version; retry after failure;
explicit NativeDir taking precedence even over an invalid environment override.
Existing ordinary resolver tests separately cover dev/pseudo-version/replace
refusal and provenance mismatch. They never access public GitHub by default.

## Cross-platform CI

Dispatch existing `guest-build-boundary.yml` on this branch with
`v03_acceptance=true`. It builds/reuses one exact verified WASM and separately
verifies/reuses target AOT on **macos-15 arm64** and **ubuntu-24.04 x86_64**.
Toolchain: Go 1.26.8, Python 3.14, Wasmer 7.4.2; Ubuntu keeps SSE2 + SSSE3.
Existing guest/AOT input seals preserve source/toolchain/hash provenance.
Canonical native/wheel packaging and packaged FAST acceptance run before the
new ORM/zero-setup checks; reviewed notice hashes must match the runtime.
No benchmark, Docker, Tart, tag or publication runs in this mode.

Evidence artifact: `initialization-<platform>-<candidate-sha>`, containing
`tests/evidence/v03-<platform>/acceptance.json`, stage logs, both dogfood suites,
zero-setup fixture identities and AOT provenance. Failure stops the required
steps and retains the failed stage; summaries report failure rather than infer
PASS. Codex submits and hands off without polling.

## Snapshot/Fork and audit readiness

The small dogfood workloads have not demonstrated a clear speed advantage for
Snapshot/Fork. Its product positioning remains unresolved pending broader
workloads; this task neither promotes nor demotes it.

**Pending cross-platform CI:** this branch is not yet declared ready for a
v0.3 release-readiness audit. If both clean platform jobs pass all required checks,
these specific compatibility/usability acceptance gaps are closed and a dedicated
audit is the next decision. Public-release installation smoke still belongs to
the eventual release; the private fixture is not public publication evidence.
