# 4並列と8並列：CPU費用と待ちを分ける

**今回の同一ホスト・同一仕事では、mariamemの「4並列で頭打ち」は再現しなかった。
4→8で全3組とも速くなった。ただし48件に使うCPU時間はpgmemの約3倍で、
SQL区間には時々0.4〜0.8秒の長い待ちがあった。**
「MariaDBだからこの程度が当然」「メモリ容量が4並列の限界を決めている」と結論づける証拠はない。

勧める次の確認は、この長いSQL区間を3クエリに分け、どの要求／応答で待つかを見る小さな追試。
これは全体時間の振れに直結する観測であり、Fork全体の最適化や通信方式変更を先に実装する理由にはしない。
一方、CPU費用の削減は独立した改善候補として残る。今回の測定だけでは、CPU時間増加を
「余分な命令が増えた」と「同じ処理に時間がかかった」に分解できない。
この実験はここで終了し、追加追試・製品変更・Issue作成・main採用は行っていない。

## 条件

- Apple M1、物理メモリ16GiB、macOS27.2、Go1.27.3、CGO0、GOMAXPROCS8。
  sysctlでperflevel0/1の物理CPU数は各4。通常のdesktopでアプリ・VMが稼働し、専用機ではない。
- mariamem v0.6.0とpgmem v1.18.2。別々のclean checkoutを同じGoでbuild。
  **両方TCP**。pgmemのプロセス内接続や過去の70件アプリスイートは今回の対象外。
- rootに同じ整数1,000行を準備し、snapshotを取得、rootを閉じる。
  48個の独立した子DBを、上限4または8で作成・処理・破棄する。
- 子ごとにFork、接続、SELECT1、COUNT/SUMで初期データ検証、1行UPDATE、更新値SELECT、cleanup。
  先行する子の更新が後続の初期データに漏れないことも確認。
- 各セルfresh processを3回、別warmup1回。round 0/2はmaria4→pg4→maria8→pg8、
  round1は逆順。外れ値は削除していない。子48件は独立した48回の反復試験とは数えない。
- batch wall/CPUはroot準備・snapshot・最終snapshot破棄を除外し、全子の処理・破棄を含む。
  CPUはgetrusageのバッチ前後差、子ごとのCPU加算はしない。
- RSSは親processからDarwin proc_pid_rusageで約20ms周期に観測。
  baselineはsnapshot準備後・子開始前、peakはバッチ中の観測最大。
  子のphase wall spansと開始offsetも保存。RSSの測定ABIはpsと事前照合。

同じアプリSQLだが、エンジン・ドライバ・wire protocolは異なる。
MariaDB12.3.3 / PostgreSQL18.3、mysql v1.9.3 / pgx v5.11.0の宣言経路の比較であり、
エンジン単体やtransport単体のA/Bではない。

## 48件全体：mariamemも8並列で速くなった

各セル3processの中央値。括弧は最小–最大。CPU秒は全threadのCPU時間の合計。

| 製品 | 並列 | バッチwall秒 | 合計CPU秒 | CPU/子ms | 観測peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| mariamem | 4 | 1.115 (0.704–1.531) | 3.227 | 67.2 | 379 |
| mariamem | 8 | 0.600 (0.578–0.917) | 3.776 | 78.7 | 700 |
| pgmem | 4 | 0.269 (0.230–0.295) | 1.066 | 22.2 | 936 |
| pgmem | 8 | 0.266 (0.224–0.333) | 1.230 | 25.6 | 994 |

同roundのP8/P4を対にすると：

| 製品 | wallの変化（3組） | 合計CPUの変化（3組） |
| --- | --- | --- |
| mariamem | −46.2%, −40.1%, −17.9% | +14.5%, +17.0%, +21.9% |
| pgmem | +13.1%, −17.0%, +15.6% | +9.3%, +15.4%, +21.3% |

この仕事では、mariamemは8並列で短縮する一方、CPU時間も増える。
pgmemは元の絶対時間が短いが、4→8のwall短縮は一貫しない。
「pgmemなら8並列まで伸びる」という一般化も、このTCP経路の結果からはできない。
過去のP4/P8アプリ結果と今回の小プローブを混ぜて速度比を作らない。

CPU÷wallはmariamem P4で2.90、P8で6.17、pgmem P4で3.96、P8で4.63が中央値。
これは平均のCPU占有相当数で、CPU使用率の時系列・命令数・メモリ帯域ではない。
待ちの長い回ではこの値が低下する。CPU時間の増加だけで、同期処理の増加・周波数・
CPU配置・キャッシュ競合などのどれが原因かは確定できない。

## 大きな振れはForkの後にあった

各process内48子の中央値を取り、その3個の中央値。全体wallへ加算できない重複区間。

| 製品・並列 | Fork return ms | SELECT1までのreadiness ms | その後の3 SQL ms | cleanup ms |
| --- | ---: | ---: | ---: | ---: |
| mariamem P4 | 42.3 | 44.7 | 4.5 | 8.5 |
| mariamem P8 | 61.2 | 68.1 | 6.7 | 10.3 |
| pgmem P4 | 10.2 | 15.4 | 4.7 | 0.17 |
| pgmem P8 | 15.7 | 27.0 | 8.9 | 0.24 |

mariamemの正常測定6process中4processに、SELECT1後の3 SQL区間で100ms超の子があった。
各processの最大値：

