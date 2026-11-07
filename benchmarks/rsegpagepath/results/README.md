# Rseg header acquisition: read miss, I/O and read completion

**結論:** Forkのrsegヘッダ取得平均4.53msのうち、**読込み後の `buf_page_t::read_complete()` が4.23ms（約93%）**でした。同期I/O要求は0.179ms。確認した二つの明示的な `read_wait` 経路は0回です。次の焦点は読込み後の検証・復旧処理であり、今回の結果からread thread数やI/O並列度を変えることは勧めません。

**推奨:** 次へ進むなら、`read_complete()` 内のページ検証／チェックサムと条件付きrecoveryを区別し、検証を保ったまま計算を速くできるかを確認します。CRC処理のホスト側高速化などは候補ですが、今回の4.23ms全部をCRC費用とは呼べません。最適化・追加観測は本タスクでは開始していません。

**最も強い反対点:** 観測したのは関数の経過時間で、CPU時間ではありません。`read_complete()` は復号・展開の判定、ページID、破損／チェックサム検証、条件付きrecovery、状態更新とunlockを含みます。どれが支配的か未計測なので、checksum無効化・recovery省略・「CPUだけが原因」という結論は出しません。明示的read_waitが0でも、同期IOや下位関数内の全待機がゼロと証明したわけではありません。

## Result

Single macOS arm64 host, Go1.27.3, P1, three alternating Fresh/Fork primary pairs x48 children each, same diagnostic binary, warm static-page prototype, equal application schema/seed, Pipe/no TCP. Primary Fork per-child means over144 children:

| Exclusive part of rseg-header acquisition | Mean ms |
| --- | ---: |
| Buffer-pool hash lookup |0.00605|
| Frame initialization inside read miss |0.02050|
| Synchronous IO request |0.17932|
| **Read completion (validation/recovery/state updates)** |**4.22586**|
| Race-to-existing-page read_wait |0|
| Other read-miss work |0.04489|
| Random read-ahead function |0.00538|
| Read-wait for an in-flight cache hit |0|
| Other page handling/latching |0.03394|
| Measured wrapper difference |0.01512|
| **Total header acquisition** |**4.53105**|

Read-miss inclusive mean is4.47057ms; do not add it to its nested parts. Every child has nonnegative residuals and exact add-back through both nesting levels. `read_complete` is93.26% of the mean header interval. Its pooled per-child median is4.16540ms and median per-child share93.58%, meeting the predeclared dominant-path criterion (>=0.5ms and>=50%). `decision.json` records `DOMINANT_PATH_IDENTIFIED` with only `header.read.read_complete` selected.

Whole rseg restoration mean/p50/p95:5.33007/5.24210/5.71058ms. Header acquisition:4.53105/4.45622/4.85942ms. Read completion:4.22586/4.16540/4.51438ms. Fork API p50 is27.04940ms. These diagnostic values are not an ordinary-speedup claim; the previous campaign's4.67ms and this campaign's4.53ms use different instrumentation and independent executions.

| Fork primary process | Header mean ms | Read-completion mean ms | Read-completion p50 ms |
| --- | ---: | ---: | ---: |
|0|4.4375|4.1404|4.1175|
|1|4.4263|4.1443|4.1277|
|2|4.7294|4.3930|4.3181|

Read-completion means for indices0–7 versus8–47 are4.131/4.142,4.130/4.147,4.399/4.392ms. There is no consistent first-wave-only elevation in these samples. All samples/tails remain. No child API/SQL/cleanup or rseg span exceeds100ms in this campaign; no tail exclusions or extra repetitions.

## Observed path counts

All144 primary children in each route have identical counts:

| Per child | Fresh | Fork |
| --- | ---: | ---: |
| Rseg-header acquisitions |1|128|
| Initial buffer-pool hits |1|0|
| Initial buffer-pool misses |0|128|
| Read-miss calls |0|128|
| Frame-init / sync IO / read-complete calls |0 /0 /0|128 /128 /128|
| Random-read-ahead function calls |0|128|
| In-flight-hit read_wait calls |0|0|
| Race-to-existing-page read_wait calls |0|0|

Random-read-ahead invocation does not mean pages were prefetched; its0.005ms interval includes early exits. Initial miss does not generally prove an IO was performed, because another reader could win the race; the nested IO/completion counts establish the path in this workload. IO requests are not physical disk accesses: mariamem has its own host/file backing, and this measures `fil_space_t::io` wall time, not device latency or storage bandwidth.

Fresh's first persistent header already exists in its buffer pool. Fork starts with file state and restores128 registered segments. Thus the path difference now includes both restored-segment count and cache state, not merely a slow memcpy of the snapshot. This does not mean total Fresh startup avoids creating the remaining segments later.

## Source and generated mapping

