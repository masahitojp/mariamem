# Rollback-segment restoration: bounded source check

**結論:** 削減候補はありますが、約5msの支配要因はまだ確定していません。最初に確認する候補は、**空のUNDOスロットの連続範囲をまとめて判定すること**です。ページや履歴の検証を省く案ではありません。今回はソース確認で終了し、試作・追加計測はしていません。

**推奨:** 次へ進むなら、既存のrseg区間を「ページ取得」「UNDOスロット走査（実UNDO復元呼出を除く）」「実UNDO復元」「残り」に一度だけ分け、登録segment数・null/non-nullスロット数を併記します。空スロット走査が十分な費用を占める場合だけ、小さな高速経路を試作します。効果の裏付けなしにsegment数を減らしたり、復元を省いたりはしません。

**最も強い反対点:** 生成コードは空スロットのバイト順変換を既に省略しています。走査よりページ取得・待機の方が支配的なら、この候補は効きません。ソース上の反復回数を、そのままCPU費用や5msの内訳と読まないことが条件です。

## Scope and evidence

- Source-only, no runtime/product/guest/generated-code changes, build, CI or performance samples.
- Native MariaDB12.3.3 source_commit `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`. Nine GitHub files fetched at that ref, Git blob IDs and SHA256 checked; identities in `source-files.json`.
- Report context `eb1082ba1263650b83b12b472ff9dc98381ac30d`. Generated p2 and Fn17233 hashes match the earlier measured transaction-split artifact exactly; `generated-mapping.json` records the check. Core rseg/undo files are not guest patch targets in this context.
- The earlier measurements are single-Mac P1, diagnostic observer-on. [Transaction split](https://github.com/masahitojp/mariamem/blob/397aaf82f5b52abb6a7c1e02bafcc0ce88d2b29c/benchmarks/trxstartupsplit/results/README.md): rseg restoration Fresh0.017ms/Fork5.016ms means. [Purge-before-capture](https://github.com/masahitojp/mariamem/blob/eb1082ba1263650b83b12b472ff9dc98381ac30d/benchmarks/purgebeforecapture/results/README.md): now5.376ms/drain5.264ms; actual UNDO flag changed to empty but most cost remained. These are separate campaigns, not an inter-campaign speedup comparison.
- Plan: one question, <=30min active source work, <=12 upstream files, zero heavy CI/builds. Exit is a concrete candidate or no candidate; missing cost evidence is reported, not silently filled by new experiments.

## A substantive Fresh/Fork difference

Fresh creates **one** persistent rollback segment and calls `trx_lists_init_at_db_start()` at that point. Later startup creates the remaining persistent segments, filling the array to128 on successful ordinary writable startup. The source explicitly places this later creation after doublewrite setup. A prepared writable database therefore has those registered segments available to restore at the next startup. Fresh's tiny measured early restoration does not mean it avoids all segment setup across startup.

Sources: [initial creation and early restoration](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/trx/trx0sys.cc#L128-L164), [fill registered slots to128](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/trx/trx0sys.cc#L287-L348), [startup ordering](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/srv/srv0start.cc#L1785-L1799).

This is a source-derived normal-path expectation, **not newly measured per-child segment counts**. Recovery/error/read-only paths must not be generalized from it. The two routes both iterate the outer128 slots; the expensive restoration body runs only for registered ones.

## Work inside the measured function

| Work | Source-established behavior | Implication |
| --- | --- | --- |
| Locate registered segments |128 iterations, one mini-transaction and TRX_SYS page lookup per iteration |Repeated lookup exists on both Fresh and Fork; it alone does not explain their gap. |
| Restore each registered segment |Initialize its runtime state; fetch space header page0, release it, fetch rseg header |Multiple segments may repeat lookup of the same space header. A lookup may be a buffer-pool hit, read, or wait. |
| Inspect UNDO slots |For each restored segment, examine `srv_page_size /16` slots |At16KiB,1024 slots per segment;128 registered segments imply131,072 checks over512KiB of slot fields. This is conditional arithmetic, not an observed page-size/count/performance result. |
| Restore actual UNDO entries |Only non-null slots invoke undo reconstruction; cached UNDO is also reconstructed |An empty-history/empty-UNDO classification does not mean every slot is null. |
| Restore history and max IDs |Validate and load conditional history nodes; update transaction/binlog metadata |Purge can remove history work without removing registered-segment headers and slot scanning. |

Sources: [outer loop and restoration](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/trx/trx0rseg.cc#L596-L726), [per-segment headers and history](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/trx/trx0rseg.cc#L453-L574), [slot loop](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/trx/trx0rseg.cc#L420-L446), [slot count](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/include/trx0rseg.h#L50-L54).

Actual undo restoration reads/validates state, offsets, transaction IDs and pages, then creates an undo memory object and links it to the active/cached list. **The131,072 conditional checks are not131,072 allocations.** Per-segment runtime objects are in a fixed array. [UNDO reconstruction](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/trx/trx0undo.cc#L960-L1188).

## Candidate ranking and safety

### 1. Group contiguous empty slot checks — first candidate, unmeasured

Every slot contains either `FIL_NULL` (all bits1) or a page number. A possible fast path can check several slots together; only an all-null group may advance without individual processing. A mixed group must use the existing per-slot restoration in original order. This preserves checking all bytes and processing every non-null entry, including invalid ones, rather than trusting an earlier "UNDO empty" flag.

The measured generated Fn17233 already reads a32-bit value and compares it to-1 at L85. Byte reversal and Fn16802 (undo reconstruction) occur only on the non-null L87 path. Thus "remove an endian conversion for every empty slot" is **not** a candidate: it is already removed. Grouping may still reduce branches/address checks, but neither emitted assembly nor its cost was measured here.

Any eventual guest C fast path needs bounded unaligned-safe loads (e.g. memcpy, not aliasing-unsafe casts), no reads past the slot range, supported page-size handling, and the same fallback/error behavior for mixed/corrupt entries. Tests should place a non-null entry at each group boundary and the final slot, and compare exact restored state/error behavior. Product adoption would also require ordinary observer-off Fork/whole-batch confirmation and both-platform acceptance; no such adoption is proposed here.

### 2. Avoid repeated metadata-page lookup — secondary, defer

TRX_SYS is acquired128 times; the space header is acquired for every registered segment even when the space is shared. Caching descriptors or hoisting a validated lookup might reduce repetition, but retaining page pointers/latches across mini-transactions changes lifetime/lock assumptions. Background IO also exists during startup. Do not hoist raw pointers or skip header recovery simply because application transactions have not started.

If page acquisition dominates, measure hit/read/wait contributions before choosing this change. `buf_page_get_gen()` explicitly handles buffer-pool hits, missing pages and read waits, so an acquisition count is not a disk-read count. [Buffer-pool implementation](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/buf/buf0buf.cc#L2766-L2820).

### Not selected

- Reducing the128 persistent segments is a concurrency/format/engine policy change, not a local redundant-work removal; normal startup fills them back to128. Do not assume an old `innodb_undo_logs` tuning knob controls this loop.
- Skipping restoration when history length is0 is unsafe as a general deduction: cached entries, IDs and header validation remain.
- Sharing restored runtime objects across children is a much larger ownership/locking architecture change.
- Automatically waiting for purge remains rejected for Fork acceleration in the measured workload.

## Concrete next observation, if approved

One diagnostic build, existing P1 harness, at most three alternating Fresh/Fork primary pairs. Aggregate per Fork rather than recording timestamps for131k individual slots. Count registered segments, scanned/null/non-null slots and requested header pages; record page size. Split elapsed time into header acquisition, slot loop excluding nested undo reconstruction, actual undo reconstruction, and residual, adding back to the enclosing rseg interval. Keep existing SQL/isolation/cleanup controls and complete UNDO-owner logs. Record early/late samples separately if timing changes over the batch.

Suggested decision threshold to fix **before** that run: group-scan prototype only if the exclusive slot loop has per-child median >=0.5ms (about10% of the present interval) and null slots dominate. Below that, close this candidate; if measurements cannot separate the components within <=30min tooling/one build, report inconclusive. Timing pairs around128 segment loops may themselves perturb the measurement, so report hook counts and keep the result diagnostic until observer-off validation. This proposed observation has **not been run**.

## Verification and retention

`anchors.json` retains14 line ranges with excerpt SHA256; `source-files.json` retains fixed Git blob/file identities; `generated-mapping.json` binds the exact earlier measured function. `verification.json` is a source-check PASS only. `SHA256SUMS.json` covers the report and retained manifests/scripts.

To re-fetch, copy `acquire.py`, `plan.json`, and `source-files.json` into a disposable `evidence/` directory and invoke `python3 -B evidence/acquire.py` with the nine paths from the manifest. It writes upstream sources under sibling `temp/upstream/` and checks existing manifest identities. Run `verify.py TEMP_UPSTREAM EXACT_WORKTREE` from this report directory to check sources, anchors and generated function against retained hashes. No full upstream/generated source copy is retained here; the pinned sources and Git history reconstruct it. Owned scratch is removed after preservation. Existing unrelated root changes remain untouched.
