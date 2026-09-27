# Prepared-key restore-copy attribution

## Evidence and condition

Run [36291032684](https://github.com/masahitojp/mariamem/actions/runs/36291032684), successful retry, measured source `c499e07bfe0221d757e219b575720f39991be849`.
Go 1.26.8, Wasmer 7.4.2, MariaDB 13.1.0 embedded, 1,000-row fixture. macOS 15.7.9 arm64: 3 logical CPUs; Ubuntu 24.04.5 x86_64: 4 CPUs, kernel 6.17 Azure, glibc 2.39, SSE2 + SSSE3 AOT. Hosted machines are not equivalent hardware.

20 alternating measured pairs plus two warmup pairs per platform. Both conditions use prepared test RSA keys and the same within-call validation-reuse patch. `control` means restore diagnostics OFF; `reuse` means diagnostics ON in this run, **not a validation A/B**. Guest source and runtime configuration are identical between these two conditions.

Verification: independently recomputed the restore summary from all 20 ON raw reports on each platform; checked complete execution and 14 successful existing-key branch/public-key checks per report, stage clock validity, per-file/global byte reconciliation, and downloaded native manifest SHA against provenance. Artifact upload contains manifests/provenance and measurement JSON, not the native binary itself; AOT hashes below are recorded CI identities, not independently rehashed binary downloads.

Shared WASM SHA256: `cd980b88d997af2f83438419c6829cd5bca2c46e256c0f8e7a98e9e9a9cadee9`.
Mac AOT: `2e985e076ca60f6e0723f1e78bc2eecfdfc29985e4e08d5fb67c8f5f1f386bdb`.
Ubuntu AOT: `6d3f2d1e1b578793373068886d5ceeb832c1959a0af08d75414650f102503eae`.

## Source facts: the actual restore path

`Snapshot.Fork` validates snapshot inventory and native metadata, then host startup
launches Wasmer with the immutable snapshot directory mounted at `/snapshot-in`.
These host integrity checks are outside the guest restore timer. Wasmer mount setup
before guest main is also outside it.

Before `l4m_open`, guest `snapshot_copy("/snapshot-in/data", "/mariadb", 0)` recursively
uses `lstat`, directory creation/enumeration, exclusive destination creation, and
64 KiB `fread`/`fwrite` chunks. `/mariadb` is the guest's unmounted memory filesystem.
Source and destination streams are closed afterward. No explicit fsync is performed.
There is no additional Go-host per-Fork snapshot-copy loop. Snapshot export uses the
same routine in the opposite direction after shutdown; this probe records restore only.

## Instrumentation and measurement

The opt-in `restore_copy` member of startup JSON records monotonic wall time,
process and current-thread CPU, call counts and logical bytes for:

- directory/stat metadata and enumeration
- source open
- exclusive destination creation
- source reads, including the final EOF read
- destination writes
- source close
- destination close, including possible stdio flush

A bounded inventory records each file's size, inclusive file-copy wall time, and
operation counters/times. Overflow, invalid clocks or byte reconciliation failures
reject the measurement. Per-file inclusive time starts after `lstat`; metadata is
separately aggregated. Untimed bookkeeping and instrumentation appear in the total
minus exclusive-operation wall times, not in an invented runtime attribution.

Run via the existing guest-boundary workflow's `restore_attribution=true` input.
The canonical Go runner uses 1,000 rows and workers 1/4/8, 20 measured pairs and two
warmup pairs. Both conditions use the **same** existing test RSA keys and disposable
within-call validation-reuse patch. Existing auth checks require the enabled plugin,
loaded keys and matching public key, with no generation. Alternating control/probe
order measures instrumentation perturbation: control disables restore counters;
probe enables them. No expensive memory diagnostics are requested.

This source instrumentation changes the guest identity, requiring one WASM build
and platform AOT rebuild. Subsequent matching inputs can reuse verified immutable
artifacts. No production provenance is reinterpreted.

Raw pair JSON, lifecycle summaries and `summary.json.restore_copy` provide p50/p95,
raw per-DB observations, per-file rankings and CPU/call/byte observations for each
platform and concurrency. Artifacts remain ignored locally and are uploaded under
`initialization-<platform>-<candidate>`; `init-restore/` contains the results.


## Measured lifecycle and instrumentation perturbation

All latency cells are p50 / p95 milliseconds. Per-DB observations: 20 / 80 / 160 for workers 1 / 4 / 8; within-batch observations are correlated, not independent trials. Marginal percentiles must not be summed.

| Platform | Workers | Fork → SQL OFF | Fork → SQL ON | Restore OFF | Restore ON |
|---|---:|---:|---:|---:|---:|
| macos | 1 | 718.1 / 856.0 | 753.5 / 882.6 | 271.9 / 330.2 | 289.7 / 355.0 |
| macos | 4 | 1477.6 / 2134.0 | 1463.7 / 2209.4 | 568.5 / 834.8 | 628.4 / 993.5 |
| macos | 8 | 2906.1 / 3673.7 | 2783.2 / 3509.0 | 1013.3 / 1482.9 | 1100.5 / 1483.9 |
| ubuntu | 1 | 533.1 / 548.4 | 560.3 / 575.5 | 225.4 / 234.3 | 252.7 / 264.4 |
| ubuntu | 4 | 764.8 / 833.8 | 795.3 / 902.7 | 332.2 / 420.3 | 355.3 / 481.6 |
| ubuntu | 8 | 1289.3 / 1434.2 | 1367.1 / 1503.5 | 500.1 / 685.6 | 567.1 / 804.8 |

**Derived paired calculation:** median ON-minus-OFF restore differences, computed per pair (one per-batch median at parallelism), are macOS +20.3 / +23.6 / +55.6 ms and Ubuntu +28.7 / +40.3 / +65.9 ms. Fork differences are macOS +15.5 / −21.4 / −20.2 ms and Ubuntu +26.8 / +27.6 / +76.0 ms. Mac parallel end-to-end signs are noisy; they do not imply instrumentation speeds up Fork.

**Limitation:** the per-operation clocks are not negligible. Use OFF for end-to-end baseline, ON for attribution; do not subtract a median overhead from individual operation values. Mac OFF ×1 Fork is 718 ms here versus 485 ms in the previous run, and restore 272 versus 156 ms. Ubuntu OFF agrees much more closely with its previous run. Changed instrumented guest identity and hosted-run variability prevent causal attribution of that cross-run macOS difference.

## Measured restore-operation waterfall (diagnostics ON)

| Platform | Workers | Total | Read | Write | Metadata | Source open | Dest create | Source close | Dest close | Outside timed ops |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| macos | 1 | 289.69 / 355.01 | 147.84 / 171.79 | 121.28 / 164.17 | 1.91 / 3.43 | 0.49 / 0.75 | 0.28 / 0.42 | 0.68 / 0.96 | 0.05 / 0.13 | 15.15 / 17.99 |
| macos | 4 | 628.40 / 993.49 | 354.24 / 635.39 | 219.22 / 354.95 | 2.85 / 6.86 | 0.74 / 1.34 | 0.43 / 0.86 | 0.80 / 1.58 | 0.07 / 0.21 | 25.45 / 65.73 |
| macos | 8 | 1100.54 / 1483.94 | 716.12 / 996.61 | 274.25 / 547.18 | 2.74 / 6.61 | 0.74 / 1.42 | 0.44 / 0.92 | 0.76 / 1.53 | 0.07 / 0.17 | 25.25 / 59.96 |
| ubuntu | 1 | 252.74 / 264.36 | 204.08 / 214.00 | 33.37 / 34.31 | 1.04 / 1.09 | 0.18 / 0.21 | 0.21 / 0.24 | 0.09 / 0.10 | 0.04 / 0.05 | 13.35 / 14.10 |
| ubuntu | 4 | 355.33 / 481.57 | 287.70 / 413.13 | 44.30 / 50.10 | 1.49 / 1.83 | 0.26 / 0.34 | 0.33 / 0.54 | 0.13 / 0.24 | 0.06 / 0.12 | 19.68 / 23.65 |
| ubuntu | 8 | 567.06 / 804.80 | 482.42 / 723.67 | 52.17 / 63.04 | 1.61 / 3.78 | 0.28 / 0.85 | 0.34 / 0.78 | 0.13 / 0.29 | 0.06 / 0.13 | 24.28 / 33.31 |

**Measured fact:** read is the largest component and write the second on both platforms. Median per-sample read share grows macOS 51.3% → 58.6% → 69.3%, Ubuntu 80.9% → 80.7% → 85.9%. Directory creation/enumeration/open/close is small. The untimed residual includes clock/counter bookkeeping; it is not a runtime-init residual.

## CPU and concurrency

Cells: p50 / p95 ms process CPU; current-thread CPU in parentheses. CPU deltas surround synchronous operations; process CPU also includes other runtime threads.

| Platform | Workers | Read CPU | Write CPU | Total restore CPU |
|---|---:|---:|---:|---:|
| macos | 1 | 135.0 / 154.7 (74.1 / 85.5) | 121.1 / 164.2 (122.2 / 167.7) | 280.6 / 338.5 (213.4 / 269.3) |
| macos | 4 | 185.0 / 218.2 (104.1 / 125.3) | 175.0 / 229.2 (176.8 / 231.4) | 389.1 / 448.4 (307.2 / 359.7) |
| macos | 8 | 196.6 / 233.1 (111.5 / 135.7) | 153.2 / 200.0 (155.3 / 204.0) | 378.1 / 452.5 (292.0 / 352.2) |
| ubuntu | 1 | 176.7 / 186.4 (87.6 / 93.4) | 33.5 / 34.4 (33.6 / 34.6) | 225.1 / 234.4 (134.5 / 141.4) |
| ubuntu | 4 | 173.0 / 189.2 (81.9 / 93.1) | 41.8 / 44.7 (42.0 / 44.5) | 234.6 / 251.3 (141.2 / 153.3) |
| ubuntu | 8 | 167.7 / 192.8 (81.5 / 95.5) | 43.8 / 46.2 (44.0 / 46.4) | 230.9 / 255.7 (143.3 / 157.7) |

**Measured fact:** read wall grows macOS 148 → 354 → 716 ms while process CPU grows 135 → 185 → 197 ms. Ubuntu read wall grows 204 → 288 → 482 ms while process CPU stays ~177 → 173 → 168 ms. Write wall also grows, especially macOS, but read has the largest absolute growth.

**Inference:** substantial CPU-backed transfer/materialization work exists at ×1; concurrency adds scheduling/wait/contended-service time rather than proportionately more per-copy CPU. These observations cannot distinguish CPU scheduling from WASIX service waits or memory bandwidth contention. They do not demonstrate physical disk saturation. No expensive memory diagnostics were rerun; sampled CPU/RSS remains in raw benchmark JSON and is not per-stage memory attribution.

## Files and logical transfer

Every restored DB has 11 files and 4 directories; 2,227 reads (including 11 EOF reads) and 2,216 writes. Total logical bytes are ~144,885,816 (138.17 MiB), with a few bytes of small-file variation between trials. Source bytes equal destination bytes and inventory sizes in every measured ON sample.

| File | Size MiB | Byte share | Mac ×1 copy p50/p95 ms | Ubuntu ×1 copy p50/p95 ms |
|---|---:|---:|---:|---:|
| data/ib_logfile0 | 96.0000 | 69.478% | 194.77 / 242.68 | 177.16 / 186.52 |
| data/ibdata1 | 12.0000 | 8.685% | 25.82 / 38.40 | 21.08 / 24.72 |
| data/undo001 | 10.0000 | 7.237% | 17.66 / 32.12 | 17.66 / 19.74 |
| data/undo002 | 10.0000 | 7.237% | 21.36 / 30.32 | 16.68 / 18.14 |
| data/undo003 | 10.0000 | 7.237% | 21.45 / 37.58 | 15.77 / 17.69 |
| data/test/benchmark_rows.ibd | 0.1562 | 0.113% | 0.25 / 0.48 | 0.38 / 0.47 |

**Derived calculation:** redo, system tablespace and three undo files total exactly 138 MiB, ~99.87% of copied bytes. The 1,000-row fixture table is only 160 KiB. Redo is both the largest byte source and largest per-file elapsed interval; median per-sample redo time share is macOS 66.5% / 63.4% / 61.4% and Ubuntu 70.3% / 65.0% / 65.8% at ×1/4/8.

**Source fact:** the current routine transfers every byte; there is no sparse-extent shortcut. This does not prove that any contents may be omitted. Redo/undo semantics must be preserved. Smaller cache/plugin allocations are not part of this file-byte accounting.

## Conclusions, hypotheses and blind spots

- **Measured fact:** bulk reads, followed by writes, dominate; file-count metadata is not the dominant target. A handful of fixed InnoDB files dominate both volume and elapsed time.
- **Source fact:** the cold restore materializes host-mounted snapshot contents into the guest memory filesystem through 64 KiB stdio chunks. Host validation is outside this timer.
- **Unknown:** `fread` combines libc buffering, WASIX transfer/runtime servicing and host filesystem access. `fwrite` combines buffering and memory-filesystem work. No measured boundary identifies individual inner copies or physical I/O.
- **Unknown:** there is no demonstrated removable redundant copy. An unavoidable cold materialization and an avoidable boundary-transfer cost are different hypotheses.
- **Hypothesis:** reducing per-chunk host-volume service/transfer cost could improve both latency and concurrency. CoW/VFS could avoid bulk materialization, but these measurements do not yet justify choosing that larger architecture.
- **Unknown:** detailed attribution is perturbed by instrumentation. Previous macOS absolute numbers are not a directly comparable performance result. Clock anomaly investigation is deliberately deferred; the successful run passed validity checks.

## Recommended restore experiment

Run one disposable **source-boundary A/B copy probe**: copy the exact same snapshot inventory into a fresh memory-filesystem destination, comparing the current host-mounted source against an identical source pre-staged in the guest memory filesystem before timing. Keep bytes, chunk size, copy code and destination unchanged, verify source/destination hashes, and record pre-staging cost separately rather than claiming it disappears. This isolates host-volume boundary cost from the common destination materialization cost; it is an attribution probe, not a production optimization or VFS design.

## FAST tranche integration checkpoint

**Prepared RSA keys:** sufficient causal evidence exists to stop RSA attribution and consider a separate productionization task. Required acceptance: provisioning/lifetime/security policy, missing/corrupt-key diagnostics, actual authentication-handshake coverage (current startup retains grant bypass), and packaged Go/Python lifecycle, Snapshot/Fork, multi-client and interrupted-query cleanup on both platforms. The test-only key path is not merge-ready.

**Within-call validation reuse:** paired evidence supports a separate small productionization task. Required acceptance: explicit verified-identity ownership, mandatory native/snapshot integrity checks, mutable NativeDir/sidecar and failure-path tests, and packaged lifecycle/cleanup on both platforms. The read-only disposable probe is not a production cache. Neither change is integrated here.
