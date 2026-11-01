# Issue68：長い待ちは最初のCOUNT/SUMで再現した

**最初の `SELECT COUNT(*),SUM(v) FROM fork_probe` に408.10ms / 382.37msの遅れが出た。**
その後のUPDATEと検証SELECTは各0.4〜0.5msで終了した。
正常系のSQL区間を3つに分ける最初のcheckpointは完了。ただし根本原因や修正は未確定で、
[Issue68](https://github.com/masahitojp/mariamem/issues/68)はopenのまま。

推奨する次の小確認は、この最初のテーブル読取りで遅延を検出した時だけGo stackを採取し、
client側をQueryContext→最初の行→結果読切りに分けること。
スレッドのwait状態と要求／応答の境界が分かれば、guest内の読取り・host通信・OSによる
非実行時間のどれを次に追うか判断できる。遅延検出時の観測は性能比較に使わず、修正前後の
主張は別の観測なし実行で確認する。ここではその追加計測や修正は実施していない。

## 固定条件と範囲

前の[4/8並列比較](https://github.com/masahitojp/mariamem/blob/5096a0c4931e2d30b56e1d1160b3e334f35df396/benchmarks/parallel-pressure.md)
と同じmariamem v0.6.0、M1/16GiB/macOS27.2、Go1.27.3、CGO0、GOMAXPROCS8。
source_commit `b3b3b46a8807482ad3f96725af86e031fe369b01`、
tag_object_sha `b57183b08d48884840111e8b53daa500734337f0`。

- 同じ1,000整数行を準備し、rootを閉じたsnapshotから48子を作成・検証・破棄。
- TCP、P4/P8各3 fresh processes、別warmup各1。round0/2はP4→P8、round1は逆順。
- 前のfixtureから製品・seed・SQL・oracleを変えず、3クエリのhost側wall clockだけ追加。
  約20ms周期の外部RSS観測も維持。pgmemの再測定はしない。
- SQL時間はクライアントAPI呼出し全体を含む。COUNT/SUMと検証SELECTはScan完了まで。
  guest内のSQL実行時間や特定mutexの待ち時間と同一視しない。
- 通常のdesktop。測定前にVMやOSのStorage関連処理が動いていた。停止していない。
  機械全体の隔離・CPU周波数・memory bandwidthの観測はしていない。
- 事前に8子の正常oracle/cleanupと1子の破損seed検出/cleanupを確認。
  前の一斉キャンセル失敗は再試験せず、正常系の結果で解決済みとは扱わない。

## 全6回（外れ値削除・追加反復なし）

ms。COUNT/SUM、UPDATE、検証SELECTは各processの48子中の最大値。
各列の最大値は同じ子とは限らず、横に加算してはいけない。

| round | 並列 | batch wall | batch合計CPU | COUNT/SUM最大 | UPDATE最大 | 検証SELECT最大 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 4 | 759.32 | 3218.27 | 15.40 | 3.78 | 2.01 |
| 0 | 8 | 636.88 | 3543.49 | 29.16 | 14.97 | 4.21 |
| 1 | 4 | 783.80 | 3201.51 | 10.26 | 2.47 | 1.23 |
| 1 | 8 | 688.52 | 3681.39 | 23.40 | 9.12 | 9.30 |
| 2 | 4 | 754.16 | 3201.11 | 7.73 | 2.77 | 1.06 |
| 2 | 8 | 871.39 | 3626.30 | **408.10** | 11.95 | 6.87 |

遅れた2子（round2/P8、child indexは0始まり）：

| child | child開始offset | COUNT/SUM | UPDATE | 検証SELECT | child全体 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 28 | 324.57 | 408.10 | 0.530 | 0.385 | 490.60 |
| 33 | 413.53 | 382.37 | 0.500 | 0.367 | 457.85 |

child33の終了はbatch開始後871.39msで、全体の終了時刻と一致する。
通常時のCOUNT/SUMは各processの子中央値を3process間で中央値にするとP4 3.31ms、P8 4.43ms。
UPDATEは0.42/0.79ms、検証SELECTは0.32/0.64ms。

今回、100ms超を観測したのは全6processのうち1process、288子のうち2子だった。
この小標本で発生確率や「400msのタイマーが原因」とは主張しない。
最初のテーブルアクセスなので、table open、初回scan、engine背景処理、通信・スケジューリング等は
まだ候補。COUNT/SUMが集計だから遅い、UPDATEは常に問題ない、と一般化もしない。

## 保存・検証・再現

measured harness source_commit: `646a8f352777a65b1e0ae04bd172935f6a7fc204`。
[inputs/compact](forkcompare/results/compact.json)にclean product/harnessのsource identity、
binary hash/Go build info、各processの集計、遅延した子の全spanを保存。
[summary JSON](forkcompare/results/summary.json) / [CSV](forkcompare/results/summary.csv)。

測定288子、warmup96子、pilot正常8子はoracle・分離・admission上限・cleanupがPASS。
破損seed負例1子は期待したoracle失敗と正常cleanup。各processのowned scratchは空。
クエリ別時間の合計とSQL区間・子全体の整合も検査した。

raw archiveには全時系列・RSS samplesと、別件#63の6ソースファイル/照合receiptを収録。
[raw reference](forkcompare/results/raw-reference.json)はref `evidence/sql-tail-20261102`、
commit [`67326e124005a8f3b759f459568f3010306c98c5`](https://github.com/masahitojp/mariamem/blob/67326e124005a8f3b759f459568f3010306c98c5/raw.tar.gz)、
109,832 bytes、SHA256 `40971e8a1850de76d349e4e67980629d6a08f0385e39bc65e8a7c4d4e2573dc5`。
workspace prefixだけを正規化し、各ファイルのoriginal/published checksumを含む。

scratch削除後も次はread-onlyでCSV/JSONをbyte一致再計算し、checksumと失敗run拒否を検査する。

```sh
python3 benchmarks/forkcompare/analyze.py --results benchmarks/forkcompare/results --check
```

実測再現はmeasured harnessの使い捨てworkspace（8GiB budget、16GiB free reserve）で、
`temp/product` に固定releaseのclean checkoutを置き、以下を実行する。

```sh
cp benchmarks/forkcompare/run.py ../evidence/run.py
python3 ../evidence/run.py --phase build
python3 ../evidence/run.py --phase pilot
python3 ../evidence/run.py --phase measure
```

還元はreport refのanalyze.pyに `--evidence <new-evidence> --results <new-results>` を渡す。
再現しなくても無制限に再実行しない。過去receiptの貼替え、製品/guest/API変更、main採用、releaseはない。
