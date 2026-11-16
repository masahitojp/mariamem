# Startup buffer loading — bounded value control

## Decision
Disabling startup preload is possible without rebuilding the guest, using an experiment-only per-instance `/etc/my.cnf`. This campaign does **not establish a meaningful whole-lifecycle improvement or a remedy for the long tail**. Keep the product default. Do not resume pending/400ms tracing automatically. Further qualification is worthwhile only with a stronger workload-specific benefit or a natural long-wait reproduction; this report does not authorize it.

## Identity and method
Product baseline source_commit `6558ee8fb2211313a8aa0ea6070ac5256767811a`; harness base `1977fff480c2f976bc23f4d2e1b8ff8db36ad128`; measured source_commit `dec0054edb856b4f74eafae96bad24d0ac01166c`. Canonical guest SHA256 `77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450`. No changes to generated engine code, canonical guest or public API. The handwritten adapter writes the same configuration path in both arms, changing only ON/OFF. This is an isolated experiment, not merge-ready canonical provenance.

Fixed Go1.27.4 / darwin arm64 / GOMAXPROCS8 / GOGC100 / CGO0. Identical executable for both arms, hash recorded. P8, MaxForks16, synchronous Close, matched 70 cases (50 reads /20 writers), SUM and status-limited audit trigger, preaggregated revenue. One warmup per arm, then ten alternating ON/OFF/OFF/ON and OFF/ON/ON/OFF blocks: 42 processes, 2,940 bodies PASS. No exclusions or adaptive repetitions. Internal elapsed includes root boot, import, snapshot, all forks/samples/tests and final cleanup. Process wall, CPU, RSS and all phase spans retained. Recursive storage scans run only between processes. No runtime tracing. P1/platform qualification and a new cross-engine comparison were not run.

## Setting validation and corrected initial check
Pinned upstream [lib_sql.cc](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/lib_sql.cc#L541) uses server/embedded option groups. [srv0start.cc](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/srv/srv0start.cc#L1968) forces the setting FALSE when creating a fresh database. The first validation incorrectly expected fresh ON=1 and failed before timing. That evidence is preserved. The corrected independent checks returned fresh=0 / restored=1 for ON, and fresh=0 / restored=0 for OFF. Both matched SQL/audit semantics checks PASS. Configuration validation SQL is disabled during timing. No post-start abort masquerades as disabled startup work.

A retry initially lacked the disposable temp directory; recreated before build. Sandboxed localhost bind was denied; validation and measurement then ran with approved network permissions. Neither failure entered the measured cohort.

## Results

| Metric | ON | OFF |
|---|---:|---:|
| Internal elapsed median, ms | 427.755 | 416.624 |
| Internal elapsed mean, ms | 426.753 | 421.765 |
| Internal elapsed range, ms | 398.252–456.289 | 391.228–468.162 |
| External process wall median, ms | 449.943 | 449.577 |
| CPU median, ms | 2102.591 | 2085.561 |
| Runs above own median ×1.2 | 0/20 | 0/20 |

Primary block comparison uses geometric mean of two observations per arm. OFF/ON internal elapsed paired median **−1.166%**, 6/10 favorable, range −4.710% to +3.882%. External process wall paired median **+0.135%**, 5/10 favorable. CPU paired median −0.694%, 7/10 favorable. Independent median difference is −2.60%, while arithmetic mean difference is −1.17%; these statistics are not interchangeable. Adjacent same-arm A/A absolute difference median: ON3.230%, OFF5.920% (five adjacent pairs each). These observations do not establish that the small effect is distinct from variability; A/A is descriptive, not a formal confidence threshold.

| Per-run phase p50, median across runs (ms) | ON | OFF |
|---|---:|---:|
| Writer Fork | 29.909 | 26.355 |
| Sample insertion | 69.012 | 70.005 |
| Test body | 1.585 | 1.643 |
| Writer cleanup | 3.543 | 3.278 |

This is consistent with moving some reads from startup into subsequent work, not proof of precise causal attribution. Concurrent phase medians/sums must not be added to explain wall time. Setup median92.463/92.461ms; run333.764/320.165ms; final cleanup2.266/2.125ms; separately computed medians need not sum to the whole median. No approximately400ms extra delay appeared in either arm. Consequently the tail hypothesis is unresolved, not disproven or fixed.

## Reproduce and retain
Use the measured SHA and a disposable workspace with worktree/temp/evidence siblings. Restore build.py, measure.py and analyze.py to evidence; create temp/tmp; run build with a6GiB budget/8GiB free floor, then measure without concurrent recursive monitoring. Runtime requires localhost bind permission. `inputs.json` and binary-sha256 identify inputs; records, per-run JSON/text, validation logs and summary preserve all outcomes. The initial source SHA3e8c33499fbadeb891a3e5ba26f8529495486b12 explains the failed fresh expectation. No extra benchmark repetitions are implicit in reproduction instructions.

Generated binaries, Go cache, copied harness and automatic failed-run cache exports are disposable. Report/evidence and the experimental source commits are retained. Main and unrelated root changes are untouched; no integration/release/CI submission.
