# One-shot hot-path investigation: why direct panic helps

結論: 最適化可能性は棄却しない。直接panicには、(1) 中小callerでMemoryEAをinlineできることに加えて、(2) inlineされない呼出でもMemoryEAの正常経路から不要なスタック保存2命令と重複加算1命令が消える、という二つの確認可能な機構がある。前回2関数shared-panicはこの全域helper改善を含まず、今回負荷のMemoryEA CPUサンプルの約1.3%に対応するcallerだけを対象にしていた。従って、その不振から直接panic/境界検査最適化全般を棄却できない。

一方、直接panicの全体短縮を全てMemoryEAの短縮で説明することもできない。今回の一回限りのサンプリング調査は候補箇所と命令機構を特定したところで終了し、追加計測・新候補実装を自動開始しない。

## Identity and finite method

- source_commit `523a8883d434af381f7a9d00a2c6ae571eefc172`, git_identity.py checked (source.json). Prior experiment runtime lineage; not latest main acceptance.
- Go1.26.10/macOS arm64, CGO0/GOMAXPROCS8/GOGC100. Same SUM-trigger + REVENUE_PREAGG=1 full-suite harness, fixed parent Close and Close-error checks, from `../suite-20261115/harness.tar.gz`. Only go.mod version and product path adjusted.
- baseline: unchanged runtime. direct: only base.MemoryEA direct panic + obsolete helper removal; exact source hash `0170988abb28903ff3824a0e5efbe7865b0ba4961a892de7ce5bfca842ba332a` matches previously qualified-as-experiment translation. shared: only Fn13460/Fn15594 AST lowering, both exact hashes checked against prior shared-lowering evidence; base helper unchanged.
- All three binaries built before executing any workload. Each arm one process, `-test.parallel=1 -test.count=20 -test.cpuprofile=...`, same 70-test pattern; fixed order baseline/direct/shared. Total 4200 test spans, 1200 writer Fork, 1203 sample spans. All processes PASS and counts checked. No repeated campaign and no new optimization.
- Profiling encompasses the whole fixture/process: boot, readers, writers, sample, queries, cleanup. It is not an INSERT-only or SQL-only profile. Test-count repetition reuses TestMain setup; it is not 20 independent full-suite launches. P8 or other platforms were not profiled.
- Managed helper budget6GiB/minfree6GiB/timeout3600s; command timeout1200s, profile timeout180s. Build durations100.18/220.14/52.69s are not cold-build comparisons. The recipe lives in run.py; inspect.py reads the built binaries, analyze.py reads saved raw profiles. Scripts expect evidence/ beside worktree/ and temp/.

## Confirmed mechanism, including a correction to the earlier explanation

The previous explanation emphasized inlining. That was incomplete: the machine code of the out-of-line helper itself also changes.

Baseline MemoryEA calls a separate `//go:noinline Wasm_trap_memory_oob()` on failure. The caller's generated machine code retains a possible return path from that opaque call. It therefore writes addr and offset (R1/R2) to the stack **before every bounds check**, although the failure path is not normally taken. The saved values can be reloaded on the failure-return path, and the successful path computes addr+offset again.

Direct `panic(...)` is recognized as a terminating path. In the measured arm64 output, the normal path no longer stores R1/R2 to the stack and reuses the earlier addr+offset result as the return value. The valid-access fast path falls from23 to20 instructions (excluding caller CALL and stack-growth slow path). Atomic size load and all three bounds comparisons remain. Baseline reloads are on the failure-return path, so **do not count two reloads as normal-path savings**. Both complete disassembly regions remain36 words including padding; direct helper stack frame grows16→32 bytes. There is no general claim that every size metric shrinks.

This directly benefits even non-inlined callers. In current binaries:

| caller | baseline MemoryEA call sites | direct call sites | observation |
|---|---:|---:|---|
| p4.Fn18056 |125|125|still calls the improved helper|
| p1.Fn5423 |1272|1272|still calls the improved helper|
| p4.Fn18187 |68|0|helper inlined;68 panic blocks duplicated|
| p3.Fn13460 |157|0|helper inlined;157 panic blocks duplicated|
| p1.Fn15594 |853|853|still calls the improved helper|

