# Adopted main versus published v0.5.0: Product Verification

**限定Product Verification COMPLETE：274実行が完了。** 2026-10-17、macOS arm64。
公開済みv0.5.0と、最終Qualificationを通過したmain構成の
対比較。起動順序修正・D block backing・Python共有hostを合わせた製品比較であり、
各変更の寄与を単独で識別する実験ではない。
[Human Review](../docs/reviews/main-product-verification.md)が次の判断を扱う。

## Inputs and measurement boundary

| 入力 | source_commit／identity |
| --- | --- |
| 公開済みv0.5.0 | `44100ec676c8c9064f32f3a01bd9a990d487bb61`、tag_object_sha `bfd854da1cecbe71ad761d1578b3f2c710a1c07f`。型付き[pin](../release/baselines/v0.5.0.json)と[取得・照合記録](main-product-evidence/results/baseline-identity.json) |
| 採用構成 | `c97e55fc065f6ee7b560325077726da53e5d95d7`。[両nativeのQualification](../docs/reviews/main-storage-qualification.md)と同一source |
| guest | いずれもMariaDB12.3.3。baseline Wasm `7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c`、candidate Wasm `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09` |
| 元の計測harness | `c618b0ac3a3c3a204099cb3fe152c87a59def1f4`。実workload／observer hashも入力receiptへ記録 |
| 限定追加確認 | `f0fd3b52ee9fa80b9c8438ed7143fbc591729cb7`。同じruntime binaryを使用。最終集計と報告のsourceは本資料のcommit |

Apple M1／16 GiB／macOS27.0.1、Go1.26.8、Python3.14.8。
同じ`CGO_ENABLED=0 -p 1 -trimpath -buildvcs=true`で、cleanな独立Git checkoutからbuild。
Goの実VCS revision／modified=falseとbinary hashを検査してから実行した。
[build receipt](main-product-evidence/results/build-pair.json)はtree、guest、provenance、
Go／compiler flags、helper、実binaryを保持する。
[Python pins](main-product-evidence/results/python-dependencies.txt)も同じ。
Go resources／Python workloadは両sourceで同一bytes。Go mainの差は、この計測で使わない
旧export optionの拒否と空SnapshotOptionsへの置換だけであることを機械照合した。
guest、converter、runtime、SQL／隔離／回収oracleは変更していない。

既存のLight、10 MiB・8表直列、10 MiB・8表4並列は各3対、100 MiB・8表直列は1対。
各suiteは4テスト。FreshはDBごとに準備、Forkは準備とSnapshotを1回行って子を4個使う。
80計測に加え1テストのpilot8件を別保存し、表には混ぜない。
別のPython実利用シナリオは54実行、小規模追加反復は120実行。
100 MiB Goの悪化を受け、同じ2ケースだけ3対ずつ12実行を後から追加した。
追加結果は元の1試行を消さず、別表で扱う。

1 campaignずつ実行し、順序を交替。build時間は除外。disk上限12 GiB、空きreserve20 GiB、
元の準備開始から2時間を上限とした。cell timeoutはmatrix900秒／sharedhost180秒。
Go cell完了時RSS8 GiB超で停止する設定はhard RAM quotaではない。
実際のowned usage最大は2.525 GiB、空き最小71.658 GiBで、追加確認も元のdeadline内に完了。
通常のOS background activityを完全に制御した実験ではなく、少数試行を母集団の保証にしない。
Ubuntu性能とTestcontainers比較は今回未実行。以前の別source／CGO設定の数値と混ぜない。

## Four-test suite time

秒、baseline→candidate。通常はn=3の中央値、100 MiBは元のn=1。
Goは実処理区間のwall（diagnostic probeを除く。並列は重複区間を加算しない）、
Pythonは既存observer込みsuite wall。同じ言語の対を比較し、言語間の速さを順位づけしない。

| case | mode | Go (s) | 変化 | Python (s) | 変化 |
| --- | --- | ---: | ---: | ---: | ---: |
| Light | Fresh | 0.389→0.364 | −6.4% | 0.478→0.473 | −1.1% |
| Light | Fork | 0.702→0.526 | −25.2% | 0.904→0.580 | −35.8% |
| 10 MiB直列 | Fresh | 2.946→2.858 | −3.0% | 3.063→3.064 | 約0% |
| 10 MiB直列 | Fork | 1.710→1.467 | −14.2% | 1.773→1.506 | −15.0% |
| 10 MiB・4並列 | Fresh | 1.816→0.901 | −50.4% | 0.947→0.943 | −0.5% |
| 10 MiB・4並列 | Fork | 1.264→1.032 | −18.4% | 1.283→1.112 | −13.4% |
| 100 MiB直列・n=1 | Fresh | 25.258→32.585 | **+29.0%** | 27.954→27.538 | −1.5% |
| 100 MiB直列・n=1 | Fork | 11.250→12.746 | **+13.3%** | 10.516→9.614 | −8.6% |

