# Host-mounted versus guest-memory restore source

## Condition and source facts

This is a disposable probe on `experiment/prepared-auth-keys`, not a production
restore optimization. Completed run [36296436362](https://github.com/masahitojp/mariamem/actions/runs/36296436362) passed on both platforms. Measured source: `43e6a58b7906f91c73a6db544829acaa9789b5cf`. This report separates measured copy-only benefit from the cost of staging and verification.

Both conditions use existing test RSA keys, active caching_sha2_password with
loaded-key/public-key checks, the same within-call validation-reuse probe, the
same Wasmer/MariaDB configuration and the same 64 KiB stdio snapshot_copy routine.
A single canonical Go benchmark process creates one 1,000-row Snapshot, then
Forks that **same immutable Snapshot** for both conditions at workers 1/4/8.
The launcher alternates host-first / guest-first across 20 measured pairs and two
warmup pairs. All clients/processes close before switching the process environment.

- **Control:** `/snapshot-in/data` → fresh memory-FS `/mariadb`.
- **Probe:** the unchanged routine first copies `/snapshot-in/data` into fresh
  memory-FS `/restore-source`, then copies `/restore-source` → fresh `/mariadb`.

The pre-stage is measured separately with identical operation counters. It is not
free or removed from Fork latency. The source copy remains alive until process
exit, adding ~138 MiB of logical file contents to the probe; memory pressure and
warm caches are therefore experimental confounders, especially at workers 8.
This is not a claim that production can retain such state cheaply.

## Correctness and observability

Before the probe's timed copy, recursive comparison checks original versus
pre-staged source: exact directory inventory, regular-file sizes and full byte
contents (stronger than comparing computed hashes). After either condition's
copy, the same comparison checks original versus destination. Extra/missing files,
symlinks, altered bytes and copy failures reject startup. No redo/undo files are
omitted. Each timed copy independently reconciles inventory sizes against both
read and write bytes in the reporter; pre-stage relative-path inventories must
also match the measured guest-source inventory.

These comparisons run **outside copy timing** and their wall/process/thread CPU
are recorded as `restore_verification`. They do add to end-to-end startup, and
probe performs one additional comparison. They can warm the source before the
probe's timed copy. Neither comparison nor pre-stage is silently subtracted.
The pre-existing `restore_begin`→`restore_complete` events cover the whole
restore operation, including these costs; `restore_copy.wall_ns` isolates the
actual comparison copy. Do not confuse these scopes.

`restore_source`, `restore_identity_verified`, `restore_copy`, and (probe only)
`restore_prestage` are structured guest startup JSON. Clock failures remain
fail-closed. `summary.json.source_boundary` retains operation wall/CPU, bytes,
calls, per-file data, pre-stage and verification distributions with raw observations.
The ordinary lifecycle waterfall still reports full Fork→SQL and restore envelope.
The benchmark validates first SQL plus 27 loaded-key checks per paired execution
(one Start and 13 Forks per condition). No expensive memory diagnostics run.


## Evidence verification and environment

Independently recomputed `source_boundary` summaries from all 20 measured raw paired reports per platform, checked completion and 27 prepared-auth branch/public-key checks per report, and verified all copy/pre-stage clocks, inventory/byte counts and content-verification results. Across both conditions and every worker, each pair has exactly the same normalized path/size inventory. Guest full-byte comparison supplies content identity; no file content is omitted. Both copy conditions have 11 files / 4 directories, ~138.17 MiB, 2,227 reads and 2,216 writes. Small-file bytes differ by under 0.5 KiB between independently prepared pairs, never within a pair.

Downloaded native manifest hashes match recorded provenance. Native/AOT binaries themselves are not included in these result artifacts, so their hashes below are CI-recorded identities rather than independently rehashed binary downloads. Recomputed summaries and valid guest verification attestations are the scope of local verification.

- Go 1.26.8, Wasmer 7.4.2, MariaDB 13.1.0 embedded.
- macOS 15.7.9 arm64, 3 logical CPUs.
- Ubuntu 24.04.5 x86_64, 4 logical CPUs, Linux 6.17 Azure / glibc 2.39; SSE2 + SSSE3 AOT.
- Shared WASM: `80f7e345e9c123361eeddded5037f22573320d2d390154c4df5d3923973a451d`.
- Mac AOT: `33cf4cd58218180f2963c0700b3408899e5b63cccfffcf307fb062463d1052fe`.
- Ubuntu AOT: `ba7a6917b0a8f5f3485244e2e59e8713c96c1e470c5cc317e54d0e413fa7243c`.

Raw results remain ignored under `benchmarks/results/source-36296436362/`; workflow artifact names are `initialization-<platform>-43e6a58...`, with `init-source-boundary/summary.json` and pair files. No runtime/product change or architecture decision follows from this analysis. Do not compare absolute platform latency as equivalent hardware.

## Measured copy-only latency

All cells are p50 / p95 ms. Host=control; Guest=probe. Per-DB sample counts are 20 / 80 / 160 at workers 1 / 4 / 8; parallel observations within a batch are correlated. Marginal medians are not additive.

| Platform | Workers | Host copy | Guest copy | Host read | Guest read | Host write | Guest write |
|---|---:|---:|---:|---:|---:|---:|---:|
| darwin-arm64 | 1 | 274.9 / 386.2 | 126.1 / 177.3 | 148.3 / 191.3 | 24.7 / 34.2 | 98.3 / 158.0 | 87.7 / 124.9 |
| darwin-arm64 | 4 | 498.8 / 849.3 | 323.8 / 472.2 | 295.1 / 526.0 | 56.2 / 109.8 | 168.6 / 296.8 | 225.6 / 344.5 |
| darwin-arm64 | 8 | 798.6 / 1253.8 | 857.8 / 1377.6 | 549.9 / 879.4 | 243.0 / 568.8 | 189.1 / 481.8 | 485.2 / 778.3 |
| ubuntu24.04-x86_64 | 1 | 254.7 / 272.5 | 51.0 / 52.6 | 204.6 / 221.1 | 13.4 / 14.1 | 34.2 / 35.9 | 26.1 / 27.3 |
| ubuntu24.04-x86_64 | 4 | 333.0 / 468.5 | 70.5 / 85.4 | 262.7 / 403.5 | 18.8 / 22.3 | 45.6 / 51.2 | 34.3 / 39.0 |
| ubuntu24.04-x86_64 | 8 | 564.8 / 759.4 | 141.5 / 215.7 | 484.6 / 673.1 | 31.1 / 47.1 | 53.1 / 65.3 | 58.5 / 82.3 |

**Derived paired calculation:** median host-minus-guest copy / read / write differences (one median per batch before differencing) are:

| Platform | Workers | Copy saved ms | Read saved ms | Write saved ms |
|---|---:|---:|---:|---:|
| macOS | 1 | 133.5 | 117.8 | 12.1 |
| macOS | 4 | 208.3 | 257.2 | −40.4 |
| macOS | 8 | −90.3 | 292.9 | −295.7 |
| Ubuntu | 1 | 203.0 | 191.0 | 8.2 |
| Ubuntu | 4 | 265.2 | 247.2 | 10.4 |
| Ubuntu | 8 | 428.9 | 455.1 | −5.9 |

**Measured fact:** read shrinks on both platforms at every concurrency. At ×1, guest-memory source leaves write as the largest copy component; Ubuntu copy is ~51 ms and macOS ~126 ms. ×1 write also shrinks modestly, so destination cost cannot be assumed perfectly unchanged. At macOS ×8, guest-source write growth outweighs read savings and total copy becomes slower.

## Measured CPU

Each cell is process CPU p50/p95 ms, followed by current-thread CPU p50/p95 in parentheses. Reads of the clocks are sequential; tiny differences are not exact CPU attribution.

| Platform | Workers | Host read CPU | Guest read CPU | Host write CPU | Guest write CPU | Host total CPU | Guest total CPU |
|---|---:|---:|---:|---:|---:|---:|---:|
| darwin-arm64 | 1 | 144.8 / 178.8 (81.7 / 100.3) | 24.9 / 33.9 (25.3 / 34.4) | 98.7 / 157.6 (100.2 / 159.8) | 88.2 / 123.9 (89.7 / 126.2) | 272.8 / 354.6 (203.6 / 275.8) | 126.0 / 174.7 (126.0 / 174.7) |
| darwin-arm64 | 4 | 161.4 / 197.8 (96.3 / 117.5) | 32.3 / 41.2 (33.0 / 42.0) | 132.3 / 174.4 (133.8 / 176.5) | 142.0 / 196.4 (143.8 / 199.4) | 316.4 / 384.2 (250.5 / 303.4) | 192.3 / 254.6 (192.3 / 254.6) |
| darwin-arm64 | 8 | 152.1 / 200.9 (88.8 / 120.5) | 54.7 / 110.9 (55.7 / 113.7) | 97.8 / 147.6 (99.2 / 148.6) | 125.9 / 199.3 (128.4 / 202.6) | 272.6 / 371.0 (205.9 / 288.2) | 200.6 / 326.7 (200.6 / 326.7) |
| ubuntu24.04-x86_64 | 1 | 176.8 / 197.1 (88.4 / 98.3) | 13.6 / 14.3 (13.7 / 14.4) | 34.5 / 36.1 (34.6 / 36.3) | 26.3 / 27.5 (26.5 / 27.6) | 224.5 / 247.5 (136.3 / 146.6) | 51.0 / 52.6 (51.0 / 52.6) |
| ubuntu24.04-x86_64 | 4 | 171.6 / 188.2 (80.5 / 94.3) | 18.8 / 20.2 (19.0 / 20.5) | 43.0 / 45.9 (43.2 / 46.0) | 33.7 / 36.7 (34.0 / 37.1) | 232.2 / 250.8 (140.3 / 154.4) | 68.1 / 72.5 (68.1 / 72.5) |
| ubuntu24.04-x86_64 | 8 | 167.7 / 187.1 (81.2 / 93.5) | 19.5 / 21.0 (19.8 / 21.3) | 44.2 / 47.4 (44.4 / 47.7) | 35.0 / 38.3 (35.4 / 38.7) | 231.2 / 251.7 (144.5 / 156.8) | 70.8 / 76.4 (70.8 / 76.4) |

**Inference:** the source-condition effect includes substantial runtime/process CPU, not merely elapsed waiting. At ×1, host read process CPU is ~145 / 177 ms (macOS / Ubuntu), versus guest ~25 / 14 ms. The process/current-thread gap largely disappears in guest-source copy, consistent with less other-thread servicing, but no profiler identifies which thread/function owns that gap.

## Pre-stage, validation and whole Fork are not free

| Platform | Workers | Pre-stage wall | Pre-stage process CPU | Pre-stage thread CPU | Host verification wall | Guest verification wall | Host Fork→SQL | Guest Fork→SQL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| darwin-arm64 | 1 | 262.2 / 322.0 | 261.8 / 324.1 | 193.1 / 237.8 | 291.3 / 394.0 | 583.0 / 748.1 | 929.2 / 1229.9 | 1368.2 / 1696.4 |
| darwin-arm64 | 4 | 522.1 / 780.3 | 326.0 / 437.0 | 265.4 / 351.5 | 421.8 / 770.4 | 865.4 / 1188.0 | 1617.3 / 2799.0 | 2529.8 / 3228.2 |
| darwin-arm64 | 8 | 856.0 / 1570.5 | 295.5 / 433.3 | 228.5 / 347.1 | 928.4 / 1686.9 | 1981.5 / 2692.1 | 3146.8 / 4366.0 | 5184.9 / 6524.8 |
| ubuntu24.04-x86_64 | 1 | 255.4 / 270.4 | 229.8 / 242.0 | 135.8 / 144.4 | 365.5 / 376.4 | 727.9 / 750.8 | 935.6 / 961.3 | 1341.9 / 1384.3 |
| ubuntu24.04-x86_64 | 4 | 347.0 / 487.0 | 232.7 / 252.2 | 139.9 / 155.7 | 662.6 / 780.5 | 1239.9 / 1450.5 | 1393.3 / 1553.5 | 2056.9 / 2326.9 |
| ubuntu24.04-x86_64 | 8 | 572.1 / 759.9 | 232.7 / 251.1 | 145.0 / 155.9 | 1266.0 / 1492.0 | 2401.8 / 2706.3 | 2567.9 / 2771.1 | 3856.7 / 4073.4 |

**Measured fact:** each probe pre-stage copies the full ~138.17 MiB, once per isolated DB. Pre-stage cost is close to a normal host-source copy; moving it before a timer does not remove it. Probe also performs two full content comparisons versus one in control. Verification itself is expensive, so these Fork figures are correctness-probe costs, not a replacement FAST baseline. Both conditions have instrumentation enabled; the prior ON/OFF perturbation result still applies.

**Measured fact:** guest-source read wall still grows: macOS ~25 → 56 → 243 ms; Ubuntu ~13 → 19 → 31 ms. The large host-read growth is greatly reduced, not universally eliminated. Guest-source write wall grows macOS ~88 → 226 → 485 ms and Ubuntu ~26 → 34 → 58 ms.

**Order sensitivity:** split the 20 pairs into ten host-first and ten guest-first pairs. Read savings remain positive in both groups at every concurrency. Mac ×8 copy savings are −90 / −104 ms, write savings −335 / −259 ms; the adverse write result is not solely an ordering sign flip. At ×4 mac write savings differ +18 / −89 ms, showing substantial variability. Ubuntu ×1 read savings are ~191 ms in both orders. These checks do not remove cache or memory-pressure confounding.

## What this proves and does not prove

- **Measured fact:** the current host-mounted source path contributes a substantial fraction of copy latency/CPU. Changing only source preparation/location while retaining the copy routine strongly reduces read time on both platforms.
- **Inference:** at single isolation, common destination materialization is not the full explanation for existing restore latency; source serving/transfer is a meaningful target. The observed paired savings are not a pure cost estimate for a named WASIX subsystem.
- **Unknown:** host-source read contains libc buffering, WASIX service/transfer and host filesystem access. Guest-source has prior staging/verification, warmer data and an extra live ~138 MiB source. This is an experimental condition effect, not an isolated physical-disk or single-boundary function profile.
- **Measured fact:** destination work remains material, especially macOS; ×8 copy-only totals there do not improve. No expensive memory diagnostics establish whether the extra source causes that write degradation.
- **Unknown:** no redundant transfer can yet be deleted safely. A host-volume optimization, retained filesystem state and CoW could have very different semantics/costs; this probe does not choose among them.
- **Measured fact:** full probe Fork is slower, not faster. No production performance improvement is implemented or claimed.

## Recommended restore direction

Investigate **the existing host-mounted source transfer/service path** with one bounded read-only probe using the same inventory and read size: locate and time the host-volume read servicing/transfer boundary, without destination writes. This is the smallest next direction supported by read savings on both platforms. Keep CPU/wall, order, bytes and cache conditions explicit; do not introduce VFS/CoW or ship an optimization yet. Destination pressure remains a documented constraint, particularly macOS ×8.

## FAST tranche integration checkpoint

**Prepared RSA keys:** existing causal evidence is sufficient to move to a separate
productionization task after this probe. Still require provisioning/lifetime/security
policy, missing/corrupt-key diagnostics, actual authentication-handshake coverage
(current startup retains grant bypass), and packaged Go/Python lifecycle, Snapshot/
Fork, multi-client and interrupted-query cleanup on both supported platforms.

**Within-call validation reuse:** existing paired evidence supports a separate
productionization task. Still require explicit verified-identity ownership,
mandatory native/snapshot integrity checks, mutable NativeDir/sidecar and failure
paths, and packaged lifecycle/cleanup on both platforms. No persistent trust cache.
Neither experiment is merge-ready merely because its measured savings are clear;
neither is integrated by this task.
