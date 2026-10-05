# v0.4.2 production candidate: disposable memory lifecycle

The controlled pure-memory32 + mmap runtime is ready for release preparation. It is not merged, tagged, or published. Version metadata remains 0.4.1 until the release-preparation decision. The released guest, SQL behavior, Snapshot/Fork implementation, and explicit legacy path are unchanged.

Runtime tested: `b14cacf359927bae5c9bdfbf6bd02952ce8b7f4c`. Start: released v0.4.1 (`547fb1a6c01e5edb0daa27de273a2e94e66eb098`). The final evidence commit adds benchmark mechanics/documentation only; runtime/recipe identity is checked against the tested commit.

- Semantics commit: `fda33d6e4dea1b5202ae0fb8437014f85d814985`.
- mmap commit: `281c37c120b7626f83191180739523ef8262d1a5`.
- [Native acceptance CI](https://github.com/masahitojp/mariamem/actions/runs/37309731622): macOS 15 arm64 and Ubuntu 24.04 x86_64, both PASS.
- [Compact measurements](v042-production-evidence/summary.json), [per-generation CSV](v042-production-evidence/generations.csv), and [checksums](v042-production-evidence/SHA256SUMS).

## Contract and implementation

The shared guest declares initial 4096 WASM pages (256 MiB), maximum 32768 pages (2 GiB). Generated pure-memory32 code uses a flat base pointer; grow must not relocate it. The candidate reserves one 2 GiB anonymous private PROT_NONE range, makes the initial logical region read/write, and enables additional OS-page-aligned ranges with mprotect before publishing MemSize. New anonymous pages are OS-zeroed. It neither allocates a 2 GiB Go backing array nor commits 2 GiB of physical RAM up front. MAP_PRIVATE shares the same mapping across this instance’s Go workers; there is no OS-process fork/CoW feature.

The generic converter rules zero-extend the dynamic memory32 address, add the static offset without 32-bit wrapping, include the actual access width, check logical MemSize, and enforce atomic alignment. SSA retains potentially trapping loads even if their values are unused. Scalar/SIMD/atomic/RMW use the shared rules; no individual generated function or address was patched.

WASI memSlice/readCStr/memSlice64 and AccessMemory see logical-length/capacity views, so imports cannot touch the protected future range. The common host adapter also calculates slice ends in uint64 at the 2 GiB boundary. The mmap owner retains the original full slice for Munmap, serializes grow/Close, and releases only after cooperative worker join. A failed unmap retains ownership in a retryable error instead of claiming release.

The semantics commit changes 41 files; its large generated diff is mechanical (942,355 additions / 929,475 deletions), with generated pN files identical to the controlled-traps evidence base. The mmap commit changes 23 files (822 additions / 26 deletions), including tests/recipe/provenance; pN files are unchanged from the semantics commit. Handwritten owner/grow/lifetime changes are bounded. Guest/WASM/source notices remain pinned; release source/license closure must be rebuilt for the final release SHA.

## Correctness and platforms

Both native platforms pass the 2,472-case immutable fixture matrix (1,693 expected traps), plus grow/max/failed-grow cases. Coverage includes scalar signed/unsigned/floating loads/stores, SIMD full/lane/splat accesses, atomic load/store/RMW, offset overflow, boundary crossing, dropped trapping loads, old-data preservation/zero fill, initial logical bounds and stable base. Mapped fixtures and real runtime tests cover shared-worker visibility, futex/TLS, max-end host imports and controlled host-surviving guest traps.

Focused runtime race tests, SQL/CRUD, auth/reconnect, multiple sessions, Snapshot/Fork, retained closed handles, repeated Start/Close and failure paths pass. Each platform passes an external Go module consumer and an installed wheel, with GORM 32 cases and SQLAlchemy 44 cases. These are real Ubuntu/macOS executions, not cross-compilation. Linux accounting uses RSS/PSS; macOS uses RSS/physical footprint.

Ownership tests cover reserve/protect failure, partial generated initialization panic, failed startup/restore, controlled root/worker failure with peer join, repeated/concurrent Close and release-error retry. Lifecycle measurement releases all 850 created mappings, with zero active mappings or release failures after every group. Non-cooperative root/worker forced termination is outside this guarantee.

Independent regeneration matches every checked-in generated/runtime byte, including ownership glue and tests. Repository checks pass (Go tests/vet; Python 451 passed, 6 ordinary-check skips; public-source check). The consumer build-jobs adjustment also passes 27 focused release-tool tests.

## Disposable lifecycle

MacOS arm64, Go 1.26.8, no forced GC. Fresh lifecycle: Start, create/insert three rows, COUNT/update, Close. Snapshot cycle: fresh Start/use, Snapshot, source Close, Fork/use, child and snapshot Close. Ready below is whole pre-Close cycle time; CPU includes all creation/use/Close and excludes the OS-counter subprocess. Values are the last ten generations’ medians.

| Case | Ready ms | CPU s / DB or cycle | Close ms | HeapAlloc MiB | RSS MiB | Physical MiB | FD / goroutines |
|---|---:|---:|---:|---:|---:|---:|---|
| v0.4.1 1×50 | 311.1 | 0.2557 | 3.2 | 2199.2 | 2738.2 | 4331.8 | 5 / 1 |
| Controlled heap 1×50 | 338.5 | 0.2771 | 6.4 | 2199.1 | 2174.7 | 4342.4 | 5 / 1 |
| mmap 1×50 | 60.2 | 0.0635 | 6.7 | 151.1 | 398.8 | 299.5 | 5 / 1 |
| mmap 1×100 | 60.8 | 0.0640 | 6.6 | 151.2 | 319.3 | 270.3 | 5 / 1 |
| mmap 4×50 | 88.8 | 0.0876 | 11.5 | 603.3 | 1310.6 | 1239.0 | 5 / 1 |
| mmap 4×100 | 132.5 | 0.1027 | 10.8 | 603.0 | 1254.8 | 1134.4 | 5 / 1 |
| v0.4.1 Snapshot cycle ×20 | 1137.0 | 0.9747 | 8.8 | 2060.9 | 2568.9 | 4532.0 | 5 / 1 |
| Controlled heap Snapshot cycle ×20 | 1156.0 | 1.0174 | 11.4 | 2060.9 | 2227.8 | 4539.2 | 5 / 1 |
| mmap Snapshot cycle ×50 | 561.1 | 0.5757 | 9.2 | 429.7 | 752.7 | 566.0 | 5 / 1 |

FD stays at 5 throughout; goroutines are normally 1 with isolated samples at 2, returning to 1 rather than accumulating. The table reports medians.

1×100: ready 60.6 → 60.8 ms, CPU 0.0635 → 0.0640 s, first/last ten medians. Compared with controlled heap’s settled 1×50, ready improves about 82% and lifecycle CPU about 77%. Snapshot-cycle ready improves about 51% and CPU about 43%; the source and child mappings are both released. Close adds a few milliseconds versus released heap, in exchange for prompt linear-memory reclamation.

The first 4×50 run stopped on a conservative first-to-last RSS-growth heuristic: latency/CPU/HeapAlloc/FD/goroutines were stable, but Go arena capacity grew during warmup. This is preserved as a stopped run, not relabeled PASS. In a separate bounded 4×100 follow-up, generations 61–80 versus 81–100 differ by only 32 KiB RSS / 6.55 MiB physical footprint (64 MiB tail-growth threshold); heap allocation and counters plateau. No GC/FreeOSMemory or runtime tuning was added.

## One canonical three-way campaign

Unchanged v04_candidate fixture/workload: 30 fresh trials, 1,000-row prepared COUNT, scaling ×1/4/8/16, 10 measured groups per size where completed. CPU/memory use a separate 30-trial fresh-resource probe. ORM uses the unchanged CRUD dogfood workload, three balanced rounds of 10/50/100 Start/Fork cases; only its stale installed-version assertion is corrected generically. Compilation, wheels and dependencies are prepared outside timing. Go 1.26.8, macOS 27 arm64, 8 CPUs / 16 GiB RAM.

| Metric (p50) | v0.4.1 | Controlled heap | Controlled + mmap |
|---|---:|---:|---:|
| Start → SQL ms | 41.97 | 54.27 | 52.20 |
| Start → 1,000 rows ms | 58.26 | 75.63 | 63.46 |
| Fork → COUNT ms | 111.77 | 125.01 | 122.07 |
| Snapshot ms | 383.46 | 373.95 | 374.87 |
| Fresh ready CPU s | 0.0458 | 0.0633 | 0.0614 |
| ×1 readiness ms | 112.43 | 123.30 | 122.42 |
| ×4 readiness ms | 402.44 | 339.55 | 156.33 |
| ×8 readiness ms | 559.66 | 461.65 | 276.45 |
| ×16 readiness ms | 983.33 | 852.94 | 563.29 |
| ×16 ready physical MiB | 4652.3 | 3667.8 | 1655.8 |
| ×16 after Close physical MiB | 4652.3 | 3667.6 | 442.9 |
| ORM100 start suite s | 35.53 | 46.92 | 12.86 |
| ORM100 fork suite s | 20.37 | 22.98 | 21.67 |

Fresh candidate Start→SQL adds 10.2 ms / 24% versus released v0.4.1; fresh ready CPU adds about 0.0156 s / 34%. Start→fixture adds about 5.2 ms / 9%; Fork→COUNT about 10.3 ms / 9%. Snapshot is approximately unchanged. The correctness tax mostly appears in the semantics-only state; helper inlining/translator optimization was not attempted. Fresh startup remains practically fast and sustained disposal is substantially cheaper.

Start→SQL p95 / ≥900 ms tails (30 trials): released: 1044.0 ms / 7; controlled-heap: 1058.7 ms / 10; mmap: 59.8 ms / 1. Existing ~1 s startup tails remain; a lower count in this single mmap campaign is not a tail-correctness fix or a guarantee. ORM100 Start timing is particularly affected by startup-tail frequency; Fork suite time is about 6% above released v0.4.1.

The released ×16 control exceeded the fixed 8 GiB physical budget (peak 8.34 GiB); it was stopped and not repeated. Valid scaling measurements retained: ×1/4/8 nine each, ×16 eight. Its p50/p95 use only completed trials and are budget-censored. Controlled heap and mmap complete all ten groups at every size; mmap ×16 after-Close footprint is about 443 MiB, compared with several GiB retained in heap controls. This limits exact uncensored comparison with v0.4.1, not the candidate correctness/platform gate.

## Budget, cleanup and limits

Each owned workspace has disk budget 8 GiB, minimum free disk 16 GiB, FD cap 256, process-tree RSS 6 GiB / physical 8 GiB, and bounded phase/workspace watchdogs. CPU is bounded per process (600/660 s in measurement); correctness tests keep their 180 s test timeout with a separate cold-build watchdog. Failed runs retain evidence. The guard demonstrably stopped excessive reference memory and cold consumer compilation; cold builds were serialized via build jobs, preserving runtime concurrency.

After checksummed benchmark binaries/wheels/metadata were preserved, the five completed canonical/lifecycle-control Git worktrees were removed with `git worktree remove`. Removed trees total 2.36 GiB; retaining 0.68 GiB of frozen artifacts yields about 1.68 GiB net reclamation. Shared Go cache, compact evidence, failed-run records, candidate and prior experiment branches/worktrees remain. Older temporary clones/venvs are retained for review rather than deleted automatically. [Cleanup receipt](v042-production-evidence/fanout-cleanup.json).

An early local worktree wheel had parent-repository VCS metadata and was rejected, not used as acceptance proof. The independent exact-source clone and both native CI targets pass clean-SHA wheel checks. Earlier harness/path/FD-observer failures and the multi-DB RSS heuristic stop are retained locally as failures; their missing measurements are not manufactured.

The existing practical/Testcontainers suite requires a legacy native bundle and Wasmer child PID, so it cannot honestly account for current in-process direct-link CPU/resource/cleanup. No new benchmark project or misleading legacy comparison was run. Adapt owning-process accounting/cleanup checks before using its fresh-vs-shared-schema-reset methodology for v0.4.2.

Known limits: guarantee is released pure-memory32 on macOS arm64 / Ubuntu 24.04 x86_64; memory64/unused backends, full shared-guest race adaptation, non-cooperative forced shutdown, CoW/Fork optimization and v0.5 guest work are excluded. Long lifecycle/canonical measurements here are macOS; Ubuntu provides native contract, race and product/ORM execution evidence. Go filesystem/metadata heap remains GC-managed and need not become zero immediately after Close.

## Human decision

Recommend the smallest v0.4.2 integration: review the separable semantics and owner/grow commits, retain deterministic/failure-path tests and provenance, and accept the bounded fresh correctness cost for the sustained disposal/reclamation benefit. No broad translator or memory architecture redesign is indicated by these results.

No runtime correctness/platform/ownership/lifecycle blocker remains in this validated scope. Before release: human integration approval, canonical version 0.4.2 plus concise notes, and exact-final-SHA Release CI verify with corresponding-source/NOTICE/licenses/provenance and consumer artifacts. Tag/publish remains a separate authorized step. The practical-harness gap and censored old control are disclosed measurement limits, not silent release gates.

V0.4.2 CANDIDATE READY FOR RELEASE PREP