Go並列Freshの最大ready区間はbaseline各`1.125, 1.123, 1.150`秒、candidate各
`0.156, 0.135, 0.137`秒。観測された全体短縮は約1秒の起動待ちの差と対応する。
一般のtail発生率を3試行で保証したものではない。

Lightでは改善後もFreshの方がForkより短い。ごく軽い準備ではSnapshotの固定費を
回収できず、migration／seedを使い回すケースでForkが有利、という製品上の違いは残る。

### Adverse 100 MiB Go case and bounded repeat

同じbinary／既存workloadで追加3対だけを実行。単位は秒。

| 100 MiB Go | 最初の1対 | 追加3対の中央値 | 参考・全4試行の中央値 |
| --- | ---: | ---: | ---: |
| Fresh | 25.258→32.585（+29.0%） | 27.783→28.299（+1.9%） | 26.615→28.527（**+7.2%**） |
| Fork | 11.250→12.746（+13.3%） | 11.068→10.022（−9.4%） | 11.159→10.078（−9.7%） |

Freshの全4値は、旧`[25.258,25.448,29.455,27.783]`、
新`[32.585,26.283,28.755,28.299]`。同じ時点の追加対では−2.4〜+3.3%だった。
最初の+29%は同程度で繰り返していないが、**悪化を消したり、単なる計測誤差と断定しない。**
全4試行のCPU中央値も29.769→31.639秒（+6.3%）であり、wallだけの問題とは言えない。
これは製品として認める不利な観測である。

最初のFresh悪化は、データ準備の合計21.743→27.674秒と更新等の2.170→3.341秒が主。
Forkも最初は準備6.366→7.688秒が増え、Snapshot0.758→0.412秒の利益を相殺した。
起動区間の約1秒待ちの再発とは区別できるが、ストレージ実装の費用とOS／実行条件の
ばらつきを原因別には分離していない。広いprofiling／runtime修正は今回実施しない。
追加3対を元のn=1の代わりに載せず、両方と全観測の感度を示す。

## Go memory and reclamation

同じGo observerの中央値、MiB。100 MiBだけは元＋追加の全4試行、他は元のn=3。

| case | 最大process RSS：旧→新 | 累積allocation：旧→新 |
| --- | ---: | ---: |
| Light Fresh | 297.0→128.7 | 604.3→23.3 |
| Light Fork | 552.9→129.4 | 479.9→20.8 |
| 10 MiB直列 Fresh | 473.6→175.5 | 1184.4→353.1 |
| 10 MiB直列 Fork | 663.8→177.2 | 669.5→117.0 |
| 10 MiB・4並列 Fresh | 814.5→505.2 | 1184.8→353.0 |
| 10 MiB・4並列 Fork | 947.3→408.7 | 669.4→116.4 |
| 100 MiB Fresh・全4試行 | 1042.9→562.7 | 5710.9→3199.5 |
| 100 MiB Fork・全4試行 | 1101.0→472.3 | 2046.2→863.2 |

累積allocationは実行中の総確保量で、同時保持量ではない。Go heapにはmmapが含まれず、
process RSSとheapは別の指標。observerと診断もこの資源観測のscopeに含む。
Python matrixのafter-SQL probeはpeakではなく、共有hostの同じprocessを複数回観測するため
子ごとの値を独立hostのメモリとして加算しない。

Goの元40計測＋4 pilot＋追加12計測では、合計240個のDB用memory mappingを作成し、
同数を解放した。各完了時点のactive／reserved／RW mappingとrelease failureはゼロ。
計測後GC時のGo heap最大は502,520 bytes（約0.48 MiB）。この有限suiteでの回収確認であり、
全workloadでのleak不在の証明ではない。SQL／transaction／子の隔離を含む274実行の
既存oracleはすべて通過した。別に記録したsandbox拒否は成功数に含めない。

## Prepare once, reuse multiple independent children

同じ既存Python公開APIのworkflowを両sourceで実行。2表・unique／FK、seed、各子の
commit／rollback、次の子に前の変更がないこと、host／scratch回収をassertする。
小規模は100行×256 bytes、中規模は10,000行×1 KiB、大規模は102,400行×1 KiB。
大規模の100 MiBはpayload量で、DB全体のfile量ではない。上の8表suiteとschemaを混ぜない。

通常計測6対の中央値、ms。子起動は全子の中央値。

