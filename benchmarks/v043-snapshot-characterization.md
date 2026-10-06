# v0.4.3 Snapshot/Fork characterization

Baseline `fa6ef5355ecb93f7e1cabbedf5caa74fe4210870`; Track B only. macOS arm64, Go1.26.8. No engine, guest, CoW or mapping optimization.

## Findings

Prepared files already use private file-backed mappings. Measured virtual/RSS accounting grows with prepared size × child count, while source tracing, live heap and physical deltas do not support an eager full private copy. File growth beyond mapped capacity does copy that individual file into a Go buffer; private-page writes and growth are different boundaries.

Fork readiness is dominated by mandatory snapshot inventory/hash validation, not mapping setup. The measured guest initialization portion is real but substantially smaller. Integrity validation cannot be called safely removable without a separate sound identity/ownership design.

Snapshot/Fork is a preparation-amortization feature: trivial tests favor fresh instances; moderate/heavy setup benefits after enough tests. This is synthetic fixture evidence, not a universal application crossover.

## Source path

`Database.Snapshot → host.finish(export) → guest shutdown/snapshot_copy → exportTransfer → snapshot.Publish/Validate`: snapshot data is copied through guest MemFS and disk during preparation; the Snapshot handle retains a path and options, not a ready heap.

`Snapshot.Fork → start → host.start → snapshot.ValidateTimed → guest.startLinked → generatedgo.StartInstance → base.MapPreparedFiles → generated.Start`: each child has independent FS nodes/FD offsets/linear memory. Prepared files use `syscall.Mmap(PROT_READ|PROT_WRITE, MAP_PRIVATE)` and mapping FDs close immediately. Within capacity, file writes change private pages; `resizeMemData` beyond capacity does `make + copy`. Linear mmap and prepared-file mappings are released after cooperative guest/worker join. No replacement CoW is introduced.

## Prepared-state scaling

Payload is additional user-table data. Baseline includes ~138MiB redo/system/undo files. All child COUNT checks and eight-row mutation checks succeeded. The matrix is one fresh-process cell per combination, with extra ×1/×4 replicas. Snapshot-to-live physical deltas subtract each process's own post-preparation/GC checkpoint; they are not exclusive active DB byte counts.

| Payload MiB | Actual prepared MiB | Children | Ready p50 ms | Group CPU s | Live heap MiB | Cumulative TotalAlloc delta MiB | Physical delta MiB | RSS delta MiB | Mapped-file dirty (rounded) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 138.08 | 1 | 115.10 | 0.132 | 12.7 | 13.4 | 75.8 | 84.5 | 4K |
| 0 | 138.08 | 16 | 463.07 | 3.004 | 197.9 | 208.1 | 1212.9 | 1319.1 | 676K |
| 0 | 138.08 | 4 | 144.69 | 0.602 | 49.7 | 52.4 | 268.7 | 332.5 | 452K |
| 0 | 138.08 | 8 | 220.12 | 1.503 | 99.1 | 104.5 | 500.0 | 662.0 | 452K |
| 100 | 262.02 | 1 | 202.30 | 0.664 | 12.8 | 17.8 | -60.6 | 200.1 | 1956K |
| 100 | 262.02 | 16 | 749.96 | 13.716 | 198.8 | 218.8 | 1187.7 | 3179.6 | 30.3M |
| 100 | 262.02 | 4 | 217.60 | 3.313 | 50.0 | 70.1 | 171.3 | 798.7 | 7044K |
| 100 | 262.02 | 8 | 376.24 | 6.664 | 99.6 | 107.1 | 489.0 | 1590.9 | 15.4M |
| 10 | 157.02 | 1 | 125.22 | 0.203 | 12.8 | 13.9 | 79.3 | 98.1 | 2596K |
| 10 | 157.02 | 16 | 493.70 | 4.379 | 198.4 | 209.6 | 1260.5 | 1535.0 | 43.7M |
| 10 | 157.02 | 4 | 151.00 | 1.094 | 49.9 | 54.4 | 297.9 | 387.1 | 10.2M |
| 10 | 157.02 | 8 | 256.03 | 2.281 | 99.4 | 105.6 | 578.0 | 770.2 | 22.1M |

COUNT does not guarantee consuming every payload byte (InnoDB clustered COUNT can traverse the same data pages). Four extra 100MiB ×1/×4 full CRC32 scan cells read every payload (104,857,600 bytes per child), all producing the same checksum sum `398567321190400`. At ×4, read-only physical footprint was 1169.6MiB versus 1089.8MiB for COUNT; RSS was 1758.8MiB. Shared clean file pages can appear repeatedly in RSS across mappings. These counters are not proof that all resident pages are private.

At ×16, RSS delta grows from ~1319MiB minimal to ~3180MiB for the 100MiB fixture, and file-backed virtual mappings scale with child count. This is real RSS/address-space amplification; it must not be described as flat memory. Live Go heap is ~198MiB for all three prepared sizes, rather than 16×prepared bytes, and physical deltas remain ~1188–1261MiB. Small mutations produce comparable results. This does not cover heavy file growth, hot buffer-pool residency, arbitrary workloads or unbounded concurrency.

