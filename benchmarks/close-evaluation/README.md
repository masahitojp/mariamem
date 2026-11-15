# Close待機方式の有限比較 — #206

**結論:** guest停止後のcleanupと次のFork受付を安全に重ねる機構は確認できた。一方、最終drain込み全体wallの短縮は空き枠ありでもペア中央値1.38〜2.65%で、全ペアには再現しなかった。**現候補の非同期入口をこのまま製品採用することは保留を推奨する。** #119の0.7.0スコープを取り下げる決定ではなく、採用する差分のHuman判断を待つ。70テストへの拡大は自動で開始しない。

最も強い継続理由はP2/cap4で4/5ペアが速く、peak RSSの増加も観測しなかった点。ただし短縮は約7.85ms/48子、CPUはペア中央値2.46%増で、同じ小fixtureの結果だけでは公開API・最終drain・失敗所有権の複雑さに見合う全体利益をまだ示せない。#203の解放失敗対策の正しさ・採用価値は、非同期化の速度とは切り離してレビューできる。

## 固定対象と完了範囲

- Product source_commit: `f563128520fc49097ac83ef47cdea2dee21ff62a`（#203–#205接続済み、未統合候補）。
- 計測harness source_commit: `4066c92606d1b9d7cc5c784e6f1b8891ce1cbf4c`。追加はtest/driverと公開ファイル一覧だけで、productコード変更なし。
- Apple M1 / MacBookAir10,1 / 16GiB / macOS27.2.1、Go1.26.10、GOMAXPROCS8/GOGC100。主・診断CGO0、raceのみCGO1。
- Guest SHA256: `77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450`。
- 40本の主計測（20ペア、1,920子）、warmup8本、診断8本、smoke2本、race2本。全60プロセス・2,880子がSQL・Wait/Disposed・lease返却・mapping数復帰を成功。失敗・除外0、外れ値はすべて保持。
- 既存Go7パッケージと実guest gate/Snapshot/worker trapを先行確認。#203から不変のbase mapping/descriptor失敗注入テストも同treeで追加確認。公開境界Python10件もPASS。

ビルド前にgit_identityとclean statusを確認した。測定は同じplain binaryを環境変数だけで切り替えた。診断はtest定数false→trueだけのoverlayで別binary。ビルド・race・診断は主計測と重ねていない。binary SHA・実buildinfo・UTC順序・load average・全run値は [results.json](results.json)、独立再計算は [analyze.py](analyze.py)、集計は [summary.json](summary.json)。

共有ホストの有限観測で、A/Aや信頼区間による雑音分離はしていない。結果は保証値・別OS・旧mainとの製品全体比較ではない。両armに共通の安全性修正・Close operation・producer費用を含む。

## 主結果 — 最後の解放待ち込み

1,000行を1回準備/Snapshotし、48子をP workerで処理。各子はCOUNT/SUMの初期値検証、id0更新、更新結果確認、SQL pool終了/WaitDisconnectedを行う。主timerは最初のForkから全handleのWait/Disposed確認・Snapshot.Closeまで。process wall/CPU/peak RSSは準備・process終了も含む。

「ペア差」は各ペアのstop−sync、比率はstop/sync−1の中央値。**両armの独立中央値の差とは異なる。** 負は短縮。

| P / MaxForks | 条件 | ペアwall差中央値 | ペア比中央値 | 速かったペア | 全ペア比の範囲 |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 / 2 | 空き枠あり | −24.35ms | −2.65% | 3/5 | −7.60〜+14.73% |
| 2 / 4 | 空き枠あり | −7.85ms | −1.38% | 4/5 | −3.30〜+6.45% |
| 1 / 1 | 飽和 | +3.23ms | +0.35% | 2/5 | −2.94〜+1.60% |
| 2 / 2 | 飽和 | +7.27ms | +1.34% | 2/5 | −5.19〜+190.48% |

| P / cap | 同期batch独立中央値 | 停止待ちbatch独立中央値 | 同期drain独立中央値 | 停止待ちdrain独立中央値 |
| --- | ---: | ---: | ---: | ---: |
| 1 / 2 | 947.20ms | 911.34ms | 0.014ms | 1.023ms |
| 2 / 4 | 569.79ms | 561.94ms | 0.016ms | 1.590ms |
| 1 / 1 | 930.93ms | 915.74ms | 0.017ms | 0.986ms |
| 2 / 2 | 560.16ms | 574.43ms | 0.016ms | 1.845ms |

