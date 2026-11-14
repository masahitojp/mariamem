# Two real functions with a shared panic target — runtime check

結論: 関数ごとにpanic先を共有する試作は実guestでも動作し、以前の全域direct-panic候補の大幅なサイズ増加は起きなかった。しかし今回の2関数だけの適用では全体時間の改善を確認できず、P8は5組中4組で悪化した。この候補は採用せず、wasm2goへの正式パッチ化・全関数への拡大に自動的には進まないことを推奨する。共有panicという生成方式一般を否定する結果ではない。

## Fixed scope and inputs

- source_commit: `a75cf08b60c53c4a8391ebe81afd96c170e5c667` (git_identity.py verified; source.json).
- This source is the prior experiment lineage, not current main. Its product runtime baseline is the prior bb1e937-era runtime; no claim about current-main acceptance.
- Go 1.26.10 / macOS arm64 / CGO_ENABLED=0 / GOMAXPROCS=8 / GOGC=100.
- Only p3.Fn13460 (close_thread_table, 157 accesses) and p1.Fn15594 (update_single_table, 853 accesses) are transformed, using the pinned `../shared-lowering-20261115/lower.go` pass. The exact transformed hashes match that prior experiment. base.MemoryEA and other functions remain baseline.
- Prior assembly evidence: one runtime.gopanic call site per selected function; MemoryEA calls removed in those functions. Small function disassembly region -13.3%, large function +4.9%. Those are prior assembly-region measurements, not this binary's whole text size.
- Harness is exactly the pinned `../suite-20261115/harness.tar.gz` Maria arm with the snapshot-parent Close correction and Close error checks. Only go.mod version changes from Go1.27 to 1.26.0, and its product path is resolved. No new SQL/fixture changes.
- Original SUM triggers, audit enabled, REVENUE_PREAGG=1, matched constraints/indexes; 70 test bodies, 20 writer forks and 21 sample spans per process.
- Each arm: one warmup + five measured runs at each P1/P4/P8. Alternate baseline/candidate order by round. Both binaries built before measurements. 36 processes, including warmups. No third engine in this narrow test.

## Results

Independent medians of five processes, milliseconds. CPU sums process user+system time; process wall includes the time wrapper and process startup/exit. Suite elapsed comes from the existing trace recorder. These clocks have different boundaries.

| parallel | baseline suite | candidate suite | paired suite change | candidate faster |
|---|---:|---:|---:|---:|
| P1 | 1585.181 | 1575.700 | -0.27% | 4/5 |
| P4 | 659.831 | 673.788 | +3.56% | 2/5 |
| P8 | 564.678 | 591.182 | +8.78% | 1/5 |

Paired changes are medians of the five corresponding relative changes, not ratios of independent medians.

| parallel | baseline process wall | candidate process wall | paired wall change | baseline CPU | candidate CPU | paired CPU change |
|---|---:|---:|---:|---:|---:|---:|
| P1 | 1623.021 | 1628.595 | +0.43% | 2159.031 | 2158.299 | -0.21% |
| P4 | 700.193 | 704.948 | +0.68% | 2518.066 | 2592.027 | +1.39% |
| P8 | 604.647 | 621.195 | +8.92% | 2693.681 | 2659.769 | -0.70% |

P8 paired suite rates: +8.78%, +14.42%, +9.00%, +5.07%, -20.61%. The last baseline was 744.611ms versus candidate 591.182ms; all samples retained. Five pairs on a shared macOS host do not establish a precise causal slowdown, but do not provide an adoption benefit. CPU changes are small/mixed. Do not compare absolute timings directly with the earlier Go1.27.4 or global-direct-panic run.

Per-process p50, then median across five processes (ms; concurrent spans must not be added to reconstruct wall time):

| parallel | writer Fork baseline → candidate | sample baseline → candidate | test body baseline → candidate |
|---|---:|---:|---:|
| P1 | 17.382 → 17.773 | 45.796 → 45.904 | 1.220 → 1.343 |
| P4 | 26.055 → 24.815 | 64.020 → 64.463 | 1.596 → 1.762 |
| P8 | 34.958 → 29.544 | 100.278 → 109.726 | 2.241 → 2.190 |

Non-stripped suite binaries: 108,555,138 → 108,654,210 bytes, **+99,072 bytes (+0.0913%)**. This is a test executable, not a distribution host or wheel. The bounded two-function result cannot predict whole-generator application size. Median maximum RSS baseline → candidate: P1 206,897,152 → 206,766,080; P4 422,952,960 → 414,056,448; P8 654,000,128 → 683,409,408 bytes.

## Correctness and evidence

Both arms PASS all five tests in tests/generatedmemory and TestWorkerTrapActualGuestNotifiesAndIsolatesPeer. All 36 suite processes PASS; independent verify.py confirms 2520 test spans, 720 writer forks, 756 sample spans and recomputes paired summary from raw records. No observer hooks or runtime counters were added.

These tests cover real SQL, memory traps, snapshots and worker isolation, but do not exhaustively exercise every transformed access's OOB path. The same-pass 495-case fixture and negative transform tests are previous shared-lowering evidence. This run does not newly measure dynamic call frequency or attribute the small mixed CPU effect to particular instructions.

Raw traces/time outputs are in campaign/, records.json; summary.json contains all paired values and phase aggregates. Source identity, transformed hashes, executable hashes and exact scripts are included. run.py reconstructs from the pinned input; place scripts in an experiment evidence/ directory with sibling worktree/ and temp/ to reproduce. Runtime logs are gzip-compressed for retention; verify.py accepts either representation.

Initial experiment_workspace run failed before executing the script because its relative command path was interpreted from the worktree; console.log.gz preserves it. Retried using an absolute script path under experiment_disk.py with the same 8GiB owned budget / 8GiB minimum free / 6000s limit for the whole pipeline. No guest experiment ran in the failed attempt. Each build/test command timeout 1200s; each suite process 180s, campaign 900s. Successful pipeline: baseline runtime build/test 158.00s, suite build 3.50s; candidate runtime build/test 79.23s, suite build 3.01s; campaign 38.21s. Build cache conditions differ, so build durations are not performance comparisons.

## Decision and next condition

Do not productize this two-function patch. The code-size objective was met in this finite scope, but the original goal is faster application execution, and this test provides no stable improvement. If further exploration is chosen, first identify which dynamic access sites dominate CPU and whether this lowering increases register pressure/spills in those hot functions; choose a new bounded target using that evidence. That would require a separate profiling/assembly investigation, not an automatic full-generator rewrite.

If a later candidate proves useful, wasm2go generation is the intended owner: emit memory32-valid bounds checks and a per-function shared trap block in the converter, fail closed for unsupported forms, then canonically regenerate and refresh provenance/license records. This AST overlay is only a disposable prototype. No main merge, full converter change, release, wheel-size acceptance, or Linux result is claimed here.
