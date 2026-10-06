# v0.4 integrated direct-link candidate: FD lifetime + cold-copy preallocation

Terminology note: “No CoW … is introduced” below describes the cold-copy
preallocation change, not absence of existing prepared-file OS CoW. Deferred
CoW means additional image/ownership mechanisms; see the
[current path audit](../docs/copy-on-write.md). Original measurements are unchanged.

**V0.4 INTEGRATED CANDIDATE COMPLETE** — local normal acceptance and one canonical campaign; no tag, publication or release-readiness declaration.

## Identity / acceptance

Pre-integration: `6940bf1ac3010a020c8a67cd366d9e26c42c4974`. Measured runtime: `57b5ed4f8c7148e553e23583516567ddb21052ad` on v0.4/generated-go-integration.
A: `cbad371b0591cade6ba84dd7aaff373408202bd0`; B source recipe: `1687465bcbaff74a334b3e89181c47e66478792c`; B generated-artifact integration: `57b5ed4f8c7148e553e23583516567ddb21052ad`.
Guest: `33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`; generated provenance: `ade34eabe1dfacba7182ff351a39f3f2f7f06bdd6e89556cf899a7cbc8ade867`.
Apple M1 / 16 GiB / 8 logical CPUs; ProductName:		macOS; ProductVersion:		27.0.1; BuildVersion:		26A434; go version go1.26.8 darwin/arm64; Python 3.14.7; dependencies {'mariamem': '0.3.0', 'SQLAlchemy': '2.0.54', 'PyMySQL': '1.2.3', 'pytest': '8.4.2'}.
Canonical source→WASM SHA matches the separately built lane B artifact, without experimental.patch. A fresh converter produces the identical entire input manifest/inventory. Repeated canonical generated-runtime installation is byte-identical, including provenance. Exact source/tool pins and build evidence are in release/generated-go-{inputs,translation,build}.json.
Handwritten runtime/FD/MemFS/thread/TLS/futex adapters are unchanged. Required image provenance is regenerated, not removed; those images are unused by ordinary Go startup.

| Acceptance | Result |
| --- | --- |
| canonical_check_clean_checkout | PASS; Go/vet/provenance, Python393 PASS/6 optional skip/public554 files |
| canonical_integration | PASS; focused runtime race, normal core/wire/default Snapshot/Fork, Python2/2 |
| fd_lifetime | PASS x3; retained closed handles six + Snapshot source, FD6→6 |
| sqlalchemy | PASS44/44 installed clean candidate wheel |
| gorm | PASS32/32 external Options{} including repeated AutoMigrate |
| snapshot_fork | PASS; fixture, multiple children, write/schema isolation, corrupt state, clean close |
| directory_fd_grow_truncate | PASS focused handwritten regressions |
| full_guest_race | KNOWN FAIL; not rerun, no suppression; deferred shared-memory model work |
| forced_query_timeout | KNOWN FAIL reclamation deadline; not rerun; unchanged separate containment limitation |

The original checkout retains unrelated user-owned npm files. Its publication allowlist rejects them. The exact measured commit passes canonical check in a managed clean checkout (393 Python PASS / 6 optional skips / public 554 files); no checker rule or user file was changed. Normal integration and held-FD regression run on the integration checkout. Python uses a clean-checkout installed host-only wheel. Linux image cross-compilation passes; native Ubuntu release acceptance is not claimed by this local campaign.

## Method

The original public API fixture/harness is unchanged. 2 startup warmups + 30 independent processes; 1 scaling warmup per size + 10 independent processes each for ×1/4/8/16, round-robin. SQLAlchemy 10/50/100 Start/Fork: 3 order-balanced suite runs, existing v0.3 CRUD fixture, preparation/Snapshot/final cleanup included. Go then ORM run sequentially with no competing heavy workload. No slow runs excluded.
sum owning process tree physical footprint on macOS (primary_bytes); RSS separately retained; incremental subtracts post-preparation G(0); immediate post-Close, no forced GC
sum owning process tree cumulative CPU delta from G(0) to all-ready counter collection; includes observer/version-query collection, excludes fixture/base preparation and teardown
Physical footprint is the historical primary counter; RSS is separate. Incremental=(G(n)−G(0))/n. No forced GC in the canonical path. Historical Wasmer OS 27.0 versus current 27.0.1 is an uncontrolled patch-level caveat; previous direct-link uses the same current OS. Classification: each p50/p95 independently, ≤5% approximately unchanged; descriptive, not a significance test.
Raw ignored results: $work/v04-integrated; exact digests and compact observations: [values](v04-integrated-values.json). A final report-only commit follows the measured runtime SHA and does not change its code.