Thus direct panic's effects are broader than inlining in small functions. At inlined sites it also removes call/return and exposes constants to local optimization, but this investigation does not quantitatively separate each compiler optimization's contribution. Panic itself does not have to execute to improve the normal path. No panic stack was sampled.

## Dynamic evidence and selected targets

CPU profiles use10ms samples. The numbers below are sampled cumulative CPU seconds attributed to MemoryEA, **not invocation counts**. Inline virtual frames are included; do not add MemoryInBounds to MemoryEA because they overlap.

| metric | baseline | direct | two-function shared |
|---|---:|---:|---:|
| total sampled CPU s |37.73|29.20|37.80|
| MemoryEA cumulative sampled s |1.50|0.71|1.23|
| measured process CPU s (getrusage) |40.041|31.168|40.139|
| profiled process wall s |30.714|24.343|30.365|
| non-stripped test executable bytes |108555138|191098530|108654210|

These are single observations with profiler overhead and fixed ordering, **not repeatable performance estimates or adoption benchmarks**. The direct executable retains the large size penalty. Host/wheel sizes are unmeasured.

Baseline immediate callers of MemoryEA:

| caller | attributed sample s | share of MemoryEA1.50s |
|---|---:|---:|
| p4.Fn18056 (historical symbol map: buf_page_t::flush) |0.44|29.3%|
| p1.Fn5423 (ha_maria_init) |0.11|7.3%|
| p4.Fn18187 (buf_LRU_remove_block) |0.06|4.0%|
| p3.Fn13460 (close_thread_table; prior shared target) |0.01|0.7%|
| p1.Fn15594 (update_single_table; prior shared target) |0.01|0.7%|

Names are from the repository's historical function-map.txt (buffer-zero-candidate validation); selected names also agree with prior inline-trial map. Function numbers and Go symbols in the fresh binaries are the primary identities. They do not establish phase attribution: the whole-suite fixture includes startup and teardown, so these are not automatically INSERT hot paths.

The previous shared targets jointly represent just0.02s /1.50s =1.33% of this baseline's MemoryEA samples (only two10ms samples; imprecise). Removing1010 static call sites therefore did not imply removing a large dynamic cost. In the direct profile Fn18056's attribution is0.26s and Fn5423's0.07s even though their call sites remain; Fn18187 is0.04s including virtual inline frames. These finite samples support consistency with the inspected mechanism, not a precise causal effect per function.

Using physical frames instead of inline virtual frames: MemoryEA leaf samples are1.48→0.45→1.22s. Direct's cumulative0.71s also includes inlined helper executions attributed to their actual callers. profile-summary.json preserves raw accounting and all immediate caller weights; pprof flat/cum/physical/callers outputs cross-check the extraction.

## What remains unexplained

Total sampled CPU decreases8.53s baseline→direct, while MemoryEA cumulative decreases0.79s. These cannot be equated. Other large reductions include rawsyscalln15.66→12.47s, pthread_cond_signal3.79→2.89s, pthread_cond_wait2.93→2.20s, usleep2.82→2.20s. End-to-end scheduling, lifecycle and sampling variation may contribute; this experiment does not establish how much is an indirect optimization effect. It does not measure syscall counts, cache misses, branch prediction or dynamic access counts. No claim that all CPU gain is helper call overhead, or that each apparent runtime reduction is causal.

No INSERT-only new profile, no phase observer hooks, no extra warmup/repetition, no isolated non-inlining control, and no Linux or distribution qualification were added. The bounded question yields a concrete compiler mechanism and likely targets; full causal apportionment remains outside this one-shot scope.

## Recommendation

Keep the optimization avenue open, but do not productize the current global-inline or two-function shared candidates. This investigation is complete.

If a new experiment is later approved, the smallest discriminating candidate is **direct panic in MemoryEA while explicitly keeping MemoryEA out of line**. It would preserve the confirmed normal-path simplification without broadcasting inline code and panic blocks across hundreds of thousands of sites. That is an unmeasured hypothesis, not a proven speed/size solution. Alternatively, a targeted shared lowering should start from a sampled hot caller such as Fn18056, not static call-site count alone. Do not automatically run either experiment from this report.

For that helper-only hypothesis, the canonical runtime patch in wasm2go would be the eventual owner; a per-function shared-label emitter rewrite is not inherently required. Adoption still needs a same-source finite correctness/performance/size decision and canonical generation/provenance work.
