# Fork attribution after prepared UCA adoption

2026-11-05. Conclusion: **server_init remains dominant**. In this traced cohort it accounts for 84% / 79% / 73% of mean Fork elapsed at P1 / P4 / P8, and 65% of the P1→P8 increase. Memory setup and execution residual also expand. Limiter admission wait is negligible. The dominant interval spans guest MariaDB and its host imports; it is not evidence that all the cost belongs exclusively to MariaDB C code.

[Standalone stage graph](report.html) · [Per-child CSV](children.csv) · [Summary](summary.json) · [Exact inputs](inputs.json)

## Additive Fork elapsed breakdown

Milliseconds per child, **means across 144 children per P** (three48-child processes). Traced observations only; means add to total, whereas independent phase medians would not. Guest monotonic durations are subtracted from the host execution duration, without aligning timestamps across clocks. No outlier is removed.

| Phase | P1 | P4 | P8 |
|---|---:|---:|---:|
| Host admission / setup / dispatch | 0.88 | 1.73 | 2.79 |
| Filesystem / prepared handles | 0.06 | 0.08 | 0.33 |
| Linear memory reservation / generated init | 1.87 | 2.99 | 6.55 |
| MariaDB server_init | 23.40 | 32.96 | 48.47 |
| Bootstrap connection | 0.11 | 0.20 | 0.16 |
| Routine schema | 1.04 | 1.94 | 1.95 |
| Other guest startup | 0.05 | 0.05 | 0.08 |
| Execution residual | 0.34 | 1.34 | 5.29 |
| Ready observed to host startup end | 0.08 | 0.21 | 0.67 |
| **Total Fork** | **27.82** | **41.51** | **66.30** |

Memory reservation alone: P1 0.01 ms / P4 0.33 ms / P8 1.77 ms. Generated initialization alone: P1 1.86 ms / P4 2.66 ms / P8 4.77 ms. Admission-to-handle p95: P1 0.0036 ms / P4 0.0067 ms / P8 0.0108 ms.

Execution residual includes pre-main runtime work, startup timing serialization, framing and scheduling between guest ready preparation and host observation. It is not a pure wait-time measurement. Post-ready includes listener creation and diagnostics reading. Ordinary Start/Fork still creates a TCP listener; SQL uses Pipe.

## Untraced controls and scaling

| P | Fork p50 / p95 ms | Batch wall ms (all three) | Batch CPU / child ms | SQL >100ms /144 |
|---|---:|---|---:|---:|
| 1 | 26.30 / 30.34 | 1873.7 / 1802.3 / 1808.1 | 50.59 | 0 |
| 4 | 36.48 / 46.90 | 616.9 / 645.2 / 693.9 | 64.77 | 0 |
| 8 | 59.99 / 151.30 | 632.8 / 628.8 / 1430.4 | 70.53 | 4 |

Untraced CPU/child rises 50.6→64.8→70.5 ms, while Fork p50 rises26.3→36.5→60.0 ms. CPU is the entire batch divided by48, including SQL/cleanup/background workers; it cannot be charged exclusively to an individual Fork. More elapsed time is not explained only by admission queueing. Sharing CPU/memory resources and scheduling is consistent with the results, but their relative contributions are unproven. Minor faults stay near220k–224k per48-child batch across P, so there is no comparable increase in fault count; this does not establish equal memory bandwidth or RSS. This experiment does not measure per-child retained RSS.

Calibration: traced Fork p50 is27.1 /39.9 /64.8 ms, versus untraced26.3 /36.5 /60.0 ms. Do not substitute the traced timings for uninstrumented product performance. Traced batch medians1841 /732 /777 ms versus untraced1808 /645 /633 ms are influenced by different long-SQL realizations. n=3 cannot establish one correction factor for observer overhead. Both traced and untraced SQL tails remain recorded; no claim that P4 is a hard throughput ceiling follows.

## Separate batch CPU samples

One extra48-child CPU-profile process per P; profiling was disabled in both ordinary timing modes. Samples cover the whole child batch, not Fork alone. Their distributions are diagnostic, not precise per-phase CPU accounting.

| Sampled CPU stack | P1 | P8 |
|---|---:|---:|
| memclrNoHeapPointers flat |310ms (13.3%)|610ms (18.0%)|
| Mprotect on MemoryMapping.Grow path |220ms (9.4%)|360ms (10.6%)|
| rootRead → memclr sampled path |140ms (6.0%)|300ms (8.8%)|

The rootRead row is a subset of memclr, so these rows must not be summed. Full top/caller reports and the original profiles are in receipts.zip. Several remaining hot functions are generated FnNN symbols; no unsupported mapping to InnoDB functions is inferred. macOS sampling of runtime/syscall code has attribution limitations; these are short profiles, not evidence of time asleep on a condition variable.

Source inspection confirms two concrete host paths worth considering next:

- `internal/prepared/root.go:127` clears an output block before copying a mapped prefix over it. A bounded correctness-first experiment could clear only the uncovered suffix. It must preserve sparse holes, short reads and snapshot isolation; this report does not claim a speedup or authorize adopting that change.
- `base.MemoryMapping.Grow` performs memory protection changes while guest startup allocates. Its sampled CPU cost persists at P8. This is a lead, not proof that a previously tested batching approach will help; consult previous findings before repeating that hypothesis.

## Scope, identity and reproduction

Single Apple M1 /16GiB macOS27.2; Go1.27.3, CGO0, GOMAXPROCS8, GOGC100. Same adopted product source1862f4a89397bddfa1820d835106d3437a438cf7 and guest6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe as the preceding Pipe comparison. New harness source3be0dd9ef3d9740bbd59fe32e03225f7cc717120; parent e0cbbb08829612d5567221a1e31c9c8386577dfe. Git commit identity and clean source checked before build. Product changes are observer-only Go build overlays, separately hashed in inputs.json; canonical guest/generated source was not edited. Binary VCS stamp identifies the harness; module replacement binds the product to that same checkout.

Workload remains1,000 rows,48 independent children, Pipe, cap=worker count. Same SELECT/pristine-count/sum/update/isolation/disposal oracles. Root/capture/final Snapshot close are excluded from batch timing. Three fresh timing processes and one separate warmup per P/mode, with alternating modes and P order. One concurrent positive pilot and one deliberately wrong-seed negative control; all ordinary/warmup/profile SQL and cleanup oracles pass, and the negative fails as intended and cleans up. Each startup context owns its timing trace and guest timing reader; there is no global current-child pointer.

receipts.zip retains all29 process results (18 ordinary,6 warmup,2 pilots,3 profiles), exact per-child traces, profiles, input hashes, collector/reducer/build scripts and plan. Duplicate default timing files are omitted; callback traces retain the same unique per-child observations. Extract ZIP into an empty directory and run `python3 analyze.py --check`: no temp tree needed and no writes. Reproduce the measurement from the clean harness commit, generate its recorded overlay, then follow archived build.py/run.py with the recorded workspace layout. A rerun produces new observations. SHA256SUMS.json covers published files.

No product integration, guest rebuild, CI dispatch, main merge or release in this task. Evidence is kept on a separate experiment branch; main adoption of benchmark outputs is not presumed.
