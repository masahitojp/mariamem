# 現在mainのProduct計測 — macOS / v0.5.2比較

**146実行を完了。小規模Forkでは利用者の全体時間が短くなった。大規模な準備を含む全体時間とメモリには、一貫した改善を主張しない。**
今回のmainとv0.5.2の製品コード差はmacOSのOS確認結果の再利用のみ。
Go Light Forkは4テスト全体378→300ms（−20.8%）、Pythonは469→394ms（−16.0%）。
一方、Go 10MiB・4並列Freshは+2.7%、準備を含む100MiB再利用全体は−0.2%だった。

推薦はこの限定した製品効果として結果を受理すること。速度の全域改善やメモリ改善とは評価しない。
最も強い留保は、100MiB Python再利用のRSS観測中央値が492→549MiBに増えたこと。
通常試行の既存ru_maxrss記録とは方向が一致せず、原因を候補か実行条件かに切り分けてはいない。
隠して改善判定に混ぜず、後述の別cohortとして残す。追加調査・修正・main統合・公開は今回行っていない。

## 入力と利用シナリオ

Humanの依頼は以前のProduct計測の再実行、環境はmacOSのみ。
旧[製品比較](ubuntu-product-performance.md)のworkload/oracleを再利用し、比較対象を次の2入力に固定した。

| 入力 | source_commit |
| --- | --- |
| 公開済みv0.5.2 | `47f297cc7498625e076abb93322eb616c9560bb8`（typed release pinでtag objectと区別） |
| 依頼時のmain | `2a02e80399dc32eea71c304064b17b8921a0061d` |
| 計測実行器 | `83f72ebe6d866e98f2ab96150fe458d770af6f02` |

macOS27.0.1 arm64、MacBookAir10,1、8CPU、16GiB。Go1.26.8/CGO0、Python3.14.8、以前と同じ固定Python依存。
最小macOS15のQualificationではない。UbuntuはHuman指定により対象外で、PASSとはしない。
同じ端末/時間帯で版の順序を交替し、buildを利用者時間から除いた。
両sourceはclean cloneで、4 binaryのVCS刻印・source_commit・実行前後hashを検証。
guest SHA256 `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09` と
生成provenance SHA256 `7c7ad7b5a14b55d3d63cb9bc2484e7c93e99860f0a1b0731104d01f8ecc94589` は両版同一。
[入力・4 binary・command・環境receipt](current-product-macos-evidence/receipt.json)を正本とする。

- Matrix：Go/Python、Fresh/Fork、Light、10MiB直列/4並列、100MiB Forkのみ。
  各条件4テスト、各版3試行。84 measured＋8 excluded pilots。
- 準備して再利用：Python公開APIでusers/ordersを作り、migration/seed→Snapshot→各子のCRUD/commit/rollback→Close。
  小規模100 users（payload256byte）・中規模1万 users（payload1024byte）は2子、100MiBは102400 usersで16子。
  ordersはusersと同数で、unique/FKも使う。各版通常6試行、別のRSS観測3試行で54実行。
- Freshは各テストで独立DBを準備。Forkは親の準備を一度行い独立した子を使う。
  MatrixのLightは1行・1tableで、上記users/ordersの小規模とは別のworkload。
- シナリオ・SQL・transaction・親子隔離・Close/回収のoracleは維持。
  Go/Python observerは両版byte一致を確認した。pgmem/Testcontainers比較・profiling・100MiB Freshの追加調査は行わない。

## 1. 準備から4テスト終了までの利用者時間

単位ms、各版3 process試行の中央値。並列は4子の壁時計で、各子の時間の和ではない。
Goは既存のheap observer付きで、product wallから既存diagnostic区間を除く。
Python matrixも既存のpost-SQL資源取得を含む。Go/Pythonをobserverなしの速度順位として比較しない。

