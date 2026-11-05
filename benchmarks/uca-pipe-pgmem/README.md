# Go Pipe comparison after prepared UCA adoption

2026-11-05. Single Apple M1 / 16 GiB / macOS 27.2; Go 1.27.3, CGO=0, GOMAXPROCS=8, GOGC=100. New measurement cohort, not a relabeling of previous results.

**Conclusion:** Pipe reduces connection and SELECT latency, but these three-process cells do not establish a batch-wall improvement. The adopted UCA candidate uses less batch CPU and has shorter typical Fork latency than published 0.6.2 on the same Pipe route. Compared with pgmem Pipe, candidate batch wall remains about 2.0x / 2.3x at P4 / P8; its sampled batch RSS is lower.

[Open standalone graph](report.html). [24-process CSV](results.csv). [Summary](summary.json). [Input identities](inputs.json).

## Results

Times are milliseconds. Batch wall: median [min–max] of three fresh processes; other columns: median of three per-process values. Fork is the median of each process's 48 child elapsed times. CPU is total batch user+system across threads, not exclusive Fork CPU. RSS is sampled process peak during the batch, not retained-child memory.

| Route | P | Batch wall ms [range] | Batch CPU ms | Fork p50 ms | Cleanup p50 ms | Peak RSS MiB | SQL >100ms /144 |
|---|---:|---:|---:|---:|---:|---:|---:|
| mariamem 0.6.2 / Pipe | 4 | 787.3 [755.0–804.9] | 3434.5 | 46.0 | 8.6 | 372.5 | 0 |
| UCA candidate / TCP | 4 | 618.6 [615.5–640.8] | 2778.7 | 33.5 | 8.7 | 365.3 | 0 |
| UCA candidate / Pipe | 4 | 720.4 [601.5–1303.4] | 2892.2 | 33.1 | 8.8 | 360.5 | 1 |
| pgmem 1.18.2 / Pipe | 4 | 359.8 [331.5–451.6] | 1257.4 | 14.3 | 0.2 | 963.2 | 0 |
| mariamem 0.6.2 / Pipe | 8 | 951.0 [604.9–1003.9] | 3777.7 | 60.7 | 13.4 | 640.6 | 3 |
| UCA candidate / TCP | 8 | 881.4 [582.6–1083.5] | 3102.0 | 54.0 | 11.0 | 664.4 | 4 |
| UCA candidate / Pipe | 8 | 880.6 [528.2–1315.3] | 3116.1 | 51.6 | 13.7 | 657.2 | 3 |
| pgmem 1.18.2 / Pipe | 8 | 383.2 [374.6–388.6] | 1366.5 | 26.2 | 1.0 | 975.6 | 0 |

## Interpretation

- Candidate Pipe versus 0.6.2 Pipe: median batch wall −8.5% at P4 / −7.4% at P8; CPU −15.8% / −17.5%. Typical Fork 46.0→33.1 ms at P4; 60.7→51.6 ms at P8. Paired round wall changes have mixed signs, so do not claim a stable wall-speedup percentage.
- Candidate Pipe versus the same candidate TCP: connect p50 1.96→0.54 ms at P4, SELECT 0.462→0.137 ms. At P8, connect 5.31→1.57 ms and SELECT 0.802→0.195 ms. Median batch wall is +16.4% at P4 and effectively unchanged at P8. This workload is dominated by Fork/cleanup and occasional long SQL, rather than connection setup alone. This is an observation, not attribution of every delay.
- Candidate Pipe P4 includes one 798.9 ms SQL span (batch 1303.4 ms); all observations are retained. Long SQL also appears in TCP P8, so it is not unique to Pipe. This experiment does not identify its internal cause.
- pgmem has shorter typical Fork and cleanup; mariamem has faster connection setup in this workload. Different engines, drivers and SQL protocols remain. This is a product/workload comparison, not a pure transport or engine experiment.
- No significance claim, CPU-optimal parallelism claim, or cross-platform acceptance: n=3 processes/cell on one Mac. No new product decision follows automatically.

## Measurement boundary and correctness

1,000 integer rows; 48 independent children per process; P4/P8 workers and explicit Snapshot cap equal to P for both products. Every child checks SELECT 1, pristine COUNT/SUM, updates one row, checks its value and closes its connection/database. Later children must see the pristine baseline. Root is closed before the batch. Batch includes child connection retirement and disposal, but excludes root preparation, capture and final Snapshot close. Maria retirement includes WaitDisconnected; pgmem has no identical API step. Driver defaults remain mysql 1.9.3 and pgx 5.11.0 (including its default statement behavior).

One excluded warmup per cell; three ordinary processes per cell with rotated variant order and alternating P order. All 24 ordinary processes (1,152 children), eight warmups and four positive pilots pass SQL/isolation/cleanup checks. Four wrong-seed negative controls fail the intended oracle and clean up. Active-child interval checks confirm the cap. No sample is removed. RSS sampled every 20 ms using Darwin libproc; sampler checked against ps. External process-wall measurements additionally include root/final cleanup and observer handshake/poll overhead; they are in CSV but are not pure application E2E timings.

**Pipe scope:** SQL uses the in-process DialContext route. Normal mariamem Start/Fork still creates a TCP listener. This does not measure eliminating listener creation.

## Identities and reproduction

Measured harness commit: `e0cbbb08829612d5567221a1e31c9c8386577dfe` (parent candidate `1862f4a89397bddfa1820d835106d3437a438cf7`). Harness adapted from `d10cfa8fb810b512333bcfa8b9d661493325478e`: enable Maria Pipe and set explicit cap P; workload SQL/oracles unchanged. Actual replaced library sources and annotated tag identities are pinned separately in inputs.json; binary vcs.revision identifies the harness, not the replaced libraries. Sources were clean and checked with scripts/git_identity.py before build. Both mariamem versions use MariaDB 12.3.3, with different guest build identities.

Exact observations and original build/collector/reducer scripts are retained compactly in receipts.zip; they are not automatically proposed for main. Extract the ZIP into an empty directory and run `python3 analyze.py --check` there to verify summaries without temp/build trees or file writes. SHA256SUMS.json covers published artifacts. To rerun measurements, recreate the disposable workspace layout recorded in plan.json and the original build.py/run.py, using the clean measured harness commit and product pins. Rebuild all three binaries under the recorded Go toolchain; do not run the collector from the later report commit (its source guard intentionally rejects that). New timings are new observations. Published module/build-info paths replace the workspace prefix with <WORKSPACE>; original and published hashes are both retained.

No product/API/runtime changes, CI submission, main merge or release in this task.
