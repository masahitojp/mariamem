# Rollback-segment startup: page acquisition versus slot scanning

**結論:** Forkのrseg復元平均5.46msのうち、**rsegヘッダページ取得が4.67ms（約86%）**でした。空スロット走査は平均0.472ms、中央値0.448msです。事前の中央値0.5ms条件を満たさないため、今回の「空スロットのまとめ読み」は試作へ進めません。全く効果がないと証明したわけではなく、支配的な処理を優先する判断です。

**推奨:** 次に調べるなら、この128回のヘッダページ取得で何が起きているかに絞ります。buffer-pool hit/miss、読込み・完了待ちなどの時間を分ける最小観測が候補です。今回の4.67msは取得関数の経過時間であり、物理I/Oやディスク待ちの時間とはまだ断定できません。追加観測や最適化は本タスクでは開始していません。

**最も強い反対点:** スロット走査は0.5msに近く、3組目のprocess中央値は0.520msでした。小さな改善の可能性は残ります。ただし3組ともrsegヘッダ取得が支配的で、走査の完全除去さえ全5msを消せません。条件を後から下げたり、標本を追加して判定を変えたりせず、今回の優先順位判断を保存します。

## Measured result

One macOS arm64 host, Go1.27.3, P1 fixed waves, three alternating Fresh/Fork primary pairs x48 children per route, same diagnostic binary, prepared baseline, warm static-page prototype and application state. Pipe/no TCP. Means over144 primary children per route, milliseconds:

| Component | Fresh | Fork |
| --- | ---: | ---: |
| TRX_SYS page acquisition |0.01384|0.01693|
| Space-header page acquisition |0.00020|0.15925|
| **Rseg-header page acquisition** |0.00013|**4.67127**|
| History-page acquisition |0|0.03630|
| Slot scanning, excluding nested undo reconstruction |0.00375|0.47224|
| Actual undo reconstruction |0|0.03779|
| Residual, including other restoration and observer overhead |0.02367|0.06626|
| **Enclosing rseg restoration** |**0.04158**|**5.46003**|

These exclusive components add back to the enclosing rseg interval for every child. Header acquisition is85.55% of mean total, exclusive scanning8.65%. Means add; independently computed quantiles do not.

Fork pooled per-child p50/p95: total5.18015/6.19208ms; rseg-header4.43056/5.30238ms; exclusive scan0.44821/0.53392ms. Actual undo reconstruction p50 is0.03640ms. API Fork p50 is28.42973ms; Fresh API p50 is24.93306ms. These are diagnostic times, not ordinary performance or an optimization comparison.

| Fork primary process | Rseg total mean | Rseg-header mean | Exclusive scan mean | Exclusive scan p50 |
| --- | ---: | ---: | ---: | ---: |
|0|5.1680|4.4208|0.4476|0.4410|
|1|5.2427|4.4838|0.4547|0.4440|
|2|5.9694|5.1091|0.5144|0.5196|

The third process is slower across components, not uniquely in scanning. No causal explanation for that process difference is established. Early indices0–7 versus8–47 mean rseg times are5.201/5.161,5.157/5.260,5.903/5.983ms respectively. This does not show a consistently slow first wave. All observations remain; no per-child rseg span or API/SQL/cleanup span exceeds100ms in this campaign.

## Counts are now observed, not just source predictions

All144 primary children in each route report these same counts:

| Count per child | Fresh | Fork |
| --- | ---: | ---: |
| Page size, bytes |16384|16384|
| Registered persistent segments restored |1|128|
| TRX_SYS page acquisition calls |128|128|
| Space-header / rseg-header acquisition calls |1 /1|128 /128|
| History-page acquisition calls |0|2|
| Scanned slots |1024|131072|
| Null slots |1024|131071|
| Non-null slots / actual undo reconstruction calls |0|1|

Fork's null fraction is99.999237%, so the null-dominance condition passes. The pooled per-child median exclusive scan0.448ms fails the predeclared0.5ms condition. `decision.json` deterministically records `DO_NOT_PROTOTYPE_GROUP_SCAN`. This is not a statistical equivalence/no-benefit claim; three pairs are a bounded priority screen.