| 言語 | 条件 | Fresh v0.5.2→main | Fork v0.5.2→main |
| --- | --- | ---: | ---: |
| Go | Light・直列4テスト | 406→338（−16.8%） | 378→300（−20.8%） |
| Python | Light・直列4テスト | 561→559（−0.3%） | 469→394（−16.0%） |
| Go | 10MiB・直列4テスト | 3275→3131（−4.4%） | 1427→1321（−7.4%） |
| Python | 10MiB・直列4テスト | 3290→3303（+0.4%） | 1491→1448（−2.9%） |
| Go | 10MiB・4並列 | 1253→1286（+2.7%） | 989→968（−2.1%） |
| Python | 10MiB・4並列 | 1308→1307（−0.1%） | 1064→1038（−2.5%） |
| Go | 100MiB・直列4テスト | 対象外 | 10856→10759（−0.9%） |
| Python | 100MiB・直列4テスト | 対象外 | 10994→10909（−0.8%） |

[全14条件の小数付き表](current-product-macos-evidence/matrix-table.md)と
[全試行値/min/max/CPU/資源](current-product-macos-evidence/matrix-summary.json)を保存。
3試行から統計的な一般保証はしない。Go並列Freshの範囲はbaseline1247–1342ms/main1268–1288msで重なり、
悪化の再現性や原因を確定したわけではないが、+2.7%を除外・置換せず残した。

### Go Light Forkの区間

| 区間の中央値 ms | v0.5.2 | main |
| --- | ---: | ---: |
| 親Start | 64.63 | 51.58 |
| 親setup | 8.82 | 8.31 |
| Snapshot | 6.70 | 4.05 |
| 4子のFork起動合計 | 235.10 | 164.89 |
| point/count/mutation | 12.85 / 1.33 / 12.84 | 10.65 / 1.36 / 13.35 |
| 4子の切断待ち＋Close合計 | 35.80 | 44.37 |

各行は区間値をprocessごとに合計してから3試行で中央値化したもの。区間中央値の和は全体中央値と一致しない。
Goのchild_closeは `disconnect`（SQL pool Close＋WaitDisconnected）を含む
（`benchmarks/ownedprepared/main.go:256`）。DB.Close単体とは違う。
その値はbaseline37.43/35.80/35.22ms、main44.37/45.22/35.72msで、すべての工程が速くなったわけではない。
差の原因は今回切り分けていない。Snapshotの製品コードは同じで、この数ms差を新しいSnapshot高速化とは扱わない。
親と子の起動区間の短縮が、全体の利益の主要な観測箇所だった。

## 2. 一度準備して複数Forkで再利用するPythonシナリオ

以下は通常試行、各版6 process反復。Snapshotだけでなくmigration/seed、子の接続・CRUD・切断・Closeを含む。

| 規模 | 子数 | 全体中央値 v0.5.2→main | 差 | 子起動合計中央値 ms |
| --- | ---: | ---: | ---: | ---: |
| 小規模 | 2 | 264.30→247.39ms | −6.4% | 99.92→82.19 |
| 中規模 | 2 | 3608.28→3576.30ms | −0.9% | 113.42→85.82 |
| 100MiB | 16 | 37904.85→37842.38ms | −0.2% | 951.88→758.71 |

小規模では起動短縮が全体にも現れた。100MiBでは子起動合計は約193ms短いが、
migration/seedだけで中央値約34.77→35.04秒かかり、全体の差は小さい。
大規模の全体はbaseline37.28–38.46秒/main37.34–39.71秒。mainの39.71秒も残した。
このシナリオは2table/unique/FK付きの準備であり、上表matrixの100MiBとは同じ仕事量ではない。
全量コピー・hash・SQL処理の新たな最適化効果を示すものでもない。

Snapshot中央値は小規模4.08→3.99ms、中規模3.44→4.57ms、100MiB9.14→9.39ms。
Snapshotそのものの安定した改善は確認していない。

## 3. メモリ・allocation：利益と増加側の両方

Go matrixの中央値（MiB、各版3試行）。累積allocationは処理中の確保量であり同時使用量ではない。

