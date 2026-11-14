# Direct panic with MemoryEA kept out of line

結論: **正常経路の簡素化を保ち、全域inlineを禁止しても全suiteの利益が残った。** noinline候補は基準に対してP1/P4/P8の全15組でsuite elapsedとCPUが短縮。対応率中央値はsuite -5.67%/-4.79%/-4.76%、CPU -4.95%/-6.84%/-3.38%。非strip test executableは96bytes小さく、直接panic/inline許可版の約76%肥大を回避した。

推奨: この小さい候補を次の製品化検証へ進める価値がある。現時点でmain統合はしない。最大の反対材料は、inline許可版の速度利益の多くを残せていないことと、古い固定source/macOS arm64/5組のみの結果であること。今回は速度の最大化ではなくサイズとの釣り合いを改善できた。最新main・配布host/wheel・他OS・正規生成の条件は別途判断する。

## Fixed inputs and three arms

- source_commit `523a8883d434af381f7a9d00a2c6ae571eefc172`, verified by git_identity.py; source.json. This is the previous experiment runtime lineage, not current main.
- Go1.26.10 / macOS arm64 / CGO_ENABLED=0 / GOMAXPROCS=8 / GOGC=100.
- A baseline: existing runtime base.go calling a separate noinline trap helper.
- B direct: direct panic in MemoryEA, inline permitted; remove obsolete trap helper. Source hash exactly `0170988abb28903ff3824a0e5efbe7865b0ba4961a892de7ce5bfca842ba332a`, matching prior canonical-translation experiment.
- C noinline: B plus only `//go:noinline` on MemoryEA. No bounds-expression, arbitrary-uint64 contract, SQL, Wasm guest, transport or other function changes. source-hashes.json and two exact source diffs preserved.
- Overlays only; no canonical converter, generated inventory, provenance or release pin updated. This is not a merge-ready source change.
- Same pinned `../suite-20261115/harness.tar.gz` Maria harness, original SUM triggers, audit enabled, REVENUE_PREAGG=1, matched constraints/indexes, parent Close and Close-error checks. Only go.mod Go version and product worktree path resolved.

## Stage 1: correctness and mechanism

All three arms pass61 top-level base tests plus all5 generatedmemory tests and TestWorkerTrapActualGuestNotifiesAndIsolatesPeer. Tests cover the existing boundary/runtime surface, not exhaustive proof of every memory access or full release acceptance.

Compiler diagnostics confirm `cannot inline MemoryEA: marked go:noinline`. C and B helper normal-path disassembly matches instruction-for-instruction through the first RET:20 instructions. Prior A23-instruction normal path remains the comparison; atomic size load and three bounds checks remain. No assumption that lower inline cost itself guarantees improvement.

| selected caller | A MemoryEA call sites | B | C |
|---|---:|---:|---:|
| Fn13460 |157|0|157|
| Fn15594 |853|853|853|
| Fn18056 |125|125|125|
| Fn18187 |68|0|68|

The source directive/compiler diagnostic establishes the inline prohibition; selected disassembly confirms representative callers. The generation meaning was unchanged and Stage1 passed before the performance campaign was allowed to run. stage1.json, assembly-summary.json, compiler output and exact assembly retained.

## Stage 2: 54-process campaign

Each P1/P4/P8 arm has1 warmup +5 measured independent processes, rotating order A/B/C by round. No profiler. All binaries built before campaign. All54 processes PASS; each70 test-body spans,20 writer Fork and21 sample spans. Total3780 test bodies,1080 writer Fork,1134 sample spans including warmups. verify.py independently recomputes paired statistics and checks raw trace counts and runtime results. No additional repetitions or candidate changes.

Independent five-process medians in ms:

| P | A suite | B suite | C suite | C vs A paired median | C faster |
|---|---:|---:|---:|---:|---:|
|1|1427.382|1199.433|1343.344|-5.67%|5/5|
|4|679.978|582.941|629.971|-4.79%|5/5|
|8|580.027|467.613|550.034|-4.76%|5/5|

Paired rate medians are computed from corresponding rounds; they are not ratios of independent medians.

