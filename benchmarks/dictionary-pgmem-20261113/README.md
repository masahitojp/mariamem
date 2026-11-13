# Dictionary wait candidate versus pgmem — 2026-11-13

**結論:** この1,000行・48子DBのPipe比較では、候補はpgmemより総時間中央値がP4で14.7%、P8で15.5%長い。CPUは約1.73倍／1.68倍を使い、観測ピークRSSは約64%／38%低い。統合前mainに対してP4は実質横ばい、P8は中央値593.4→290.0ms。これは今回の有限観測であり、一般的な高速化や自然な長時間待ちの完全解消を示さない。

[全30回のCSV](results.csv) / [集計と各ペア](summary.json) / [固定計画](plan.json) / [入力とバイナリ](inputs.json) / [ソース識別](source-identity.json)

## 条件と数値

Apple M1 / 16 GiB / macOS 27.2.1 arm64。全対象をGo 1.27.4、CGO=0で新規ビルド。実行はGOMAXPROCS=8、GOGC=100。並列数P=4/8、SnapshotのMaxForks=P、各条件5プロセス、各48子DB。各条件に除外warmupを1回、各製品に正負のpilotを1回ずつ実施。数値の良否による除外・再実行はない。

時間はms、RSSはMiB。総時間は5プロセスの中央値 [最小–最大]、CPU/RSSは各プロセス値の中央値。Fork/cleanupは各プロセスの子48個のp50を取り、その5個の中央値。CPUは全スレッドのuser+systemで、wallと異なる。

| 対象 | P | 総時間 ms [範囲] | CPU ms | Fork p50 ms | cleanup p50 ms | 観測ピークRSS MiB | SQL >100ms /240 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 統合前main | 4 | 334.6 [331.8–345.6] | 1812.1 | 21.26 | 2.94 | 338.8 | 0 |
| 辞書待機通知候補 | 4 | 333.1 [332.1–340.8] | 1805.3 | 20.62 | 3.27 | 339.0 | 0 |
| pgmem 1.18.2 | 4 | 290.4 [225.8–316.4] | 1046.1 | 9.12 | 0.15 | 944.0 | 0 |
| 統合前main | 8 | 593.4 [293.6–684.1] | 2032.0 | 29.14 | 4.63 | 574.2 | 5 |
| 辞書待機通知候補 | 8 | 290.0 [285.9–297.1] | 1974.9 | 32.07 | 4.61 | 609.1 | 0 |
| pgmem 1.18.2 | 8 | 251.0 [207.6–268.7] | 1176.3 | 14.82 | 0.45 | 987.0 | 0 |

## 解釈と限界

- 候補対mainのP4ペア差中央値は+0.004%、候補が速いのは2/5回。P8ペア差中央値は−50.17%、5/5回で候補が速い。P8のCPU中央値は約2.8%減に留まり、典型的Fork時間は改善していない。wall差を一般的な処理能力の倍増と読まない。
- P8のmainにはSQL区間>100msが5/240、候補とpgmemには0/240。ここでSQL区間はCOUNT/SUM・UPDATE・再SELECTをまとめたもの。PREPARE単体でもUPDATE単体でもなく、#140/#143のowner・通知・再開の因果関係は測っていない。#143は保留継続。
- pgmemは両Pの全5ラウンドで候補より総時間が短い。ただしP4ではFork>100msが4件ある。全観測を残し、pgmemについてもtailの不在は主張しない。
- RSSは20ms周期のプロセス観測ピーク。瞬間的ピークの厳密な上限でも、保持した子DB単体のメモリでもない。mariamemの低いRSSと高いCPUはこのワークロードでの交換条件として扱う。
- バッテリー95%・放電中。開始時にSpotlight mds_storesとVirtualization VMが各約33% CPUを使用。専用の静穏ホストではない。並べる順をラウンドで回し、P4/P8の順も交互にしたが、OS負荷・温度・電源の影響を除去した試験ではない。n=5プロセス/cellで統計的有意差や他機種への一般化は主張しない。
- エンジン、wire protocol、driverは異なる。mysql 1.9.3とpgx 5.11.0の既定のstatement動作を含む製品比較であり、SQL内部の速度だけを分離した比較ではない。前回のPython fixed30とはワークロード・cap・SDK・Go版が異なり、数値を同列に混ぜない。

## 計測境界と正しさ

1,000行の整数テーブルを準備してSnapshotを取り、rootを閉じてから測定する。各子はFork→接続→SELECT 1→初期COUNT/SUM検証→1行UPDATE→更新値検証→接続とDBの後片付けを行う。後続子の初期値は常に元の状態であることを検証する。batch時間には全子の後片付けを含み、root準備・Snapshot取得・最終Snapshot Closeは含まない。mariamemではWaitDisconnectedも含む。pgmemには同じAPI段階がない。

SQLには両者ともin-process Pipe経路を使う。通常のmariamem Start/ForkによるTCP listener作成は残る。root StartとSnapshotの時間はCSV/JSONに別記し、外部process wallには観測のhandshake/pollも混ざるため純粋なアプリ全体時間とは呼ばない。

本計測30プロセス・1,440子、warmup6プロセス、positive pilot3プロセスは全てSQL/独立性/cleanupを通過。誤ったseedのnegative pilot3プロセスは意図したoracleで失敗し、cleanup成功。子の開始終了区間から同時実行上限も検証。RSS取得はlibprocとpsを照合。読み取り専用の再集計と4つの破損証拠拒否対照もPASS。

## ソースと再現

- 候補 source_commit `0f5b26f370875d26bd337031f48856d8f57c10db`。準備時にPR161はOPEN。後からmainが動いても、この計測のsourceは変更しない。
- 統合前main source_commit `8df45792a927e440972266ee799d6f7223713e14`。
- pgmem v1.18.2 source_commit `a61005d37d01e6671f814fe8ca828222e8147df4`、tag_object_sha `145e5d2fc70983b89a4bdd8438e547fcd60244ed`。取得時の公開latest releaseとannotated tag/peeled commitを検証。
- 共通harness source_commit `e0cbbb08829612d5567221a1e31c9c8386577dfe`。Goソースは無改変。ライブラリsourceはmodfileで別々に固定し、置換先とバイナリbuildinfo/hashを記録。バイナリのvcs.revisionはharnessのもの。
- source/guestは既存の正式生成物。今回の計測は新しいguest generation、Qualification、releaseを行わない。

集計の再検証はこのディレクトリで `python3 analyze.py --check`。SHA256SUMS.jsonが公開コピーを固定する。rawの数値は変えず、公開コピーの個人パスだけ正規化し、原本と公開版のhashをnormalization.jsonに保持した。

再計測は保存した計画を新しいworkspaceへコピーし、予算12GiB・空き12GiB以上でprepareする。evidenceへplan.jsonと各Python scriptを置く。既存repositoryの保存済みharness/candidate/main commitsを使い、tempからcampaign.pyを実行する。build.pyは正確なGo 1.27.4を要求する。build-handoff後に全ビルド監視の終了を確認し、manual_measure.pyを実行する。フルディスク走査は各プロセス前後に限り、timed batch中は20ms RSS観測のみ。各プロセス120秒、測定全体900秒で停止する。新しい実行は新しい観測として保存し、本結果を上書きしない。

ランタイム変更、追加実験、Issue143再開、CIやreleaseの開始はない。後片付けの実測receiptはcleanup.jsonを参照。
