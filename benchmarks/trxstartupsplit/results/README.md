# Transaction startup: purge versus rollback-segment restoration

**結論:** Forkのトランザクション起動約5.05msのうち、rollback segment配列の復元が約5.02msでした。purge管理の作成は約0.027msです。Freshも同じ関数を別の場所から呼びますが、配列復元は約0.017msでした。

**次の候補:** Snapshot前にpurgeが進むのを待ち、UNDO状態が変わるか・その後のFork費用が下がるかを対照実験します。各Forkの仕事を一度だけの準備へ移せる可能性を、ゲスト変更より先に調べます。今回の結果だけでは高速化を確約しません。

**最も強い反対点:** 非空UNDOと費用の相関が見えても、費用の大半は全rollback segmentの読み込み・検証・管理状態復元かもしれません。その場合、purge待ちは準備を遅くするだけです。次はフラグだけで成功とせず、準備の待ち時間・Fork・バッチ全体を同じ条件で比較する必要があります。

## Measured split

One macOS arm64 host, P1 fixed waves, three alternating Fresh/Fork pairs x48 primary children per route. Per-child means, ms:

| Exact measured component | Fresh | Fork |
|---|---:|---:|
| Purge system construction | 0.02635 | 0.02660 |
| Rollback-segment array initialization/restoration | 0.01721 | **5.01638** |
| Remaining transaction-list call time | not independently bracketed | 0.00376 |
| Enclosing transaction-list call | not independently bracketed | 5.04674 |
| Broad InnoDB open/recovery host interval | 0.71327 | 6.46850 |

The rseg-array call is 99.4% of the Fork transaction-list call and 77.6% of the broad Fork interval. Fork rseg process means: **5.00309 /5.00527 /5.04080ms**. Median of process p50/p95: **5.00746 /5.15133ms**. No primary API/stage spans >100ms, no exclusions.

Fresh also calls Fn18291 (`trx_lists_init_at_db_start`) through **v12129**, before dictionary creation, while the existing-data route uses **v20211**, after dictionary loading. The previous experiment bracketed only v20211. Its Fresh zero described that specific call site being absent, not the whole function being absent. In this experiment the callee's purge/rseg components are measured on both routes; Fresh's enclosing function edges were not added, so no invented Fresh whole-function total is reported. The Fresh split lies in the previous broad residual and is subtracted there; the Fork split adds back to its enclosing call with a nonnegative residual.

## Actual UNDO branch

| Route | Main children: empty | Main children: nonempty | All children incl. pilots/warmups/controls |
|---|---:|---:|---|
| Fresh | 144 | 0 | 197 empty |
| Fork | 0 | 144 | 197 nonempty |

This observes the actual bool read used by `trx_sys.is_undo_empty() == !undo_log_nonempty`. It is not an inference from the function name or expected snapshot state. **Nonempty does not prove an uncommitted application transaction.** Source `trx_undo_lists_init()` examines undo size/state and treats cached undo as empty; persisted history/undo state and transaction resurrection are distinct. The post-rseg part here is tiny; do not call the 5ms application rollback or transaction resurrection.

## What the source establishes

Pinned MariaDB12.3.3 source_commit `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`; four files fetched with Git blob and SHA256 verification. Generated transaction caller **Fn18291**, rseg-array callee **Fn17233**, whole p2 file and caller body pinned. Purge construction is inlined from L13 to the v481 rseg call; normal rseg is wrapped at that exact call; the actual branch read at address17864585 emits empty/nonempty.

- purge graph construction uses the compiled maximum of32 nodes, but is only ~0.027ms; reducing this is a poor priority for this workload.
- rseg-array initialization loops the rollback-segment slots, reads/checks relevant headers, restores registered segments and undo lists, and initializes max transaction identity. It is more than a bulk file copy.
- The source does not show that all5ms is physical I/O, slot scanning, allocations, or checksum work. None of those internal costs was separately measured here.
- Work is in MariaDB/InnoDB startup executed through generated Go and host services. Attribution to a guest function does not establish that the host shim or code generator is irrelevant.