## A. Wasmer → integrated candidate

| Metric (p50 / p95) | Baseline | Final | Delta absolute; relative | Verdict p50 / p95 |
| --- | ---: | ---: | ---: | --- |
| Start → first SQL (ms) | 308.5 / 335.3 | 38.4 / 593.7 | -270.2 / +258.4; -87.6% / +77.1% | improved / regressed |
| Start → 1,000 rows (ms) | 312.2 / 342.9 | 52.7 / 55.4 | -259.5 / -287.4; -83.1% / -83.8% | improved / improved |
| prepared Fork → COUNT (ms) | 288.7 / 349.2 | 104.6 / 251.6 | -184.1 / -97.6; -63.8% / -27.9% | improved / improved |
| Snapshot (ms) | 404.6 / 473.3 | 399.9 / 570.8 | -4.7 / +97.5; -1.2% / +20.6% | approximately unchanged / regressed |
| ×1 group-ready (s) | 0.284 / 0.297 | 0.103 / 0.107 | -0.180 / -0.190; -63.6% / -64.0% | improved / improved |
| ×4 group-ready (s) | 0.428 / 0.477 | 0.312 / 0.489 | -0.116 / +0.012; -27.0% / +2.5% | improved / approximately unchanged |
| ×8 group-ready (s) | 0.860 / 0.893 | 0.373 / 0.818 | -0.487 / -0.075; -56.7% / -8.4% | improved / improved |
| ×16 group-ready (s) | 1.890 / 1.982 | 0.574 / 0.775 | -1.316 / -1.206; -69.6% / -60.9% | improved / improved |
| ×16 incremental physical / DB (MiB) | 280.8 / 283.0 | 197.4 / 265.6 | -83.4 / -17.4; -29.7% / -6.2% | improved / improved |
| ×16 total physical (MiB) | 4501.3 / 4535.8 | 3664.7 / 4755.1 | -836.6 / +219.3; -18.6% / +4.8% | improved / approximately unchanged |
| ×16 CPU (CPU-sec) | 9.463 / 9.654 | 2.814 / 2.954 | -6.649 / -6.701; -70.3% / -69.4% | improved / improved |
| after Close physical (MiB) | 11.8 / 12.3 | 3665.4 / 4755.1 | +3653.6 / +4742.8; +30928.6% / +38601.5% | regressed / regressed |
| SQLAlchemy100 start (s) | 39.012 / 39.016 | 34.025 / 34.038 | -4.987 / -4.978; -12.8% / -12.8% | improved / improved |
| SQLAlchemy100 fork (s) | 43.142 / 44.037 | 20.430 / 20.705 | -22.712 / -23.332; -52.6% / -53.0% | improved / improved |

## B. Previous direct-link → integrated candidate

