# v0.4 production direct-link canonical baseline

**DIRECT-LINK CANONICAL BASELINE COMPLETE** — normal functional scope; not a tag, publication, full race acceptance or final release-readiness declaration.

## Source / environment

Measured source: `65f897358e1fc02aec4093ba9f474ede56ac1b54`; runtime: **direct-linked generated-Go**; branch `v0.4/generated-go-integration`.
macOS-27.0.1-arm64-arm-64bit-Mach-O; Apple M1 / 16 GiB / 8 CPU; `go version go1.26.8 darwin/arm64`; Python 3.14.7.
Historical reference: same hardware/toolchain, macOS 27.0 (26A428). Current OS: macOS 27.0.1 (26A434). The OS patch difference is an uncontrolled comparison caveat; boundaries/fixtures remain unchanged.
Compiled guest: `5a513f74607ef1f1ddd4a36ebeefbba50354d9d00564e1977475d642104903bb`. Fresh Python host SHA-256: `e2cb0e620e940e552ba41246b870cdf84fa3beeee9b4eafedb0e2cd2e58f1312`.
[Compact observations, hashes and comparisons](v04-direct-link-values.json); full raw logs/results are disposable ignored work data.
Runtime/Go harness source is committed at the measured SHA. The environment records a dirty tree because unrelated untracked npm metadata and new report tooling existed; neither participates in the measured runtime. No production/runtime implementation changed in this task.

## Production path / acceptance

`Options{}` → host/MySQL wire → `guest.startLinked` → fresh `generatedgo.StartInstance`, all inside the Go consumer. No guest executable decode/write/checksum, guest subprocess, NativeDir resolution, Wasmer discovery/download or native cache. Python uses one installed host executable with the guest directly linked; it is a separate distribution/API boundary.
Fresh per-DB linear memory, thread/TLS/FD state, MemFS and prepared writable state; consuming cold Snapshot and verified independent Fork. No live heap/worker restoration, process fork, new CoW or runtime sharing.

| Gate | Result |
| --- | --- |
| Go unit checks / scoped vet / generated provenance | PASS |
| Non-race core/protocol/auth/CLIENT_FOUND_ROWS/sessions/MaxSessions/reconnect | PASS |
| Repeated/concurrent independent DBs, normal shutdown | PASS |
| Empty PATH/cache default; Snapshot/multiple Forks/fixture/write/schema isolation/corruption | PASS |
| Focused FD/MemFS/prepared-file/thread/TLS/futex/runtime race tests | PASS |
| Installed-wheel SQLAlchemy | 44/44 |
| External GORM Options{} / repeated AutoMigrate | 32/32 |
| Full generated guest `-race` diagnostic | FAIL — known limitation, explicitly rerun; not a v0.4 gate |
| Python forced query-timeout reclamation diagnostic | FAIL — guest cleanup deadline; separate failure-containment scope, unchanged test retained |

Ordinary checkout Python checks: 388 pass / 3 skip; the publication-source test rejects unrelated user-owned untracked npm files. Six new scope/report tests pass separately. A managed Git checkout without those unrelated files passes the normal Go checks, scoped vet, generated provenance, Python checks (392 pass / 6 optional skips) and public-source scan. The user files were not changed.
The forced-timeout diagnostic does not pass and is not advertised as passing. Normal Close/session checks pass; arbitrary failure containment remains a separate decision. This report is the requested normal-path performance baseline.

## Method / reproduction

Run acceptance first, then each benchmark alone, with no tests/builds concurrently. No optimization or MariaDB configuration changes. No slow-run filtering, forced GC, OS-cache flush or shortened timeouts.
Startup: 2 warmups + 30 independent Go processes, each using the existing 1,000-row InnoDB fixture and public API. Start→SELECT 1 excludes schema/seed; Start→fixture includes them. Snapshot starts after disconnect acknowledgement and consumes its source. Fork→COUNT excludes base preparation and Snapshot.
Scaling: each ×1/×4/×8/×16 has 1 warmup + 10 independent processes, round-robin; isolated forks of a 1,000-row prepared Snapshot. G(0) is the post-preparation holder without live DBs; G(n) is the same owning Go process at all-ready.
CPU: G(0)→all-ready owning-process counters, including observer/version-query collection; excludes fixture preparation and teardown. Sampling: 50 ms + scan overhead.
Memory: historical canonical `primary_bytes` is macOS process-tree **physical footprint**, confirmed from the original report/helper; RSS remains separate. Incremental=(G(n)−G(0))/n. Immediate after-Close is measured before snapshot-holder process exit, with no forced GC; Go heap retention stays visible. OS physical accounting is not an exclusive allocation proof.
SQLAlchemy: unchanged v0.3 `test_03_update_commit_and_delete`, normal QueuePool, identical schema/seed/CRUD/relationship reads in Start and Fork. 10/50/100 tests × 3 suites/mode; base preparation/Snapshot/final cleanup included in Fork suite total. Installed-wheel Python+host boundary; not an in-process Go latency measurement.