| fixture／子数 | 準備→全Close | 全体短縮 | Snapshot | 子起動 |
| --- | ---: | ---: | ---: | ---: |
| 小・2 | 622.16→452.10 | 27.3% | 379.18→195.07 | 53.89→45.42 |
| 中・2 | 3712.93→3418.47 | 7.9% | 465.37→226.17 | 55.10→44.85 |
| 100 MiB・16 | 34069.09→33070.85 | 2.9% | 793.97→412.40 | 56.50→47.35 |

Snapshotは約48〜51%短縮。大規模はseedが支配的なので全体の利益は小さい。
通常計測では18対中16対で候補が短く、中規模・大規模に各1対の全体悪化がある。
Snapshot短縮から全体が毎回短いとは推論しない。

別の資源計測各3対での、生存host群の合計RSSの観測最大（3回中の最大）、MiB：

| fixture | baseline→candidate |
| --- | ---: |
| 小 | 498.94→124.03 |
| 中 | 627.33→163.02 |
| 100 MiB | 1050.16→535.42 |

通常計測と資源計測は別試行。ps取得後25ms待つため、実間隔はps実行時間も含む。
このRSSは厳密なhigh-water mark、Go heap、Python自身やpage cacheを含む総量ではない。
資源試行の全体時間は通常値に混ぜない。100 MiBの資源試行にも候補の全体悪化が2対ある。
観測の有無だけを原因とする比較にはなっていない。

## Previously slow small workflow

元の[1540.44msの資源計測](../docs/reviews/d-heap-shared-host.md#最終候補対mainの限定比較)は
保存したまま。今回の追加反復30対ずつを通常／資源で分ける：

| 条件・各variantの回数 | whole≥1000ms：旧→新 | start≥900ms：旧→新 | whole最大：旧→新 |
| --- | ---: | ---: | ---: |
| 通常・30 | 1/30→0/30 | 1/90→0/90 start | 1681.32→590.87 ms |
| 資源・30 | 0/30→0/30 | 0/90→0/90 start | 746.57→617.24 ms |

元のworkflow計測にも各variant通常6回・資源3回があり、全体1秒超／start900ms超はゼロ。
各workflowには準備1回と子2回のstartがある。唯一遅かった旧版の追加通常試行19は
prepare/start1068.36ms、Snapshot366.72ms、seed71.79msだった。
新構成で旧い遅い候補試行は再現しなかった。**原因の解明・tail不在の証明ではない。**
この有限回数では改善が保たれたという判断材料とし、原因不明だけで再調査を必須化しない。

## Evidence and replay

[元の完了receipt](main-product-evidence/results/completion.json)、
[継続実行receipt](main-product-evidence/results/manual-continuation.json)、
[追加12実行receipt](main-product-evidence/results/large-repeat/receipt.json)、
[全集計](main-product-evidence/results/analysis/summary.json)、
[個別cell](main-product-evidence/results/analysis/cells.json)、
[全区間](main-product-evidence/results/analysis/phases.csv)、
[全workflow通常／資源](main-product-evidence/results/sharedhost/summary.json)、
[小規模30対ずつ](main-product-evidence/results/small-repeat/summary.json)。
生JSON／consoleもresults内へ保存した。
[preservation ledger](main-product-evidence/results/preservation.json)は、公開用path正規化とCSVの
LF改行統一前後のhashを各fileへ記録する。数値・source／binary hashは変えていない。
[最終tooling確認](main-product-evidence/verification.json)は、保存した574 fileのhash、
両runtime sourceのclean状態と4 binaryの不変、集計・構文・文書参照・public sourceを照合した。
変更していないruntimeの全面検証は繰り返さず、既存Qualificationと今回の実利用oracleを使う。

最初のlinked-worktree buildはGo VCS metadataが親mainのSHAを記録し、**計測前に拒否**。
同一sourceをcleanな独立Git cloneへ移し、両binaryの実VCS identityを照合してから再開した。
[元の失敗receipt](main-product-evidence/results/failed-initial-execution.json)と
[拒否したbuild情報](main-product-evidence/results/rejected-worktree-build-pair.json)を残した。
追加確認の最初の起動もsandboxのlocalhost bind拒否でSQL前に停止し、
[失敗記録](main-product-evidence/results/sandbox-rejected-large-repeat/receipt.json)を保存後、
ローカル接続が許可された同じ条件で再実行した。機能失敗を無視して続けたものではない。

再現は[harnessの有限scopeと手順](main-product-evidence/README.md)を使用。
`experiment_workspace.py prepare`で専用branch／予算を作り、固定2sourceは
`git clone --shared --no-checkout`とdetached checkoutでtempに配置する。
同じtoolchain／pinsでvenvを準備し、`run-all.py`を2時間上限のhelper内で実行。
`repeat-large.py`は元のdeadlineを共有する。最後に`analyze.py`／`collect.py`で
全観測とoraclesを照合し、compactな証拠を保存してbuild／cache／cloneを削除する。