| Metric (p50 / p95) | Baseline | Final | Delta absolute; relative | Verdict p50 / p95 |
| --- | ---: | ---: | ---: | --- |
| Start → first SQL (ms) | 42.7 / 53.7 | 38.4 / 593.7 | -4.3 / +540.0; -10.1% / +1004.9% | improved / regressed |
| Start → 1,000 rows (ms) | 65.0 / 79.2 | 52.7 / 55.4 | -12.3 / -23.7; -18.9% / -30.0% | improved / improved |
| prepared Fork → COUNT (ms) | 126.2 / 187.2 | 104.6 / 251.6 | -21.5 / +64.4; -17.1% / +34.4% | improved / regressed |
| Snapshot (ms) | 490.0 / 592.1 | 399.9 / 570.8 | -90.1 / -21.3; -18.4% / -3.6% | improved / approximately unchanged |
| ×1 group-ready (s) | 0.112 / 0.133 | 0.103 / 0.107 | -0.009 / -0.026; -8.1% / -19.5% | improved / improved |
| ×4 group-ready (s) | 0.604 / 1.081 | 0.312 / 0.489 | -0.292 / -0.592; -48.3% / -54.8% | improved / improved |
| ×8 group-ready (s) | 0.690 / 0.916 | 0.373 / 0.818 | -0.317 / -0.098; -46.0% / -10.7% | improved / improved |
| ×16 group-ready (s) | 1.131 / 1.427 | 0.574 / 0.775 | -0.557 / -0.651; -49.2% / -45.7% | improved / improved |
| ×16 incremental physical / DB (MiB) | 197.5 / 320.8 | 197.4 / 265.6 | -0.1 / -55.2; -0.0% / -17.2% | approximately unchanged / improved |
| ×16 total physical (MiB) | 4283.3 / 6255.4 | 3664.7 / 4755.1 | -618.6 / -1500.3; -14.4% / -24.0% | improved / improved |
| ×16 CPU (CPU-sec) | 3.352 / 3.502 | 2.814 / 2.954 | -0.537 / -0.548; -16.0% / -15.6% | improved / improved |
| after Close physical (MiB) | 4283.2 / 6255.6 | 3665.4 / 4755.1 | -617.8 / -1500.5; -14.4% / -24.0% | improved / improved |
| SQLAlchemy100 start (s) | 35.649 / 36.482 | 34.025 / 34.038 | -1.624 / -2.443; -4.6% / -6.7% | approximately unchanged / improved |
| SQLAlchemy100 fork (s) | 21.405 / 21.523 | 20.430 / 20.705 | -0.975 / -0.818; -4.6% / -3.8% | approximately unchanged / approximately unchanged |

## Startup tails / scaling

| Boundary | min / p50 / p95 / max ms | ≥500 / ≥900 ms |
| --- | ---: | ---: |
| start_first_sql | 36.1 / 38.4 / 593.7 / 1051.3 | 2 / 2 |
| start_seeded | 50.7 / 52.7 / 55.4 / 55.9 | 0 / 0 |
| snapshot | 331.6 / 399.9 / 570.8 / 672.3 | 7 / 0 |
| fork_first_sql | 102.2 / 104.6 / 251.6 / 321.4 | 0 / 0 |

Start has two ~1-second trials; raw API-return timestamps place the gap before Start returns (1.042/1.050 s), with first SQL ~1 ms later. This is consistent with the documented guest-side tail shape, but the campaign did not enable direct wait/wake tracing, so no per-trial page-cleaner causal proof is claimed. No timeout, synchronization or MariaDB setting was changed. Fork p95 regresses versus previous direct-link, while both quantiles improve versus Wasmer. The two 15-trial halves have Fork p95 173.9/251.2 ms, so the upper-tail regression is observed in the whole campaign but stable repeatability is not established. Canonical Fork phase tracing was off. Post-GC diagnostic Forks have a different allocator/hash-walk boundary and are not used to attribute that regression. No repeat campaign or optimization was performed.

| DBs | G(0) physical MiB p50/p95 | ready physical MiB p50/p95 | ready RSS MiB p50/p95 | after Close physical MiB p50/p95 |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 505.9 / 506.1 | 593.9 / 594.1 | 631.2 / 631.5 | 593.9 / 594.2 |
| 4 | 506.0 / 506.4 | 4690.0 / 5776.5 | 4662.9 / 5076.7 | 4690.0 / 5776.4 |
| 8 | 505.9 / 506.3 | 3034.5 / 5007.1 | 3116.9 / 4993.1 | 3034.4 / 5007.0 |
| 16 | 505.9 / 506.4 | 3664.7 / 4755.1 | 3799.1 / 4653.5 | 3665.4 / 4755.1 |

## ORM suites (three runs/mode)