The source explanation is confirmed at the observed function: Fresh restores its first persistent segment and creates the remaining ones later; Fork restores the prepared database's registered128. The small Fresh rseg interval is not the cost of all Fresh segment setup. See the [source check](https://github.com/masahitojp/mariamem/blob/a0cb285170ec4c655de17c2dfb593ff60f50aff8/docs/reviews/rseg-source-check/README.md).

Non-null slot count is not an active/uncommitted transaction count. Cached or history-related undo objects also have startup work. Page calls are not unique pages or physical reads. No cache-hit/miss, page checksum CPU, physical I/O bytes, or read-wait partition was measured.

## Instrumentation and measurement limits

Binary source_commit **9d4e55a4892a80aec389ade735ba7bc2671360fd**.

Guest SHA256: `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`. Native source_commit: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`. `inputs.json` binds the binary hash, VCS build info, overlay chain, guest and plan. `git_identity.require_commit` and clean-tree checks ran before the build and execution. The binary stayed unchanged for all processes.

The experiment modifies generated Go only through an untracked Go build overlay, leaving canonical generated source, guest, product APIs and behavior unchanged. Whole p2 and Fn17233 hashes match the earlier measured source. Four exact direct Fn18164 calls are wrapped for TRX_SYS, space header, rseg header and history page. The nested Fn16802 undo reconstruction call is timed separately. Scan starts after page-size load and ends at the normal loop exit; nested undo time is subtracted. Null counts derive from completed `page_size/16` scans minus actual undo calls, with incomplete scans rejected. No per-slot clock, logging or counter instruction is added.

The recorder is local to this invocation, bound to the existing child startup context; roots without that binding emit no cost record. One JSON aggregate is emitted in an `innodb/rseg_cost/` event. There are262 new clock reads per Fresh child and1030 per Fork child, plus final serialization/recording. Timing-hook overhead remains in the observed intervals/residual; no uninstrumented baseline was built. In particular, Fresh0.0416ms versus the earlier campaign's0.0172ms must not be called a product regression. Final Go assembly optimization, per-stage CPU, Linux performance and off-observer speedup were not measured.

## Correctness, controls and finite scope

Two semantic positive pilots x4 children, two deliberate wrong-seed negatives x1, two warmups x48, six primary processes x48: **12 processes /394 children**, no reruns or extra repetitions. Equal schema/seed, SQL behavior, independence, fixed-wave ordering and complete disposal before the next wave passed. Negative cases rejected the wrong pristine baseline as intended and cleaned up.

All394 child-owned UNDO observer logs were retained, untruncated:761331 events total. No >100ms child spans were excluded. Every original process report, console and timing record is archived with member hashes; reduction links each sample to a canonical timing hash and owner index. Final mapping/reservation/release counts and static-image owned FDs are zero. This is the existing bounded diagnostic oracle, not fresh native SQL parity or product qualification.

Focused wave race tests and observer/helper units passed. Fake-clock tests verify nested time subtraction, call counts and incomplete/invalid scans; owner binding and disabled-root behavior are checked. Fifteen private-copy reducer mutations are rejected, including missing aggregate, wrong slot count, overlapping timing and incomplete scan. Trace mutations rebind canonical hashes so semantic accounting must reject, not checksum alone. Original evidence is unchanged by negative controls.

One diagnostic Go build took131.0s; no guest rebuild, second binary, heavy CI, optimization patch, main integration, release or platform campaign. The finite plan remains in `plan.json`.

## Reproduction and retention

From this directory:

```sh
python3 -B analyze.py . --check
python3 -B check_analysis.py
python3 -B decision.py --check
```

These commands use retained inputs only. `summary.json` includes per-process distributions, every child decomposition and tails; `decision.json` includes pooled distributions and early/late groups. `observations.json.gz`, `timing-index.json.gz`, owner archives and original-process archive preserve the observations needed to reproduce the result. `SHA256SUMS.json` covers every retained file. For a new campaign, checkout the exact measured source and use `benchmarks/rsegcostsplit/build.py` and `run.py` in an experiment workspace; hashes and limits are recorded, not inferred from this report commit.

Owned binary, caches and worktree are disposable after committed/pushed preservation. Root's four pre-existing changes remain untouched. No product decision follows automatically from this diagnostic result.