FDs are 6 at baseline, 6+5×children live, and 6 after Close. After-Close goroutines are 2, of which one is this harness's resource watchdog (baseline was taken before its creation). After diagnostic GC, live Go heap returns below 1MiB. Natural post-Close Go allocator/physical history remains visible; no production GC or FreeOSMemory policy was added.

## Fork stages

Single-child read cells (main campaign; a replica exists for minimal/10MiB). Stages use one host clock; guest phases below use the guest clock independently. Ready includes the public API and excludes first query.

| Additional payload MiB | Fork ready ms | Snapshot validation ms | Prepared mappings ms | Linear setup ms | Generated enter → guest-ready frame ms | First COUNT/use ms |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 115.10 | 61.18 | 0.94 | 1.39 | 33.65 | 8.55 |
| 10 | 125.22 | 70.19 | 0.87 | 1.40 | 35.74 | 37.54 |
| 100 | 202.30 | 126.39 | 1.29 | 1.52 | 49.83 | 290.32 |

Validation hashes all prepared data once per Fork; logical read-byte counters preserve that work. Validation alone is ~53% of minimal ready and ~62% of the 100MiB ready in these cells. This is measured host work, not a demonstrated removable percentage. Other API/OS setup includes supported-platform validation and temporary-directory setup.

Existing bounded guest initialization diagnostics (two separate minimal cells, not the main matrix) measured server initialization ~35ms, InnoDB plugin ~11.4–11.8ms, and its runtime/open-recovery substage ~6.8–7.1ms. Most of the extra minimal Fork cost is not structural InnoDB recovery. Source/guest/generated identity remains unchanged. Linked guest diagnostics are copied from private MemFS after join because the original startup `ReadGuest` sees no disk diagnostic at ready.

Traced minimal read Forks were 115.10/115.83ms versus an untraced read control 116.01ms; untraced mutation was 115.56ms. 10MiB traced read 125.22/127.28ms versus untraced 125.98ms. Small sample noise prevents claiming zero instrumentation tax. Checkpoints, GC, vmmap and compact JSON serialization happen outside timed operation intervals. Concurrent child CPU intervals overlap; use group CPU, not their sum.

## Suite crossover

Fresh includes Start + fixture/setup + test + Close for every test. Fork includes prepare Start + fixture/setup + Snapshot once, then Fork + test + Close per test and Snapshot.Close. Paired fresh runs precede Fork runs, with diagnostic GC between paths; this ordering and synthetic sequential suites are limitations.

| Additional payload MiB | N | Fresh suite s | Snapshot/Fork suite s | Faster path |
| --- | --- | --- | --- | --- |
| 0 | 1 | 0.066 | 0.533 | Fresh |
| 0 | 4 | 0.296 | 0.958 | Fresh |
| 0 | 8 | 0.602 | 1.456 | Fresh |
| 0 | 16 | 1.196 | 2.476 | Fresh |
| 10 | 1 | 0.629 | 1.214 | Fresh |
| 10 | 2 | 1.275 | 1.356 | Fresh |
| 10 | 4 | 2.539 | 1.742 | Fork |
| 10 | 8 | 5.119 | 2.363 | Fork |
| 10 | 16 | 10.271 | 3.755 | Fork |
| 100 | 1 | 5.815 | 6.691 | Fresh |
| 100 | 2 | 11.495 | 7.193 | Fork |
| 100 | 4 | 23.364 | 8.198 | Fork |
| 100 | 8 | 46.977 | 10.201 | Fork |
| 100 | 16 | 96.036 | 14.274 | Fork |

Observed crossover: none through N16 for trivial schema/light CRUD; 10MiB fixture loses at N2 and wins at N4; 100MiB wins at N2. N16 heavy preparation is 96.04s fresh versus 14.27s Snapshot/Fork (~6.7×). Moderate fixture is 10.27s versus 3.76s (~2.7×). Snapshot does not make trivial tests cheaper.

Parallel scaling is covered by the live-child ×1/4/8/16 matrix, not by a second parallel suite campaign. Larger prepared states/mutations were deliberately omitted; the requested maximum matrix fits the guard.

## Budget, evidence and limitations

56 accepted fresh-process cells completed; no guard violation. Minimum free disk 12GiB, owned disk budget4GiB, process RSS/physical ceiling8GiB with 250ms sampling. The continuous guard does not retain its peak; compact evidence records the maximum checkpoint counters. A sampling ceiling is not a kernel hard limit. Existing expensive Go caches are shared and preserved; temporary snapshots closed successfully. The initial sandbox-denied `ps` cell and exploratory smoke are excluded from accepted numeric tables.

Evidence: [compact values](v043-snapshot-characterization-values.json), [raw checksum inventory](v043-snapshot-characterization-checksums.txt), [reusable harness](snapshotcharacterization/README.md). Raw compact JSON, traces and vmmap summaries remain in `/private/tmp/mariamem-v043/track-b/evidence`; disposable binaries are in its `temp`. Hashes preserve file identity but do not substitute for ownership attribution.

Correctness checks for observational changes: focused generatedgo/guest tests, timing race tests, scoped vet and Python compilation. No canonical benchmark, Linux performance claim, runtime optimization or release was performed.

Recommendation: retain existing prepared-file sharing; use the measured fixture crossover to choose fresh or Fork. Any future latency work should first prove a bounded integrity-preserving validation design, rather than assume a new CoW layer or structural InnoDB rewrite is necessary.
