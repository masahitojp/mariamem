# MemoryEA: 正規生成版と製品Goのruntime・性能対照

**結論: 製品Goでも局所INSERT/CPUの利益を再現。製品採用判断には全suiteとサイズの交換条件が残る。** P8 rawは全5組改善したが、process wallは1組悪化、対応中央値-2.49%に留まる。前回Go1.27.4のprocess wall利益を現在の全体改善とは扱わない。

source_commit a35ec0accac0e8fc053ce27971ca12a1c9fe5cdb、experiment/memory-ea-runtime。Go1.26.10/macOS arm64/CGO0/GOMAXPROCS8/GOGC100。guest77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450、CI43569024494 artifact14103568702。converter archiveと全13patchを検証、新規converter→全面変換→source adapter→generate_runtime.py installerを実行した。

installerには新しいcandidate inventoryを未採用の提案入力として隔離worktreeのmanifestに一時設定し、finallyで既存pinを復元。外部outputだけを生成。これはUNQUALIFIED診断候補で、canonical採用証跡ではない。installerの検査・runtime adapter・static image生成を変更/迂回していない。installed-provenance.jsonは当該提案入力への結合を保存する。製品release pin未変更。

全出力比較: code/base/base.go、provenance.json、image/layout.jsonだけ変更。baseは同じ境界検査の直接panicと不要trap helper削除だけ。layoutはbaseソースハッシュだけが変わり、イメージ内容と他ソースは一致。正規生成した全Go/asmをoverlayで実行し、既存runtimeをそのまま流用した手編集候補とは区別する。

両armでbase全テストと既存generatedmemory全5test、TestWorkerTrapActualGuestNotifiesAndIsolatesPeer成功。OOB/幅跨ぎ/nonwrap/grow/worker共有/TLS/失敗join/CRUD/Fork/Close、worker trap通知とpeer隔離を検査。全consumer/fullrace/Ubuntuの受入れではない。

## 同条件対照

前回固定harnessを使用し、ExperimentDump/ExperimentPhaseの観測hook呼出だけを削除、go.modを1.26.0へ合わせた。製品側observer overlay/追加Module fieldsは両方なし。差分加算trigger、監査status限定、5triggers/FK/CHECK/index/注文UPDATEを両arm同じに保持。REVENUE_PREAGG=1設定保持（raw probeではquery未実行）。

P1/P8各armwarmup1＋交互5組=24process、192DB、19,200 raw INSERT。全trigger本文/合計/audit/stock/FK/CHECK/公開Close oracle成功。Fork/親注文準備/BEGIN/PREPAREとCOMMIT/oracle/Closeはraw外。全標本保存し追加反復なし。process wallはtime wrapper・起動停止等込みで70test suiteではない。

| 指標 | P1 baseline→candidate | 対応率中央値 | P8 baseline→candidate | 対応率中央値 |
|---|---|---:|---|---:|
| raw100 INSERT p50 ms |13.9035→11.3260|-17.73%|22.6450→18.8910|-16.94%|
| process wall ms |495.574→447.389|-9.85%|289.047→284.840|-2.49%|
| CPU ms |683.404→601.853|-12.92%|730.251→660.288|-10.61%|
| 最大RSS bytes |650362880→655196160|+1.06%|641794048→648970240|+1.03%|

独立5process中央値と対応round率中央値を区別。rawは各process8DB中央値。raw/CPUは両P全5組低下、wallはP1全5組・P8の4/5組低下。P8wall対応範囲+1.41%〜-16.50%。共有host、有限標本。raw改善がprocess全体に比例して現れるとは結論しない。CPUはRUSAGE_CHILDREN差分、RSSはmacOS time bytes。ビルドを計測に重ねていない。

非strip test binary 108590658→191117538 bytes（+76.00%）。配布物サイズではない。build-results秒数はruntime検査後のcacheを使うtest binary組立であり、cold compile対照として扱わない。

## 次の判断

一行のruntime改善候補として利益は支持するが、製品採用を推奨するには約76%のbinary増加と全suite利益を確認する必要がある。次は元SUM/事前集約売上SQLで全suite P1/P4/P8と配布hostサイズ・cold費用を有限対照し、両OS受入れへ進む価値を判断することを推奨。局所利益だけで他エンジンとの差10%達成を主張しない。

run.py→verify-build.py→measure.py→analyze.py。Python3.14が必要。prepare8GiB/最低空き8GiB。生成工程はhelperで監視。helperがcompleted後の再runを拒否したため、その後の検査/計測は個別timeout付きで手動実行し、専用予算監視は継続していない。空き容量確認はしたが全工程のpeakを保証しない。これは実行管理上の留保。統合/releaseなし。