Binary source_commit **`d48ecf650431380f0baf35793450c1b0c5db3733`**. Guest SHA256 **`6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`** unchanged. Native MariaDB12.3.3 source_commit **`83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`**. Two native files were re-fetched at this pin and checked against Git blob and SHA256 identities; no guest rebuild.

- [buf_page_get_gen](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/buf/buf0buf.cc#L2760-L2831) is mapped by the exact generated Fn18164 body and known caller arguments. See the source identity in `source-files.json` and the line ranges in `native-mapping.json`.
- `Fn16792` maps to `buf_read_page`; its final boolean is **unzip**, not a sync flag. It supplies a non-null error pointer to `buf_read_page_low`, which selects READ_SYNC. [Native caller](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/buf/buf0rea.cc#L504-L545).
- In `Fn16789` (read-low), frame init is Fn16791, IO request is Fn17564, completion is Fn18174, race wait is Fn16787. Multiple generated copies of these branches are all wrapped with strict occurrence-count checks. [Sync IO, completion and race wait](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/buf/buf0rea.cc#L275-L375).
- `read_complete` includes more than checksums; recovery is conditional on its argument. [Validation and completion](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/buf/buf0buf.cc#L3485-L3687). The actual recovery argument and costs of its internal validation/recovery branches were not separately captured.

`page-mapping.json` pins whole generated files, function bodies, call strings and label boundaries. The inherited UNDO-owner hook in Fn18164 at L272 is retained: raw-body and already-instrumented-body hashes are recorded separately. It was discovered during pre-build mapping, not removed or relabelled. `native-mapping.json` and `completion-source.json` retain source range hashes.

## Attribution boundaries

Only the exact rseg-header caller binds an observer, keyed by its exact generated `*Module`, not the shared ThreadPool. Sibling-worker calls and unbound roots do not contribute; reentrant page requests remain within the parent operation. The top call's lookup, read-miss, random-read-ahead and read-wait times are disjoint. Frame initialization, IO request, read-completion and race-wait are nested components within the read-miss interval only.

Data are accumulated per child in one header summary attached to the existing rseg record; there is no per-slot clock/log operation. This adds1792 clock reads per Fork child and4 per Fresh child, on top of the prior rseg observer. Instrumentation uses exact-Module map lookups and wrappers; unbound calls also pay a lookup. The measured wrapper/residual includes part of the observer cost. No observer-off overhead control, final assembly optimization analysis, stage CPU attribution, physical read counters or Linux acceptance is claimed.

No elapsed-time result is silently promoted to CPU cost. Potential source hypotheses include checksum computation, conditional recovery or lower-level services used by completion. They remain hypotheses until separately identified. The next bounded candidate should preserve all corruption checks, page identity validation and child isolation.

## Controls and finite campaign

One diagnostic Go build101.5s, same binary for two semantic pilots x4 children, two wrong-seed negatives x1, two warmups x48, and six primary processes x48: **12 processes /394 children**. All SQL/state, child independence, fixed-wave ordering, exact owner binding and cleanup controls passed. Wrong-seed cases failed as expected and still cleaned up. No process reruns or added samples.

All394 untruncated child UNDO-owner logs are retained,780151 events total. Original reports, console and timing JSON are archived with per-member hashes. Canonical timing hashes bind samples to original traces. Final mappings/reservations/release failures and image FDs are zero.

Focused wave race tests and observer units passed. Fake-clock tests cover phase accounting, nested read accounting, incomplete/overlapping phases, exact-Module isolation, nested exclusion and binding cleanup. Twenty private-copy reducer mutations are rejected, including missing header data, bad hit/miss counts, overlapping outer/nested times and incomplete calls. Trace mutations update their private canonical hashes so semantic accounting must reject; originals remain unchanged.

No optimization, canonical guest/generated/API change, heavy CI, product adoption, main integration or release was performed.

## Reproduction and retention

From this directory, after build/temp cleanup:

```sh
python3 -B analyze.py . --check
python3 -B check_analysis.py
python3 -B decision.py --check
```

`summary.json` contains every child decomposition, distributions and tails; `decision.json` contains pooled shares/counts and early/late groups. Original observations and all owner logs are retained in compressed archives. `SHA256SUMS.json` covers retained files. `inputs.json` preserves the measured source, exact binary hash, guest, plan and overlay hashes; later report commits do not relabel the binary.

To re-fetch native source, copy `acquire.py`, `native-plan.json` and `source-files.json` to disposable `evidence/`, then invoke the script with the two source paths. New measurements use the exact binary-source commit's `benchmarks/rsegpagepath/build.py` and `run.py` in a bounded workspace. Owned build/cache/worktree and archived duplicate originals are removed after preservation; pre-existing root changes are untouched.