```sh
GOTOOLCHAIN=go1.26.8 python benchmarks/v04_candidate.py --runs 30 --scaling-runs 10 --json /path/to/work/candidate.json
# installed host-only wheel, pinned SQLAlchemy/PyMySQL/pytest; no native override
/path/to/installed/python benchmarks/v04_orm.py --runs 3 --json /path/to/work/orm.json
python benchmarks/v04_direct_link_report.py /path/to/work/candidate.json /path/to/work/orm.json --acceptance /path/to/work/acceptance.json
```

## Canonical comparison

Each quantile is classified independently. ≤5% relative difference is “approximately unchanged”; this descriptive rule is not a significance test. Baseline values use full historical precision before rounding.

| Metric | Wasmer baseline | direct-link generated-Go | delta | verdict |
| --- | ---: | ---: | ---: | --- |
| Start → first SQL p50 (ms) | 308.5 | 42.7 | -265.9 (-86.2%) | improved |
| Start → first SQL p95 (ms) | 335.3 | 53.7 | -281.5 (-84.0%) | improved |
| Start → 1,000 rows p50 (ms) | 312.2 | 65.0 | -247.2 (-79.2%) | improved |
| Start → 1,000 rows p95 (ms) | 342.9 | 79.2 | -263.7 (-76.9%) | improved |
| prepared Fork → COUNT p50 (ms) | 288.7 | 126.2 | -162.5 (-56.3%) | improved |
| prepared Fork → COUNT p95 (ms) | 349.2 | 187.2 | -162.0 (-46.4%) | improved |
| Snapshot p50 (ms) | 404.6 | 490.0 | +85.4 (+21.1%) | regressed |
| Snapshot p95 (ms) | 473.3 | 592.1 | +118.8 (+25.1%) | regressed |
| ×1 group-ready p50 (s) | 0.284 | 0.112 | -0.171 (-60.4%) | improved |
| ×1 group-ready p95 (s) | 0.297 | 0.133 | -0.164 (-55.3%) | improved |
| ×4 group-ready p50 (s) | 0.428 | 0.604 | +0.176 (+41.2%) | regressed |
| ×4 group-ready p95 (s) | 0.477 | 1.081 | +0.604 (+126.7%) | regressed |
| ×8 group-ready p50 (s) | 0.860 | 0.690 | -0.170 (-19.8%) | improved |
| ×8 group-ready p95 (s) | 0.893 | 0.916 | +0.022 (+2.5%) | approximately unchanged |
| ×16 group-ready p50 (s) | 1.890 | 1.131 | -0.759 (-40.2%) | improved |
| ×16 group-ready p95 (s) | 1.982 | 1.427 | -0.555 (-28.0%) | improved |
| ×16 incremental physical / DB p50 (MiB) | 280.8 | 197.5 | -83.3 (-29.7%) | improved |
| ×16 incremental physical / DB p95 (MiB) | 283.0 | 320.8 | +37.8 (+13.4%) | regressed |
| ×16 total physical p50 (MiB) | 4501.3 | 4283.3 | -218.0 (-4.8%) | approximately unchanged |
| ×16 total physical p95 (MiB) | 4535.8 | 6255.4 | +1719.6 (+37.9%) | regressed |
| ×16 CPU p50 (CPU-sec) | 9.463 | 3.352 | -6.112 (-64.6%) | improved |
| ×16 CPU p95 (CPU-sec) | 9.654 | 3.502 | -6.153 (-63.7%) | improved |
| after Close physical p50 (MiB) | 11.8 | 4283.2 | +4271.4 (+36158.0%) | regressed |
| after Close physical p95 (MiB) | 12.3 | 6255.6 | +6243.3 (+50814.2%) | regressed |
| SQLAlchemy100 start p50 (s) | 39.012 | 35.649 | -3.364 (-8.6%) | improved |
| SQLAlchemy100 start p95 (s) | 39.016 | 36.482 | -2.534 (-6.5%) | improved |
| SQLAlchemy100 fork p50 (s) | 43.142 | 21.405 | -21.737 (-50.4%) | improved |
| SQLAlchemy100 fork p95 (s) | 44.037 | 21.523 | -22.514 (-51.1%) | improved |