| 条件 | 累積allocation v0.5.2→main | process RSS high-water v0.5.2→main |
| --- | ---: | ---: |
| Light Fresh | 23.4→23.1 | 128.8→128.7 |
| Light Fork | 19.1→18.7 | 129.6→129.9 |
| 10MiB直列 Fresh | 354.9→354.6 | 175.9→172.0 |
| 10MiB直列 Fork | 116.8→117.0 | 177.4→177.6 |
| 10MiB並列 Fresh | 353.2→352.2 | 510.1→517.1 |
| 10MiB並列 Fork | 117.1→116.1 | 407.5→407.6 |
| 100MiB Fork | 879.0→878.5 | 480.8→487.7 |

今回のGo実行全体でRSS最大はbaseline512.61MiB/main526.52MiB。
100MiB Freshは測っていないため、以前の100MiB Freshの大きなRSSを再検証したとはしない。
Goのmappingは198作成/198解放、全cellでactive/reserved/rwとrelease failureがゼロ。
これは対象ケースの回収を確認したもので、一般的なリーク不在の証明ではない。

### Python再利用：RSS観測付きの別cohort

25ms間隔のps samplingを行った各版3試行。通常時間の6試行と混ぜない。

| 規模 | 観測付き全体中央値 ms v0.5.2→main | sampled host peak RSS中央値 MiB v0.5.2→main |
| --- | ---: | ---: |
| 小規模 | 305.64→278.13 | 120.80→120.22 |
| 中規模 | 3963.70→3895.09 | 164.64→163.20 |
| 100MiB | 44681.67→42890.74 | **492.34→549.22** |

大規模sampled RSSの全値はbaseline436.03/492.34/538.53MiB、main549.78/543.91/549.22MiB。
観測した3対すべてでmainの方が大きい。通常試行に既存記録される `ru_maxrss` のraw中央値は
561520640→539099136と反対方向で、観測の有無・実行条件を跨いだ一律の増加/改善とは言えない。
raw値はOS依存指標で、上表のps samplingと同一指標として合算しない。
候補の影響か実行条件の影響かは未分離であり、単なるばらつきと決めつけない。
今回の結論は「安定したメモリ改善は確認していない」。このFork再利用の観測を、閉じたFresh調査へ混同しない。

## 4. 検証・再現・保存

| 確認 | 判定 |
| --- | --- |
| 予備8＋measured matrix84＋reuse54の完了 | PASS・146/146、全command exit0 |
| SQL、commit/rollback、独立DB/親子隔離、Start/Close、host reap、scratch cleanup | 既存oracle全実行PASS |
| source commit型、release tag identity、clean clone、4 binaryの刻印/前後hash | PASS |
| observer同一性、guest/provenance一致 | PASS |
| mapping回収 | PASS、198/198 |
| 独立再集計 | PASS、matrix/cell/summary完全一致、reuse寸法/label/cohort/host isolation照合 |
| 計測器negative/unit・Git identity | 17 tests＋12 subtests PASS |
| 公開source境界・diff・保存hash | PASS（保存時に確認） |
| Ubuntu / 最小macOS / 全Qualification / 公開 | 今回は実施しない |

[計測recipe](../../benchmarks/current-product/README.md)、
[全データ索引・原本/保存後hash](current-product-macos-evidence/files.json)、
[独立解析](current-product-macos-evidence/independent-analysis.json)を保存する。
再集計は測定と同じPython3.14.8で `python benchmarks/current-product/analyze.py docs/reviews/current-product-macos-evidence .`。
集計時の浮動小数点sumも版に束縛し、別Pythonで保存結果を上書きしない。
rawの全試行を残し、空のstdoutログ150件はreceiptのcommand成功記録と索引の省略一覧で追跡する。
home pathだけを置換し、数値は変更していない。通常/観測付きの結果は分離して再現する。

buildを含むcampaignは1314秒（約22分）で完了、nested peak約1.48GiB、outer workspace peak約1.78GiB。
2時間/所有12GiB/空き12GiBの上限に達していない。一時source/binary/venv/cacheを削除し、
約1.5MBの測定値・入力・再現recipeを保持する。mainの製品コードは変更していない。
結果のmain統合や新しい公開を、この計測完了から自動承認しない。