## Recommendation: one next experiment, not more unconditional subdivision

Test **purge-before-capture** as a bounded hypothesis: can preparation drain persisted undo/history enough to reduce repeated rseg restoration? Use the same schema/seed and normal snapshot semantics. Observe available purge/history state and actual empty/nonempty branch; do not assume a sleep proves drain. Compare no wait against a bounded wait while the prepared DB is still running, using one binary and alternating arms. Report added one-time preparation cost, per-child Fork and complete batch cost, and the break-even repetition count if there is a benefit. Preserve SQL behavior, child isolation and cleanup. Do not tune away recovery or validation.

This is a recommendation for the next step, not product direction or an optimization claim. It may be falsified: reaching the desired state may not reduce rseg cost, or a bounded wait may not reach it. Stop and record either result rather than extending waits until success. A concrete initial budget can reuse this harness (<=30min tooling, one diagnostic Go build<=20min, <=15min finite P1 alternating matrix). A useful result then needs ordinary observer-off Fork/batch confirmation before adoption. Linux and wider concurrency acceptance remain later, not prerequisites for this hypothesis screen.

## Campaign and controls

Same warm static-page prototype, baseline prepared before both routes, equal application state, one observer-on diagnostic binary. Two positive semantic pilots (4 children each), two deliberately wrong-seed controls (1 each), two warmups (48 each), six primary processes (48 each): **12 processes /394 children**, all retained with complete, untruncated UNDO owner logs. No repeated processes or additional samples. All SQL/state, wave ordering, route/phase/branch, interval containment/non-overlap/add-back, final zero mapping/image-FD cleanup checks passed with the corrected measurement criterion.

The original criterion incorrectly expected no callee marks on Fresh. The first Fresh pilot completed successfully and cleaned up, then the harness assertion rejected that expectation. Its four children and original logs were retained, not rerun. Only run.py was corrected, then the remaining eleven processes ran with **the same binary**. pilot-harness-correction.json records the change; the original plan remains historical. No runtime failure is disguised as a measurement retry.

Binary source_commit: **7254c32b97dd96297f72d71f83f78df34ad444eb**. Resume runner source_commit: recorded in runner-identity.json; its only source difference is benchmarks/trxstartupsplit/run.py. inputs.json preserves original VCS revision and binary hash, never relabelled to the later runner/report. Guest SHA256 unchanged: `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`.

Focused race harness and observer helper units passed. Eleven independent reducer mutations rejected, including missing rseg end and double branch; mutated traces rebind integrity hashes so actual phase gates must reject. No observer-off comparison, stage CPU, Linux, native SQL parity, RSS or product acceptance is claimed. Cross-campaign absolute times (e.g. previous5.62ms versus current5.05ms) are not performance improvements.

## Reproduction and retention

From results/: `python3 -B analyze.py . --check` then `python3 -B check_analysis.py`. Replay uses only retained inputs and does not rewrite them. SHA256SUMS.json covers every retained file. summary.json retains per-process distributions and pairs; observations.json.gz contains all child traces; original-process-reports.tar.gz contains original reports/console/timing JSON; all owner archives and original hashes are retained.

For source mapping, run verify_mapping.py with the measured worktree root. acquire.py uses upstream-plan.json and source-files.json to re-fetch at most the fixed four native files into a disposable workspace; copy those three files into evidence/ first. For new measurements, use the measured source and parent build.py/run.py with the recorded budgets. The original binary-source runner contains the Fresh-absence assumption; apply only the documented run.py correction to resume or write a fresh runner that checks both routes and record its own identity. Do not rerun the retained pilot.

No guest/native rebuild, product/API/guest-source/generated-source change, optimization prototype, CI, main integration, qualification, version or release was made. Diagnostic Go build102.2s, one build total. Unique measurements are preserved; the completed owned build/worktree is disposable.