## Startup distribution (ms)

| Boundary | n | min | p50 | p95 | max | ≥500 ms / ≥900 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Start→SQL | 30 | 38.4 | 42.7 | 53.7 | 62.0 | 0 / 0 |
| Start→1,000 rows | 30 | 58.3 | 65.0 | 79.2 | 185.3 | 0 / 0 |
| Fork→COUNT | 30 | 110.9 | 126.2 | 187.2 | 565.7 | 1 / 0 |
| Snapshot | 30 | 447.2 | 490.0 | 592.1 | 800.1 | 13 / 0 |

## Scaling / cleanup

| DBs | trials | ready ms p50/p95 | CPU-sec p50/p95 | incremental physical MiB/DB p50/p95 | ready physical MiB p50/p95 | ready RSS MiB p50/p95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 10 | 112.3 / 132.8 | 0.131 / 0.152 | 88.0 / 88.4 | 1211.1 / 1211.3 | 1248.2 / 1248.4 |
| 4 | 10 | 604.2 / 1080.9 | 0.927 / 1.419 | 552.3 / 1537.9 | 3331.0 / 7274.5 | 1819.3 / 2100.0 |
| 8 | 10 | 689.9 / 915.6 | 1.725 / 1.943 | 316.0 / 562.5 | 3650.7 / 5623.3 | 1906.1 / 2035.9 |
| 16 | 10 | 1130.9 / 1426.8 | 3.352 / 3.502 | 197.5 / 320.8 | 4283.3 / 6255.4 | 1850.5 / 2048.0 |

| DBs | G(0) physical MiB p50/p95 | peak physical MiB p50/p95 | after Close physical MiB p50/p95 | after Close − G(0) MiB p50/p95 |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 1122.9 / 1123.3 | 1211.1 / 1211.3 | 1211.2 / 1211.4 | 88.1 / 88.5 |
| 4 | 1123.0 / 1123.4 | 3331.0 / 7274.5 | 3330.9 / 7274.4 | 2208.9 / 6151.5 |
| 8 | 1123.0 / 1123.3 | 3650.7 / 5623.4 | 3650.5 / 5623.5 | 2527.5 / 4500.3 |
| 16 | 1123.2 / 1123.5 | 4283.3 / 6255.4 | 4283.2 / 6255.6 | 3160.0 / 5132.5 |

40/40 measured batches passed. Ready/after-Close process inventory is one owning process, no runtime descendants. Startup counter gaps: 42; not filled with zero, so sampled peaks may miss an edge. Normal lifecycle FD/goroutine checks pass; retained OS footprint does not distinguish live/reachable guest state, allocator retention and compressed-page accounting. No forced GC or long-lived heap soak was performed; the cause is not proved.

## Fresh Start resources — separate boundary

30 fresh independent processes, no prepared Snapshot/base. CPU ends at all-ready counter collection after first SELECT/version query. This is an extra observation, not a replacement for the prepared scaling boundary above.

| Metric | p50 / p95 |
| --- | ---: |
| CPU to ready (CPU-sec) | 0.047 / 0.092 |
| ready physical (MiB) | 90.8 / 102.5 |
| ready RSS (MiB) | 117.9 / 129.7 |
| after Close physical (MiB) | 91.2 / 103.2 |

## ORM suites

| tests | mode | suite s p50/p95 | setup s p50/p95 | per-test ready ms p50/p95 | CRUD ms p50/p95 |
| ---: | --- | ---: | ---: | ---: | ---: |
| 10 | start | 2.102 / 3.036 | 0.000 / 0.000 | 96.2 / 1105.3 | 6.4 / 8.6 |
| 10 | fork | 2.768 / 3.783 | 0.661 / 1.689 | 191.2 / 207.3 | 6.1 / 8.8 |
| 50 | start | 15.698 / 21.269 | 0.000 / 0.000 | 99.0 / 1124.6 | 6.4 / 11.1 |
| 50 | fork | 12.087 / 12.149 | 0.770 / 1.630 | 193.1 / 222.2 | 6.5 / 9.9 |
| 100 | start | 35.649 / 36.482 | 0.000 / 0.000 | 100.1 / 1122.7 | 6.5 / 10.8 |
| 100 | fork | 21.405 / 21.523 | 0.762 / 0.795 | 191.0 / 203.6 | 6.5 / 8.6 |