| P | A process wall | B wall | C wall | C/A paired wall | A CPU | B CPU | C CPU | C/A paired CPU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|1|1443.773|1255.991|1366.358|-5.74%|1965.732|1704.339|1874.735|-4.95%|
|4|706.342|605.497|650.029|-6.46%|2563.163|2184.791|2375.890|-6.84%|
|8|617.456|504.822|606.593|-6.26%|2834.438|2342.454|2721.124|-3.38%|

C process wall faster5/5,4/5,5/5; P4 one pair+0.59%. C CPU faster all15. B/A paired suite rates: -16.26%/-14.27%/-19.38% (faster3/5,5/5,5/5). C is slower than B by paired suite medians +12.66%/+7.87%/+16.21%, although individual P1/P8 pairs reverse. Do not promise the full inline-enabled speedup without its size cost.

C/A full paired suite rates:
- P1: -4.66%, -5.66%, -5.89%, -29.54%, -5.26%.
- P4: -2.53%, -18.04%, -4.79%, -2.46%, -7.56%.
- P8: -7.73%, -19.59%, -0.66%, -4.76%, -2.60%.

All outliers retained. P1 A round3=1972.964ms; B round2=1594.878ms, round4=1447.965ms; these explain why simple independent medians and paired rates differ. Shared macOS host, only five pairs, no frequency/thermal isolation. The workspace capacity monitor runs throughout all arms and also uses host CPU. Consistent signs support the bounded candidate, not a universally guaranteed percentage or a causal attribution of every saved CPU cycle.

## Size and phase detail

| executable | bytes | change from A |
|---|---:|---:|
|A baseline|108555138|—|
|B direct/inline permitted|191098530|+82543392 (+76.04%)|
|C direct/noinline|108555042|-96 (effectively unchanged)|

These are non-stripped test executables, not distribution mariamem-host or wheel. SHA256s in binaries.json. No distribution-size acceptance is inferred.

Per-process phase p50, then median of five processes (ms). Concurrent spans overlap and cannot be summed into wall time.

| P | phase | A | B | C |
|---|---|---:|---:|---:|
|1|writer Fork|16.153|13.847|15.322|
|1|sample|41.046|33.861|37.992|
|1|test body|1.222|0.876|1.063|
|4|writer Fork|26.935|24.126|25.463|
|4|sample|62.569|53.717|58.573|
|4|test body|1.597|1.192|1.518|
|8|writer Fork|33.506|25.869|34.892|
|8|sample|104.593|88.149|96.168|
|8|test body|2.458|1.671|2.593|

Not every phase improves: P8 writerFork and test-body p50 are higher for C. The conclusion is about the complete suite, not uniform acceleration of all operations. Median maxRSS bytes A/B/C: P1 206749696/212369408/206405632; P4 405225472/414203904/408600576; P8 668041216/666058752/661487616. Full phase sums/counts and all process records are in summary.json/records.json/campaign.

## What this settles, and what it does not

The counterfactual now supports a benefit without broad MemoryEA inlining. The compiler-level explanation (normal-path stack stores and duplicate addition removed by recognized no-return panic) is supported by assembly. It does not establish that exactly those three instructions account for every observed millisecond; code layout, scheduling and secondary effects remain possible.

The scoped experiment is complete. If the Human chooses productization, bring only the direct-panic/noinline helper delta and dead-helper cleanup into an isolated current-main candidate, reflect the canonical wasm2go patch, regenerate, update provenance/license records, and perform a finite correctness/performance/distribution-size/platform qualification. Do not merge this evidence branch or assume previous-source results automatically hold on current main. Further hot-path targeting or shared-label emitter changes are not prerequisites to evaluating this smaller candidate.

## Reproduction and execution record

run.py → stage1 gates → measure.py → analyze.py; verify.py is an independent raw-record check. Scripts expect evidence/ with sibling worktree/ and temp/. Use Python3.14 and the fixed source. The managed workspace runner monitored6GiB owned budget/minimum6GiB free, overall5400s; each build/runtime command1200s, suite process180s (Go timeout150s), campaign900s. durational records are saved but are not cold-build benchmarks. A harmless Python positional-maxsplit deprecation warning is retained in console.log; all commands succeeded. No retries, no changed measurement cohort, no integration or release.
