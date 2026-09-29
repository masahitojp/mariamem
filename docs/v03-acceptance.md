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
uncommitted during the local run. The completed CI run below records the exact
committed acceptance source.

| Boundary | Local macOS | Clean macOS 15 CI | Ubuntu 24.04 x86_64 CI |
|---|---|---|---|
| Installed-wheel SQLAlchemy | 44/44 | 44/44 | 44/44 |
| GORM default pool / repeated AutoMigrate | 32/32 | 32/32 | 32/32 |
| Real CLIENT_FOUND_ROWS unchanged-row 0/1 | PASS | PASS | PASS |
| Commit → dispose → next test cannot observe data | PASS | PASS | PASS |
| Race/lifecycle, sessions, shutdown | PASS | PASS | PASS |
| Snapshot/Fork + actual corrupt/symlink/wrong-build rejection | PASS (50 snapshot checks) | PASS | PASS |
| Tagged-fixture Start(Options{}) → download → cache → real SQL | PASS | PASS | PASS |
| Exact runtime notice identity | PASS | PASS | PASS |

Ignored local evidence is in `tests/evidence/v03-local/` (including per-stage logs
and nested ORM/zero-setup JSON). Native and wheel hashes are recorded before
acceptance and must remain unchanged afterward. Normal verification passed:
Go tests/vet/race, Python 329 passed / 3 skipped, public-source check, fixture
preparation/workflow tests and `git diff --check`.

## Completed clean-platform evidence

[CI run 36582171063](https://github.com/masahitojp/mariamem/actions/runs/36582171063)
passed on exact source **`872fdea882ad82540ffe32e14e506ff67b2d10c3`**.
Both jobs used Go 1.26.8, Python 3.14.7 and Wasmer 7.4.2: macOS 15.7.9 arm64
and Ubuntu 24.04.5 LTS x86_64 (glibc 2.39, SSE2 + SSSE3 AOT baseline).

Both platform evidence records report all ten required stages PASS. SQLAlchemy
passed 44/44 and GORM 32/32 without framework workarounds. Raw wire acceptance
passed 38 checks, including CLIENT_FOUND_ROWS; snapshot integrity passed 50
checks, including real corruption rejection. Race/lifecycle and packaged
Go/installed-wheel acceptance also passed, including interrupted-query
invalidation and cleanup.

Each release-like resolver consumer passed all nine cases: first download,
cached/offline, concurrent first starts, corrupt cache, corrupt download,
interrupted download, missing artifact, incompatible version and explicit
offline override. This closes Ubuntu real-runtime acceptance as well as the
previous fixture-only limitation.

The downloaded evidence agrees on source SHA, native runtime/AOT identity and
fixture archive hashes. Downloaded AOT manifests and acceptance harness source
hashes were independently recomputed; binary archive hashes were checked by CI
and reconciled across its records, not recomputed from local archive downloads.
Both platforms consumed the same guest WASM:
`d49402efec834414527537f639c9a11e5709bf8642357d34d33c7cfa471322d3`.

| Target | Accepted AOT SHA256 |
|---|---|
| macOS arm64 | `f8b46a3f6f47dde36f90f518c4edee180713027b1311a178adb0aa46fa5a7c72` |
| Ubuntu x86_64 | `2f37cba52236cc1d8406b8d360bbf76cc480fa5cb570936f44ec08a6a3821419` |

Raw downloaded evidence remains ignored under
`tests/evidence/v03-ci-36582171063/`. The workflow artifacts named below are the
run's evidence location. These development candidates retain package version
`0.2.0`; they are not replacements for published v0.2.0 assets.

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

**Ready for a dedicated v0.3 release-readiness audit:** both clean platform jobs
passed the required compatibility/usability checks for the exact source above.
This is not an aggregate release READY verdict or publication approval.
Public-release installation smoke still belongs to the eventual release; the
private fixture is not public publication evidence. No further feature work or
merge to main is performed by this acceptance task.

## Main integration and release audit

The complete accepted history plus its evidence documentation was fast-forwarded
into main at `96a5c3b32e76715eee664a171e0b6f435f3b458f`. Only documentation
differs from the CI source above. The subsequent [main audit](release-readiness-v0.3.md)
records missing release-candidate/public consumer gates; this compatibility PASS
is not aggregate release READY for a later main or release-preparation SHA.
