# v0.4.5 Infrastructure Stabilization & Product Measurement — Human Review

## Recommendation

**READY for Human Review; merge/release and Snapshot optimization remain unapproved.**
The six [audit decisions and inventories](https://github.com/masahitojp/mariamem/blob/d7b1c0f60591843b0e72327fba7c62d26b7a3ee4/docs/reviews/development-infrastructure-audit.md)
remain the primary input. Approved Decisions A/B are implemented in the existing
paths, with both-native fresh qualification and exact evidence authentication.
No guest upgrade, new feature, cache manager or Snapshot optimization is included.

## 1. Restored correctness coverage

Unique supported checks from `tests/integration.py` now have a maintained owner:
`tests/test_python_wire.py`, called by canonical `verify.py integration`.
Seven tests cover typed/null/binary/unsigned/date/decimal results and metadata,
affected rows and warning/error handling, packet/sequence behavior, recoverable
unsupported requests, connection/session cleanup and timeout/EOF boundaries.
They execute against the current guest, rather than surviving as unreachable code.
See [invariant-by-invariant coverage mapping](v045-wire-coverage.md) and
[P0 evidence](v045-p0-evidence.json). Unsupported forced-process diagnostics stay
historical; they are not a promised containment contract.

## 2. CI evidence and lifetime

Development selects verification from local changed inputs; it no longer downloads
14-day v0.4.4 Product artifacts. Missing/unknown diffs fail toward full checks and
integration. This is development verification, not reusable qualification.

The existing Product workflow now owns `runtime-qualification-v1`: macOS15 arm64
and Ubuntu24.04 x86_64, full canonical check/integration, authenticated exact source,
tree/modes, guest, commands, toolchain and artifact identities. Old receipts cannot
be read as this contract. Retention is 90 days for convenience; release reuse still
rejects unavailable/expired/invalid evidence. No silent downgrade or new competing
acceptance framework was introduced.

Final module/wheel qualification still executes external Go lifecycle, GORM32,
SQLAlchemy44 and installed pytest/xdist. Public smoke is publication-specific only
after downloaded source/wheel/host bytes and accepted READY/provenance identities
match. Unknown identity fails before consumers. These are retained future release
gates, **not newly executed artifact/publication claims** in this task.
See [responsibility migration and negative checks](v045-p1-runtime-artifact-migration.md).

## 3. Canonical workflow and consolidation

| Boundary | Entry/owner | Observed cost / limitation |
| --- | --- | --- |
| docs | wording/references; `verify.py check --scope docs` | seconds; no unchanged runtime |
| classified tooling/policy | named pytest owners or `verify.py check --scope python` | warm broad subset ~20 s pytest; cold prerequisites additional |
| SDK/ownership/VFS/SQL/build/unknown inputs | full `check` + relevant `integration` | cold native qualification below |
| native runtime proof | existing Runtime qualification workflow | exact source, both platforms; separate from artifact |
| final artifact/publication | existing Release CI and guard | retains final consumers; actual public bytes checked |
| measurement | existing OwnedPrepared capture/import/SQL + process counters | sequential identity-bound manual campaign; no automatic speed gate |

Live asset/statistics/resource helpers were extracted before migrating consumers;
ORM execution loops and result oracles share `consumer_acceptance.py`. Historical
native adapters with regression/import consumers remain until callers migrate;
similar names alone are not evidence of duplication. Old `practical_suites.py` /
competitive native/Wasmer orchestration is **HISTORICAL**, not the generated-Go
measurement entry. `_common.instance/probe/template` remain reusable lifecycle/SQL
parts; their old native-manifest environment wrapper is not used as current proof.
No new benchmark framework was made canonical.

AGENTS/development/Skills share boundary-first verification and disposable storage.
`git_identity.verify_go_binary` rejects wrong/dirty/missing/duplicate VCS stamps
before packaging or measuring. The pinned Go worktree stamping failure was caught
before measurement; a clean normal Git clone produced authentic binaries.

## 4. Qualification and reproducibility

Latest runtime/source qualification:
`34eaea1df86b57765a4d8b0840845a33d539065f`,
[run 37994377940](https://github.com/masahitojp/mariamem/actions/runs/37994377940),
both native jobs PASS, **705 tracked inputs** matching both receipts and Git.
[Authenticated identities, steps and commands](v045-measurement-native-qualification.json).
Prior `8a30e184890ba686caba65d1876aee829a4a178a` qualification remains
[separately attributed](v045-native-qualification.md), never relabelled.

| Latest cold CI boundary | Ubuntu | macOS |
| --- | ---: | ---: |
| check | 419.87 s | 587.54 s |
| integration | 622.94 s | 856.91 s |
| whole native job | 17m55s | 24m55s |

This is one observation including builds/tooling, not p50/p95 or startup latency.
Earlier P1 cold feedback was ~15m21s/~31m05s; these are different runs/sources,
not proof of a CI speedup. Development tooling-only feedback avoids those jobs.

Opt-in Snapshot diagnostics change the execution adapter. Its canonical installer
now reproduces the exact driver with pinned formatter; source inventory, handwritten
inclusion and provenance/license continuity checks pass. Historical license/host
audit evidence retains its original identity. See [repair and byte proof](v045-generated-driver-repair.md).
No fresh upstream source→WASM regeneration is claimed; guest/transpiled core inputs
are unchanged, and the actual release reproducible build gate remains required.

The later measurement harness source is `f0a06f4d0e39756fe7839783fc00dbcc2a8ca0c9`.
Its only delta from qualified source is `benchmarks/ownedprepared/main.go` and its
README, adding a real Fresh suite control and strengthening point-read oracles.
Library/SDK/host/guest bytes are unchanged. Its clean stamped binary was verified
and both modes actually executed. **Do not claim this new SHA itself received native
qualification, or relax strict release reuse rules for benchmark code.**

## 5. Snapshot characterization

Local macOS27 arm64, Go1.26.8/GOMAXPROCS2; sequential campaigns, no competing builds.
Three trace-disabled trials per size, 16 Forks/trial; one separate attribution trial.
Minimal/10/100 MiB refer to logical fixture payload, **not backing size**.

| Logical payload | Prepared bytes, approximately | Go public Snapshot median | Go Fork-ready p50/p95, 48 samples | Python import median | Python Fork-ready p50/p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| minimal | 138.1 MiB | 383.6 ms | 54.0 / 63.9 ms | 127.8 ms | 51.0 / 55.2 ms |
| 10 MiB | 157.0 MiB | 395.8 ms | 61.4 / 66.0 ms | 143.3 ms | 57.6 / 61.3 ms |
| 100 MiB | 262.0 MiB | 660.6 ms | 56.7 / 61.9 ms | 234.1 ms | 53.6 / 58.9 ms |

Python creation from an already-started imported child measured, one trial each,
temporary/persisted: 411/421, 489/505, 756/795 ms. Child startup is outside that
Snapshot timer; artifact provisioning is outside import. These boundaries cannot
be directly divided into a Fresh-preparation speedup. Three creation samples do
not support a robust p95. Repeated ~100 MiB COUNT ~280 ms remains SQL scan work.

Nested attribution, milliseconds, **within the same traced operation**:

| Interval | minimal | 10 MiB | 100 MiB |
| --- | ---: | ---: | ---: |
| public operation | 352.6 | 388.7 | 660.6 |
| host quiesce + export | 90.5 | 106.3 | 149.5 |
| export, nested inside host | 60.5 | 67.8 | 113.0 |
| source enumeration | 0.28 | 0.23 | 0.22 |
| source read + hash | 60.4 | 71.3 | 126.6 |
| copy | 72.8 | 62.9 | 117.6 |
| target enumeration | 0.18 | 0.20 | 0.20 |
| target read + hash | 60.7 | 71.8 | 130.8 |
| owned acquisition | 63.3 | 72.5 | 129.0 |

Enumeration/cleanup are small. Quiesce alone is not isolated from host scheduling,
request handling and export; residual subtraction is not a pure shutdown measurement.
Read and hash share streaming intervals, so storage and cryptographic CPU are not
separately attributable. Allocation-call intervals are small, but later page touching
may bear allocation costs. Nested totals must not be added twice.

Observed export/publish counters plus inspected owned acquisition imply nominal
**five logical full-data reads, two materializations and three hash passes** for
temporary creation. This is not five physical disk reads: cached pages, kernel copy
paths and filesystem semantics matter. Minimal state already includes 96 MiB redo,
12 MiB ibdata and three 10 MiB undo files. Complete valid owned state is structural;
this number of traversals is implementation-controlled, not a product requirement.

**Recommendation: defer optimization.** Combining final validation with retained-FD
acquisition may remove a traversal; 60–131 ms observed hash intervals are an upper
bound clue, **not an implemented/guaranteed speedup**. It requires a separate decision
and proof of exact-object/inventory/failure cleanup. Heavy preparation and repeated
SQL dilute its suite value. No integrity check was removed or weakened here.

## 6. Actual Fresh versus prepare-once crossover

Same deterministic data, point/count checks, real preparation/SQL/Close in both modes.
Median of three actual suites; alternating order. Serial product times omit diagnostic
counter subprocesses; full wall/CPU and all tails remain in raw evidence. Parallel
uses wall time, not summed overlapping operations.

| Payload | Tests | Fresh total | Prepare + Snapshot + Fork total |
| --- | ---: | ---: | ---: |
| minimal | 1 / 2 / 4 | 0.069 / 0.132 / 0.291 s | 0.464 / 0.525 / 0.656 s |
| minimal | 32 | 2.511 s | 2.635 s |
| 10 MiB | 1 / 2 / 4 | 0.619 / 1.256 / 2.540 s | 1.092 / 1.191 / 1.397 s |
| 100 MiB | 1 / 2 / 4 | 5.696 / 11.462 / 23.971 s | 6.510 / 6.809 / 7.821 s |
| minimal CRUD | 16 | 1.265 s | 1.567 s |
| minimal multi-connection commit/rollback | 16 | 1.280 s | 1.554 s |
| 10 MiB, multi-connection, 4 workers | 8 | 3.509 s | 2.038 s |
| 64 schema tables, minimal data | 4 | 0.364 s | 1.569 s |

10 MiB/2 tests has only ~5% advantage, not a universal crossover rule. At 4 tests
the gain is ~45%; 100 MiB/2 tests ~41%, at 4 ~67%. Minimal setup still favors Fresh
at the measured 32 tests. More tables alone did not make preparation expensive
enough here; approximately one-second tails appear in schema trials and are retained.
Choose based on actual migration/fixture work and reuse count, not the name Snapshot.

## 7. Bounded product controls and resources

Reused `_common.instance/probe/template` pieces and the public host override with
authenticated binary hash. Three trials, four databases/test operations per suite,
1000 rows ×32-byte data, independent connections observing a committed update and
a rolled-back delete. First-state point/count oracles reject previous mutation.

| Approach | Median complete suite | Isolation/reset responsibility |
| --- | ---: | --- |
| mariamem Fresh | 0.388 s | disposable database per test |
| mariamem Snapshot/Fork | 0.952 s | shared fixed baseline; disposable child per test |
| Testcontainers Fresh | 16.782 s | container/server/state per test |
| shared MariaDB + truncate/reseed | 4.041 s | user resets data; sessions/server state remain shared |

Includes startup/preparation, application SQL and cleanup; native counter probes
are included in these control wall times (unlike the primary Go product column).
Container image is pinned by actual ID/digests in raw evidence; all pulls/Reaper
setup outside timing. Native guest reports 13.1.0-embedded; container 12.3.3. No
guest change was made. Docker Desktop VM and three pre-existing containers introduce
noise; container-reset range 3.95–7.17 s. This is a conditional local observation,
not a general backend speed claim or equal-isolation comparison. Larger/parallel
cases above use mariamem only; they are not extrapolated container comparisons.

Separate ready seeded DB resource samples: native physical footprint 91.4 MB,
RSS 121.5 MB; Docker cgroup usage 143.4 MB, excluding the whole VM. Cumulative
native host CPU ~0.094 s, container CPU ~3.663 s include different startup scopes.
These are **not equivalent accounting or peak**. Primary Go suite CPU and before/
ready/closed/after counters are preserved; parallel simultaneous peak is not sampled.
Go benchmark FD5→6 is bounded lazy runtime initialization; all owned FDs return,
Python import FD counts return to baseline. The 64-table Snapshot retains ~137 FDs
and closes them. Native qualification remains the stronger failure/concurrency/
mapping cleanup proof, not these small performance controls.

## Scope, remaining limits and human action

Branches: `experiment/v045-infrastructure` and descendant `experiment/v045-measurement`.
Main stays released `8ede4ad65def07436b64801076004ff80aec0799`.
No active reuse intent, version bump, automatic merge/release or v0.5 work.
Review implementation/evidence now; actual final-artifact qualification remains
Release CI responsibility after approval. No coherent v0.4.6 theme is justified.
Snapshot traversal fusion, many-baseline FD pressure, hard-failure containment and
guest race redesign remain separate future questions, not additions to this release.

**Human question: accept this infrastructure/measurement candidate for v0.4.5
integration and subsequent release preparation, leaving Snapshot optimization deferred?**

Compact evidence: [raw measurements and selected traces](v045-measurements/measurements.json),
[crossover CSV](v045-measurements/crossover.csv), [checksums](v045-measurements/sha256.json),
and linked P0/P1/native reports above. Orchestration/commands, binary identities,
input SHAs, artifact manifests and dependencies are preserved in the JSON; replace
`<repository>` with a clean checkout root and recreate task-owned scratch. No
benchmark result depends on retaining database files, toolchain caches or binaries.