| Tests | Mode | suite seconds p50/p95 | preparation seconds p50/p95 |
| ---: | --- | ---: | ---: |
| 10 | start | 4.115 / 5.051 | 0.000 / 0.000 |
| 10 | fork | 2.493 / 3.333 | 0.628 / 1.455 |
| 50 | start | 20.624 / 21.499 | 0.000 / 0.000 |
| 50 | fork | 9.897 / 10.021 | 0.488 / 0.563 |
| 100 | start | 34.025 / 34.038 | 0.000 / 0.000 |
| 100 | fork | 20.430 / 20.705 | 1.506 / 1.592 |

The ×4 ready median regression versus Wasmer is removed; all four scaling p95 values improve versus the previous direct-link campaign, without proof assigning that improvement solely to preallocation; its p95 is approximately unchanged. All prepared-scaling immediate Close footprints retain ≥95% of ready footprint (see compact observations). This is still a resource concern. Preserve the prior **OS PHYSICAL ACCOUNTING DOMINATES** finding: large guest/FS Go objects become unreachable and diagnostic GC reduced live HeapAlloc approximately to zero. These counters do not prove exclusive active-DB bytes or a live-object leak, and they are not declared harmless/immediately reclaimable. Lower churn can alter allocator/OS accounting history; changed footprint/RSS is reported without a specific causal attribution.

## Snapshot allocation / phases

| Diagnostic metric | experiment before | experiment after | integrated diagnostic (n=5) |
| --- | ---: | ---: | ---: |
| total_alloc_mib | 914.83 | 278.17 | 278.17 |
| snapshot_ms | 459.20 | 384.69 | 440.30 |
| export_shutdown_ms | 171.05 | 97.73 | 102.67 |
| publish_ms | 209.39 | 208.61 | 202.26 |

The integrated diagnostic uses five fresh processes after the canonical campaign; GC/profile and checksum walks occur only after measured boundaries. Every diagnostic child fixture/write/schema/rollback/base-hash/shutdown/corruption check passes. Its small-sample latency must not replace the 30-run canonical Snapshot result. Phase medians are independent and do not sum to the API median. One integrated post-Snapshot diagnostic-GC inuse profile totals about 386.9 KiB sampled, with no dominant guest/FS allocation, supporting the prior ownership finding; it does not measure OS reclamation.
Known-size cold regular copy now pre-sizes its exclusive destination with existing ftruncate before the unchanged 64 KiB copy loop. Seven C lines, no global MemFS growth change. The prior ~775 MiB destination growth history is materially reduced: actual Snapshot TotalAlloc remains ~278 MiB versus ~915 MiB, matching the lane’s ~636 MiB sampled resize reduction. Publication is not optimized. Snapshot still owns ~138 MiB of cold on-disk data, not the exited guest/MemFS. No CoW, format/API change, ready-heap restoration or production GC/scavenging policy is introduced.

## Remaining scope / next decision

Highest-priority remaining resource issue is substantial and non-monotonic prepared-scaling/post-Close physical/RSS footprint. Attribution precedes any allocator/mapping change. Separately record Start’s sampled tail-frequency/p95 and Fork p95 versus previous direct-link as bounded future performance questions; do not infer a new synchronization bug or fix them here.
Generated-Go/direct-link preserves the measured startup/Fork/CPU/ORM Fork and normal Go distribution improvements: no per-DB executable provisioning, guest subprocess, Wasmer/NativeDir/cache dependency for Options{}. Legacy fallback and encoded images/provisioning/bundle metadata remain isolated; packaging deletion is deferred.
Deferred: immutable Snapshot backing/CoW, deeper Snapshot publish work, mmap linear memory, full shared-memory race adaptation, forced guest kill/failure containment, legacy Wasmer removal, Go1.27.0/1.27.1 arm64 workaround, and MariaDB stable-version migration. No mariamem compiler workaround is used; those arm64 versions remain unsupported pending upstream-fixed Go. No v0.5 work starts here.

**V0.4 INTEGRATED CANDIDATE COMPLETE**