Three suite trials give a coarse tail estimate; individual slow trials remain in evidence. All 18 measured suites / 960 isolated tests completed; GORM 32 cases are compatibility acceptance, not a comparable 100-test performance suite.

## Known limitations / distribution / next bounded task

The full generated guest is not Go race-detector clean. The [scope investigation](direct-link-race-scope.md) recorded 5,373 reports / 149 conflict signatures / seven broad groups and concluded **GENERAL SHARED-MEMORY MODEL WORK REQUIRED**. No suppression, `//go:norace`, function/address patch or blanket atomic rewrite is used. Focused handwritten/runtime race gates remain enabled. Re-evaluate broader memory adaptation with the planned v0.5 MariaDB/WASIX/toolchain update.
Go1.27.0/1.27.1 arm64 remain unsupported because of upstream `LDPSW: constant is not in pool`; upstream fix `b3f5034b15a7a6f065e92d0617f7a473d5d9dcfa` has already built/run the unchanged consumer. No source/compiler workaround is used.
Normal Go needs no Wasmer/NativeDir/native download/cache or per-DB native executable provisioning. Generated Go is ordinary module/build input; WASM is build-time intermediate. Explicit legacy NativeDir/Wasmer compatibility remains intact.
Later cleanup candidates: encoded platform images in `internal/builtinruntime`, private-executable provisioning/checksum/cleanup, unused generated-guest CLI/spawn scaffolding and historical image metadata. Native bundle resolver/cache and Wasmer packaging metadata remain legacy fallback machinery; they are not all unconditionally removable. No broad packaging deletion was performed.
Performance regressions and the single highest-priority bounded follow-up are discussed below. No optimization is included in this measurement task.

## Regression confirmation / coarse phase attribution

Five separate observations use only existing stage timers, outside the canonical trials. They are coarse intervals, not exclusive engine/allocator attribution; medians from different trials must not be added.

| Interval | n | min / p50 / max (ms) |
| --- | ---: | ---: |
| snapshot_export_shutdown | 5 | 179.7 / 182.5 / 356.4 |
| snapshot_publish | 5 | 221.5 / 255.1 / 361.0 |
| snapshot_total | 5 | 469.3 / 528.0 / 670.4 |
| fork_snapshot_validation | 5 | 64.4 / 65.8 / 72.0 |
| fork_linked_execution_ready | 5 | 22.4 / 27.3 / 33.3 |

×4 group-ready regression also repeats across the two five-trial halves: p50 493.7 / 678.3 ms versus historical 427.8 ms. Existing per-worker scaling phase attribution was not enabled; no specific cause is claimed.

Snapshot regression repeats across both halves of the 30 independent trials: p50 482.2 / 513.0 ms, versus historical 404.6 ms. Slow runs are retained; max is 800.1 ms.
×16 physical totals range from 4280.6 to 6255.6 MiB; 10/10 immediate post-Close samples retain ≥95% of ready footprint. Prepared-holder G(0) p50 is 1123.2 MiB. These are repeat observations, not a claim that the OS counter identifies live allocations. No forced GC, reference clearing or runtime change improved the numbers.
RSS/physical accounting must not be conflated: historical ×16 RSS p50/p95 was 2827.5 / 3005.2 MiB, now 1850.5 / 2048.0 MiB. Physical p50 verdict: approximately unchanged; p95: regressed. Do not substitute the separate fresh Start figure for prepared ×16 per-DB footprint.

**Single highest-priority follow-up:** locally attribute allocation/reference lifetime and retained footprint introduced by prepared-files Snapshot preparation (the elevated G(0) footprint), then distinguish reachable state from Go allocator/OS retention before selecting a fix. Snapshot export/shutdown and publication are the existing coarse time boundaries. This is a bounded performance investigation, not another execution architecture; it is not implemented here. Fork itself improves in this canonical latency comparison.
SQLAlchemy start: 106/480 per-test ready observations ≥900 ms; 107 ≥500 ms.
SQLAlchemy fork: 0/480 per-test ready observations ≥900 ms; 0 ≥500 ms.

The known guest-side ~1s tail remains visible in the Python/host Start boundary. These trials were not individually traced to prove every slow sample is the same race; no claim that the tail was fixed.

**DIRECT-LINK CANONICAL BASELINE COMPLETE.** No performance optimization, tag or publication.