| round | P4 batch / SQL最大 ms | P8 batch / SQL最大 ms |
| --- | ---: | ---: |
| 0 | 1114.8 / 820.3 | 599.6 / 403.6 |
| 1 | 1531.2 / 814.8 | 917.4 / 813.5 |
| 2 | 703.6 / 11.6 | 577.5 / 31.0 |

round0/P4は子17が開始238.9msから875.9ms滞在し、SQLだけで820.3msを使った。
round1/P4は最後の子47のSQL814.8msがbatch終了を延ばした。
一方、P4の合計CPUは3.174–3.227秒と近い。
**wallの大幅な振れを、Fork CPU費用の増加だけで説明するのは不適切。**
SQL区間のwallにはOSによる非実行時間も含むため、DB内部のwaitと確定はしない。
COUNT/SUM・UPDATE・SELECTのどれで止まったかは今回未分離。

長いSQL待ちのなかったround2でも、mariamemはP4 704ms→P8 578msで約18%短縮した。
この1組を「ノイズを除いた真の性能」と選別はしないが、今回の改善がすべてtailの偶然だけ、
とも説明できない。3組は稀なtailの頻度や最適並列数を決めるには足りない。

## メモリ：保持した子の増分とバッチのpeakは別

子開始前RSSはmariamem約50MiB、pgmem約136MiB。
mariamemのバッチpeakはP4約379→P8約700MiB。
pgmemはP4約936→P8約994MiBで、今回のバッチpeakはpgmemの方が高い。

以前の「4子を順番に作って保持」ではRSS増分がmariamem約311MiB、pgmem約103MiBだった。
今回は48回の作成・破棄中のprocess RSSなので、解放後の保持・再利用・GC等の影響を含む。
ピークRSSを1子の常駐費用で割ったり、以前の結果を誤測定と決めたりはしない。
高いRSSの内訳は調べていない。20msで取り逃すピークもあり得る。

したがって今回の結果は、「mariamemだけがメモリ容量を使い切り4並列で頭打ち」を支持しない。
ただしシステム全体のmemory pressure・帯域・cache missは未測定で、その不在を証明もしない。

## 事前確認で出た別問題

最初のharness `0ed4593666fcc729e61ebf0fda7932a15eaa8d27` では、破損seedを8並列で検出し
共有contextをキャンセルした際、mariamemのguest cleanup timeoutが出た。
batch約40秒、`cleanup_complete=false`。processは終了しowned scratchは空になったが、
製品の正常なcleanupが成功したとは扱わない。rawの `pilot/0-mariamem-p8-negative.json` に保存。

正常系のスケーリングと一斉キャンセルの契約は別なので、oracle負例を1子に分離した。
最終pilotは両製品で8並列の正例／1子の負例が期待どおり終了しcleanupも成功。
これは**一斉キャンセル問題の解消ではない**。その修正・再現追試は本実験の対象外。
測定12process、warmup4processはすべて48子完了、SQL oracle、admission上限、cleanupを確認した。

## 入力・保存・再現

measured harness source_commit `d10cfa8fb810b512333bcfa8b9d661493325478e`。
[typed product pins](forkcompare/source-pins.json)、[plan](forkcompare/plan.json)、
[compact observations](forkcompare/results/compact.json)に実際のバイナリhash・Go build infoを保存。
本実験のproduct/guest/generated/API/release変更はゼロ。
全child時系列とRSS samplesはrawへ分離し、report側にはprocess単位の合計・中央値・最大値・checksumを残す。

[summary.json](forkcompare/results/summary.json)、[CSV](forkcompare/results/summary.csv)、
[raw reference](forkcompare/results/raw-reference.json)。
raw ref `evidence/parallel-pressure-20261101`、commit
[`aefe4ec17021c27811a301aa19f7c6b210a12f9b`](https://github.com/masahitojp/mariamem/blob/aefe4ec17021c27811a301aa19f7c6b210a12f9b/raw.tar.gz)、
57,320 bytes、SHA256 `2118f3a0d9f224aff94b910312546f3760bfb713185d9a043e9499e432e21849`。
workspace prefixだけを正規化し、各ファイルのoriginal/published hashをarchive内に保存。
失敗した最初の負例も含み、過去のreceiptは貼り替えていない。

scratch削除後も、次はread-onlyでcompactからCSV/JSONをbyte一致再生成してchecksumを検証する。
失敗runを成功集計に入れないnegative checkも実行する。

```sh
python3 benchmarks/forkcompare/analyze.py --results benchmarks/forkcompare/results --check
```

runtime再現はmeasured harnessの新しいdisposable workspace（budget12GiB/free reserve16GiB）で、
`temp/product` にpin済みmariamem、`temp/pgmem` にpin済みpgmemのclean checkoutを置く。
source identity検査はrunnerがbuild前に実行する。

```sh
cp benchmarks/forkcompare/run.py ../evidence/run.py
python3 ../evidence/run.py --phase build
python3 ../evidence/run.py --phase pilot
python3 ../evidence/run.py --phase measure
```

report refのanalyze.pyに `--evidence <new-evidence> --results <new-results>` を渡して還元する。
再現には同じ環境が必要で、数値の一致は保証しない。取得・buildは時間比較から除外。
この実験の結論にLinux、他SQL、長い実アプリテスト、P8を超える並列を含めない。
