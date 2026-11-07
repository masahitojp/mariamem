# Bounded purge-before-capture A/B

**結論:** Forkの約5msを減らすための自動purge待ちは、今回の条件では勧めません。履歴数とFork後のUNDOフラグは変わりましたが、rollback segment復元は約5.38→5.26ms、Fork中央値は約28.55→28.60msでした。準備込み48子の所要時間は約1.91→2.75秒に増えました。

**得られた切り分け:** 空UNDOでも約5msのrseg復元費用が残ります。「非空UNDOだけが主要因」という仮説は支持されません。次に最適化対象を探すなら、待ちを延ばすのでなく、rseg復元内のヘッダー読込み・検証・管理状態構築が対象です。今回それぞれの内部時間を測ったとは主張しません。

**最も強い反対点:** 診断付きではCloseと準備後バッチが短縮しました。多数の子で償却できる可能性は残ります。ただしownerログ量が大きく変わり、通常実行の効果とは切り離せていません。この限定的な可能性を理由に、今回の待ち案を既定化したり追加計測を無制限に続けません。

## Fixed experiment

One macOS arm64 host; P1 pipe route; same diagnostic binary, static-page image, prepared schema/seed and fixed waves. Three alternating pairs x48 children per arm. `now` reads history once and captures. `drain` observes history with20ms polls, at least100ms of opportunity, then captures on two consecutive zero observations or the1s deadline. It does not force purge, change engine settings, or disable validation.

The deadline bounds additional sleeping/polling; an in-flight SQL query/scheduler delay can finish slightly after1s. The entire preparation observation has a1.5s context deadline. Primary measured wait phases were1002.2–1004.8ms; do not interpret the plan's1000ms as a hard total wall-time quota.

Status query: `SHOW GLOBAL STATUS LIKE 'Innodb_history_list_length'`. The [MariaDB status-variable documentation](https://mariadb.com/docs/server/ha-and-performance/optimization-and-tuning/system-variables/innodb-status-variables) defines this history counter; it is distinct from the startup `undo_log_nonempty` branch observed by the existing diagnostic. Missing/invalid status fails closed; no fallback query or extra build was needed.

## Result

Primary144 children per arm; no exclusions. Mean stage values except explicitly labelled medians, ms:

| Metric | now | drain |
|---|---:|---:|
| Root history, initial → final | 2 → 2 | 2 → 0 |
| Fork startup empty/nonempty branch | 0 /144 | 144 /0 |
| rseg-array restore mean | 5.37566 | 5.26445 |
| rseg median of process p50 | 5.30835 | 5.22413 |
| Fork mean | 29.32808 | 29.03622 |
| Fork median of process p50 | 28.55075 | 28.59556 |
| Child Close mean | 5.6254 | 2.4261 |
| 48-child batch, median process | 1809.69 | 1638.21 |
| Preparation +48 children +cleanup, median process | **1905.02** | **2749.95** |

All three drain primaries ended with history0 and all children took the empty branch. Only **1/3** primaries met the stricter two-consecutive-zero criterion before exit; **2/3** reached the finite timeout with one final zero observation. Timeout is a recorded policy outcome, not a successful stable-zero claim or a runtime test failure. Including pilots, warmups and negative controls, now has197 nonempty children and drain197 empty children.

| Pair | Added preparation | Batch difference | Complete suite difference | Fork p50 difference |
|---|---:|---:|---:|---:|
| 0 | +998.69 | -183.36 | +815.33 | -0.168 |
| 1 | +1005.28 | -170.16 | +835.12 | -0.544 |
| 2 | +1012.92 | -133.30 | +879.61 | +0.293 |

Every pair is slower end to end at48 children. rseg remains near5ms with empty UNDO. The Fork median is mixed; a robust practical Fork speedup is not established. We do not infer stage CPU from elapsed time.

The measured Close difference explains most of the batch decrease (~3.2ms per child). It needs caution: the full campaign's retained owner event counts are **324559 now versus1519 drain**, and legitimate no-event owner files serialize `events:null`. Diagnostic work and log disposal differ by arm. We cannot separate observer overhead from ordinary Close work in this one observer-on campaign. There is no observer-off claim.

A purely arithmetic extrapolation of the diagnostic batch savings would amortize the extra preparation after roughly261/284/365 children in the three pairs. Those counts assume linear savings and unchanged state/scheduling, neither tested here, and the observer confound remains. They are **not a recommended threshold or evidence for a longer suite**. No extra sample was run to reach break-even.

## Decision and limits

Recommendation: **do not add automatic pre-capture purge waiting for Fork acceleration** on this evidence; close this bounded hypothesis. Preserve the Close/batch observation as conditional evidence, not an adopted benefit. Waiting changed state as intended, so the lack of a substantial rseg improvement is informative. It does not prove that all snapshots, undo histories or purge policies behave alike.

A future voluntary investigation could examine rseg header/slot validation and runtime reconstruction, or validate ordinary Close effects if a concrete use case justifies it. No such follow-up is started here. No engine validation/recovery was skipped and no guest/product/API change is proposed by this report.

## Controls, identity and retention

Binary/source_commit **68e9713453b1cbac3739fb255605103430fb216f**; same executable for both arms with VCS.modified=false, original hash and overlay identities in inputs.json. Guest unchanged SHA256 `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`. The exact rseg/UNDO mapping is inherited from benchmarks/trxstartupsplit/layout.json and its source-bound report; only preparation harness/report fields were added here.

Two semantic pilots (4 children each), two expected wrong-seed controls (1 each), two warmups (48 each), six primaries (48 each): **12 processes /394 children**, all retained with complete untruncated owner logs and original timing/report/console archives. Exact state/UPDATE/pristine isolation, branch/phase/non-overlap/add-back, wave order and final zero mappings/image FDs all pass. No primary stage/API spans>100ms were removed (none occurred). Eleven independent reducer mutations rejected, including invalid history and missing trace markers. Fake-clock/race tests cover no-wait, progress, already-zero minimum wait, never-zero deadline, invalid mode, observation error and cancellation.

Reduction first rejected legitimate `events:null` in zero-event owner files. The collector was corrected to count that as zero, retaining the original file and digest; no measurements or processes were repeated. Original observations were not edited. Collection and replay checks run after the correction.

Reproduction from this results directory: `python3 -B analyze.py . --check`, `python3 -B check_analysis.py`, `python3 -B extra.py --check`; verify SHA256SUMS.json. All use retained data without build/temp state or original-input mutation. summary.json retains every process distribution, wait observation and pair. extra-summary.json retains all child span, suite/batch CPU, Fork CPU and lifetime max-RSS summaries; lifetime RSS is not a per-DB retained-memory experiment. Original process reports/logs/merged timing JSON, full owner archives and their original member hashes are retained.

For a new campaign use the measured source with benchmarks/purgebeforecapture/build.py then run.py in an owned workspace under the recorded budgets. The policy has one build and this fixed matrix, not authorization for more samples. No guest/native rebuild, Linux/parallel acceptance, CI, product adoption, main integration, qualification, version or release occurred. Completed isolated build/worktree is disposable; only compact evidence and Git history are retained.
