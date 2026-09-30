# v0.3 release-readiness re-audit

Audited `main` at `fb1dfff575d0d7cf1604d3edcdd583c8db97bb11` on
2026-09-30 JST, after the release-pipeline fixes. This supersedes the
`NOT READY` audit made at `96a5c3b`.
No v0.3 version bump, tag, release, or publication was made for this audit.
The canonical version is still `v0.2.0` / Python `0.2.0`.

## Product evidence

[The v0.3 cross-platform acceptance](https://github.com/masahitojp/mariamem/actions/runs/36582171063)
accepted the product state at `872fdea` on macOS 15 arm64 and Ubuntu 24.04
x86_64. [The acceptance report](v03-acceptance.md) records SQLAlchemy 44/44
and GORM 32/32 on each platform, including ordinary CRUD, relationships,
transactions, pools, and cleanup-free committed per-test isolation. SQLAlchemy
uses normal `CLIENT_FOUND_ROWS` behavior; GORM repeats `AutoMigrate` with working
schema discovery. The same run covered Snapshot/Fork, corruption and lifecycle
checks, notices, and nine release-like Go resolver cases per platform. These
full dogfood counts are product evidence, not a claim that the release guard
reruns both entire suites.

The resolver's normal API is `mariamem.Start(ctx, mariamem.Options{})`. Exact
version resolution, first download, verified cache reuse, offline startup,
concurrent first resolution, corruption/interruption rejection, and explicit
`NativeDir` override were accepted. Dev, replaced, and pseudo-version builds
must not silently use an unrelated public bundle. The supported release scope
remains macOS 15+ arm64 and Ubuntu 24.04 LTS x86_64 (SSE2 + SSSE3); the clean
acceptance toolchains are Go 1.26.8 and Python 3.14.

## Release boundary re-audit

[Full Release CI verification](https://github.com/masahitojp/mariamem/actions/runs/36664326897)
used exact remote source `fb1dfff575d0d7cf1604d3edcdd583c8db97bb11`.
Both platform candidate builds, native and installed-wheel acceptance, focused
consumer smoke, platform guards, and the aggregate guard succeeded. The
aggregate recorded `READY` for that source. This was `operation=verify`: it
exercised the new gates with the still-canonical `v0.2.0` version, and did not
tag or publish. It is **not** final `v0.3.0` candidate acceptance.

| Required boundary | Evidence and fail-closed check |
| --- | --- |
| macOS and Ubuntu | Independent clean native and installed-wheel acceptance on macOS 15 arm64 and Ubuntu 24.04 x86_64; both platform guards and the aggregate require the exact source SHA and supported platform set. |
| Go zero setup | External Go module from a private exact-version proxy containing candidate Go source; fresh empty cache, no native override or repository-local bundle; `Start(ctx, Options{})`, SQL, then verified offline cache restart. |
| Candidate distribution | The production resolver requests the canonical exact-tag URLs, redirected to a private candidate distribution serving the unchanged frozen native archive. Receipt, archive SHA256, package version, embedded input-lock identity, and candidate Go-source identity must match. No public tag is needed for candidate testing. |
| Python wheel and SQLAlchemy | Candidate wheel installed in a clean external virtualenv; ordinary engine/session, schema creation, INSERT + COMMIT, SELECT, and unchanged-row UPDATE rowcount 1 without modifying `CLIENT_FOUND_ROWS`. Installed wheel hash/version must match the candidate. |
| GORM discovery | External Go consumer performs `AutoMigrate`, confirms the table is discoverable, and repeats `AutoMigrate` without duplicate creation. This runs against the accepted native bundle. |
| Source, artifacts, notices | Pinned guest source/toolchain and common WASM, separate platform AOT provenance, native/wheel manifests and hashes, corresponding source, runtime notices, and public-source/version checks remain required by the existing guard. |

The downloaded CI records show all four focused consumer steps PASS on both
platforms. Each platform's `ci-ready.json` binds the exact SHA256 of its
`ci-consumer-smoke.json`; the aggregate re-runs the platform checks and requires
both records. Missing, skipped, failed, wrong-source, wrong-platform, or
wrong-native/wheel-hash consumer evidence prevents `READY`. Focused negative
tests also cover these failure paths. The exact candidate's native and wheel
hashes differ by platform as intended, while both share the same source and
common guest provenance.

Publication rechecks aggregate `READY`, the exact tag target and accepted asset
hashes, and never rebuilds accepted bytes. Post-publication smoke is configured
to download the published assets and use the public Go tag with an empty cache
and `Options{}`, plus the published wheel in a clean SQLAlchemy virtualenv and
the GORM discovery check on each platform. That public path cannot execute
before a real release; its implementation and negative checks are present, but
its first actual v0.3 public result remains a publication-time check. A smoke
failure must be reported without moving the tag or replacing assets. An old
v0.2 native bundle cannot satisfy the final v0.3 candidate's exact artifact
hash and consumer-behavior checks.

For this re-audit, the downloaded platform and aggregate records were checked
again against the local guard's consumer-evidence verifier, including source,
artifact hashes, harness identity, and evidence SHA256 binding. Focused
release-path tests passed (75 tests), and `scripts/verify.py check` passed (Go
tests/vet, Python 368 passed / 3 skipped, public-source and version checks).
The `v0.3.0` remote tag and GitHub Release did not exist when checked; release
preparation must check again before submission.

## Findings

Each remaining finding has one classification.

| Class | Finding / action |
| --- | --- |
| **REQUIRED BEFORE RELEASE** | Prepare canonical `v0.3.0` / Python `0.3.0`, release notes, README/install examples, current-release/project-status and maturity wording. Check tag and release uniqueness. Current public v0.2 references remain accurate until publication. |
| **REQUIRED BEFORE RELEASE** | Freeze the resulting exact release-preparation SHA and run full macOS/Ubuntu candidate acceptance and aggregate guard for **that SHA and v0.3.0**. The `fb1dfff` verify rehearsal and earlier branch acceptance cannot be reused as final-version `READY`. |
| **DOCUMENT** | The ordinary `check.yml` workflow still uses an accepted alpha.2 guest for its development check. It is not evidence of current v0.3 guest behavior; the exact-candidate Release CI run is authoritative. |
| **DOCUMENT** | First Go startup downloads the exact native bundle unless it is already verified in cache or an explicit override is used. Development builds need an explicit matching bundle; Python's supported installation channel remains GitHub Release wheels while PyPI recovery is pending. |
| **DOCUMENT** | Per-isolated-DB memory remains substantial and latency depends on hardware. Small ORM workloads have not established a Snapshot/Fork speed advantage. The public v0.3 smoke can only run after publication. |
| **DEFER** | Larger migration-heavy workloads, additional framework/version matrices, dbt, broader OS/architecture support, and CoW/runtime/VFS/sharing work belong to v0.4 or later investigation. |

The previous two `BLOCKER` findings are resolved in the release pipeline. No
current correctness or distribution blocker was found in this re-audit.

## v0.3 release verdict

**READY AFTER RELEASE PREP**

### Blocking items

None identified.

### Release preparation checklist

1. Finalize `v0.3.0` metadata, release-facing documentation, and notes; verify
   the tag/release are unused and run normal release-preparation checks.
2. Commit and push the focused preparation, then use its exact remote SHA for
   full two-platform Release CI acceptance and aggregate `READY`.
3. Only after that same candidate is `READY`, let the authorized release
   workflow tag and publish its accepted bytes, then run public Go/GORM and
   Python/SQLAlchemy smoke on both platforms. PyPI is not required.

### Deferred backlog

ORM workloads beyond the tested SQLAlchemy/GORM suites, dbt, broader platforms,
and memory/storage/runtime architecture exploration remain outside v0.3.