drainはworker終了から最後のhandle確認とSnapshot.Closeまで。停止待ちの早期返却により最後に残った時間を主timer外へ追い出していない。工程は重なるためAPI短縮×48を全体短縮として足し算しない。

## CPU・メモリ

以下も全5ペアの比率中央値。

| P / cap | batch CPU差 | process CPU差 | process wall差 | process peak RSS差 |
| --- | ---: | ---: | ---: | ---: |
| 1 / 2 | −1.43% | −1.45% | −3.56% | −0.14% |
| 2 / 4 | +2.46% | +2.54% | −0.86% | −0.34% |
| 1 / 1 | +0.82% | +0.62% | +0.04% | −0.05% |
| 2 / 2 | −0.11% | +0.66% | +4.76% | −0.71% |

CPUの一律削減は確認できない。独立peak RSS中央値はP1で約127MB、P2で約228MBで、同cap両armに大きな差はない。小さい差をメモリ削減効果とはしない。これは各fresh processのhigh-water markであり、定常子保持量・unique物理RAMではない。全handleは最終監査まで保持する共通harnessで、通常アプリのGC/lifetime差まで代表しない。

## 診断 — 何が重なったか

別診断各1本で、同期APIのclose p50は1.86〜2.67ms、停止待ちの返却は0.88〜0.97msになった。全停止待ち192子でbackend cleanup終了より前に返却した。

| P / cap | 同期close p50 | 停止待ち返却p50 | 同workerの次Fork受付が前cleanupと重なった数 | 最大観測pending cleanup | 最大sampled mapping数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 / 2 | 1.898ms | 0.879ms | 47/47 | 1 | 1 |
| 2 / 4 | 2.673ms | 0.970ms | 46/46 | 2 | 2 |
| 1 / 1 | 1.863ms | 0.899ms | 0/47 | 1 | 1 |
| 2 / 2 | 2.559ms | 0.932ms | 2/46 | 2 | 2 |

同期は全cellで同workerの重なり0。P1/cap1では早く返しても次ForkのAcquireへ待ちが移る。P2/cap2は共有poolなので他workerの返却枠を使う少数の重なりがあり、「飽和なら絶対ゼロ」ではない。

stopped→backend cleanup終了のp50はP1約0.94ms、P2約1.32〜1.34ms。残るruntime/transport/transfer処理を含む区間で、munmapだけの費用ではない。Fork受付の重なりは確認したが、guest初期化のどの命令とメモリ解放が重なったかは分離していない。

mapping数はstage時点のsample最大で、真の最大値の下限。既存のpeak logical RW bytesはP1約775MB、P2約1.55GBで両arm同じだったが、guestのgrowがあるためこれをmapping個数や物理RSSへ換算しない。P1空き枠ありの次Fork受付では前子mappingの保持も観測した。

observerは時計・mutex・mapping sample・wrapperを追加する。診断batchはP1で約1.15〜1.18秒、P2で約0.64〜0.66秒と主計測より遅かった。観測負荷と時点の環境差は分離しておらず、診断の時間・重なり頻度を無観測性能へそのまま外挿しない。

## 大きい遅延と #162

P2/cap2のpair2ではsync560.165msに対しstop1627.187ms（+1067.023ms/+190.48%）。削除も再試行もせず集計に含めた。遅延の大部分はworker処理中で、最終drainは1.845ms。主計測では工程ごとの時計を外しているため、Fork・SQL・Close・スケジューラのどこかは未特定。CPUは+約218msで、wall全増分と等しくない。

#162の「#119受入れ内で再現の有無を確認」の条件とも照合した。診断384子のうち、同期Close192子は最大6.808ms、100ms超0。残る192子の停止待ちAPI返却は別の完了境界であり、同期Closeの分布に混ぜない。全runでtimeout/未回収0。**計時した同期Closeでは410ms/40秒事象は未再現。** 主計測のClose単体は計時していないため、上のbatch外れ値をClose由来とも、Closeではないとも断定しない。#162の原因解消・修正済みとはしない。独立の追加再現campaignは開始していない。

## 安全性と残る判断

停止前の解放禁止・worker gate・reader gate・最後のexport応答・構築失敗・trap・取消しは既存の制御/実guestテストで確認。#203のfailed mappingだけのretry、generic descriptor失敗保持、runtime→guest→host→leaseの未解放保持、ファイル削除失敗owner、watch/並行Close、Snapshot.Close競合も同じproduct treeで確認した。実OSの障害全般を再現したものではない。

全60 runでSQL初期値/更新、48 handleのWait/Disposed、lease0、active mapping/reserved/RWのbaseline復帰、48 create/48 release、release/grow failure増分0を確認した。通常テスト・smoke/race・warmup・主計測・診断を混ぜず保存している。

この有限比較と分析は完了。#119は0.7.0の対象のまま、採用差分はHuman判断待ち。Codexの推薦は現方式の非同期APIの採用保留であり、scopeからの除外決定ではない。70テストでの再評価を優先するなら同じ候補を使う有限計画が次に必要。長いCloseの原因確認は実際の遅い個体の工程/stackが不足し、#162の既存observer準備目安20〜30分と次の受入れ内の有限観測が候補になるが、今回の結果から自動開始しない。

main統合・公開API・全platform受入・releaseは行っていない。#203の正しさ修正を単独で採用する場合も、最小差分と対応CIのレビューが必要。

## 再検算と再現

```
python3 benchmarks/close-evaluation/analyze.py benchmarks/close-evaluation/results.json
```

validatorは60run/40本/20pair、全cell・arm、エラーなし、resource復帰、各診断childの7eventと順序を検査して全表を再計算する。結果bundle約320KBに全runを保持し、binary/cacheは保存しない。

測定の再実行はcleanな計測SHAからexperiment-workspaceをprepareし、`campaign.py <workspace>`をguarded runnerで実行する。主/診断/両armは同じsource。追加base確認は `go test -p 1 ./internal/generatedgo/code/base`、公開境界はPython3.14の `unittest discover -s tests -p test_release_tools.py`。実行前の固定計画を以下に保存する。

---

# Finite Close evaluation (#206)

Plan: same connected product source f563128520fc49097ac83ef47cdea2dee21ff62a,
Go1.26.10/macOS arm64, GOMAXPROCS8/GOGC100. Build identities and the committed
harness source_commit are recorded before running. No product runtime edits.

Each fresh process creates 1,000 (id,v=id) rows, snapshots once, then processes
48 private children with P workers. Each child verifies COUNT/SUM, updates id0,
verifies its value, closes its SQL pool and waits for disconnect. Compare public
Close with internal stopForCleanup. Every handle is finally Waited and Disposed
checked, all leases must return and mapping count must match pre-batch baseline.
The primary timer includes all 48 children, final drain and Snapshot.Close.
Process wall/CPU/peak RSS include setup and process exit. Batch CPU is sampled
at the two batch endpoints; no per-stage instrumentation runs in the plain build.

Cells P/cap = 1/2, 2/4, 1/1, 2/2. Separate one-process warmup per arm/cell,
then five alternating pairs per cell = 40 measured processes. Round order rotates
cells; even rounds sync→stop, odd rounds stop→sync. Fixed 150ms inter-process
pause. Diagnostic runs follow all measurements: one per arm/cell, separately.
Smoke and two race workload processes precede warmup. All runs, failures and
outliers are retained. No extra sampling or removal of slow pairs is authorized.

The diagnostic overlay changes only evalDiagnostic=false to true, adding
backend close/stopped/cleanup-end events and mapping samples. It calls the same
admission Acquire then forkReserved path to mark real startup admission after
waiting, whereas the plain arm uses public Fork. Its cleanup window includes
remaining runtime/transport/transfer work, not only munmap. Event recording can
perturb scheduling; do not use its times as the performance estimate. Mapping
counts are point samples (a lower bound on the maximum); the runtime's existing
peak logical RW bytes counter is also retained, not equated to physical RSS.

Both arms include #203–#205. This isolates waiting policy within the candidate,
not its total overhead relative to old main. No public async API or adoption is
established. Improvement must include final drain; unconfirmed disposal fails
the run. If no consistent whole-batch benefit appears, recommend withholding
adoption rather than expanding into an indefinite search. 70-test suite and
platform qualification require a separate continuation decision.

Budget: one local host, two hours active work, at most 90 minutes per guarded
execution, 16GiB owned scratch and 12GiB free-space reserve, no heavy CI.
If a safety failure or budget breach occurs, stop, preserve evidence and report
what remains rather than dropping requested cells or checks.

Run the committed campaign with a prepared experiment workspace path argument.
The experiment-workspace runner supplies TMPDIR/GOTMPDIR and storage guarding.
