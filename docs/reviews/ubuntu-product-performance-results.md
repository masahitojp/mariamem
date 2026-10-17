# Ubuntu性能確認の結果とHuman Review

## Human Review

**推薦は、Ubuntu性能確認を完了として受理し、v0.5.2のSnapshot改善にはUbuntuでも裏付けが得られたと判断すること。**
v0.5.1→v0.5.2の小規模再利用では、Snapshotが222.72→5.11ms、
準備から子2個の利用・全Closeまでが520.99→304.42msになった。
Go／Pythonの4テストForkも多くの条件で短縮した。機能oracleと全246実行の照合は完了した。

**最も強い反論は、大規模PythonではSnapshotの利益が全体改善になっていないこと。**
100 MiB・4テストForkはv0.5.1比+2.4%、別schemaの100 MiB・16子再利用は+0.5%だった。
この悪化を無かったことにせず、候補の費用か実行条件のばらつきかは未分離とする。
一方でSnapshot自体の短縮はこの大規模でも全6対にあり、改善した区間と相殺した区間は分けられる。
そのため結果を受理する推薦は維持するが、「すべてのworkloadで全体が速い」とは結論しない。
ここでruntime修正や追加の原因調査を自動で開始する推薦ではない。

## Human decision（2026-10-18）

Humanは上記推薦を受け入れ、Ubuntu性能確認を完了として受理した。
Snapshotの改善と、大規模Pythonでは全体の悪化もあり原因未確定であることを併記する。
全workloadの高速化や原因解明を完了扱いにはしない。
この受理は追加調査・main統合・runtime変更・Qualification・公開の承認を含まない。

## 対象と証拠

- [CI run 39073990176](https://github.com/masahitojp/mariamem/actions/runs/39073990176)、
  [job 117517239946](https://github.com/masahitojp/mariamem/actions/runs/39073990176/job/117517239946)。
  計測、後片付け、artifact保存はsuccess。
- harness source_commit：`a3a852fe643ad3d651ef8bee895e015912b4449c`。
  [事前scope](ubuntu-product-performance.md)と[手順](../../benchmarks/ubuntu-product/README.md)を審査対象にした。
- 製品は公開済みv0.5.0=`44100ec676c8c9064f32f3a01bd9a990d487bb61`、
  v0.5.1=`7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`、
  v0.5.2=`47f297cc7498625e076abb93322eb616c9560bb8`。
  annotated tag objectとcommitはtyped pinで別々に検証した。
- native Ubuntu24.04.5 x86_64、Go1.26.8／CGO_ENABLED=0、Python3.14.8。
  GitHub-hosted image=`20261012.334.1`、CPU記録はIntel Xeon 6973P-C・4 logical processors。
  これは1台のrunner・1campaignの観測。記録対象のcgroup v2 limitファイルはなく、値を推測で補わない。
- artifact ID=`12117761969`、ZIP SHA256=
  `95054b6fac6e7cae797bc25dc93326f68de639338d5e2bce4b295815ad3a1249`。
  GitHubのdigestと取得したZIPが一致し、展開515ファイルもZIPとbyte一致した。
- [receipt](../../benchmarks/ubuntu-product-evidence/receipt.json)、
  [全試行と再集計](../../benchmarks/ubuntu-product-evidence/review-summary.json)、
  [保存前後のhash](../../benchmarks/ubuntu-product-evidence/preservation.json)。
  公開用にrunnerのpath prefixだけ正規化し、原本／保存後hashを区別した。

## 事前条件と完了判定

| 条件 | 判定と根拠 |
| --- | --- |
| 各版の固定source／guest／converterを改変しない | PASS。3版のpin、guest hash、provenance、observer hashをGit blobへ照合。今回runtime変更なし |
| 同じobserver | PASS。Goの未使用export option撤去だけを許容し、他のGo／Python workloadは同一bytes。C helperも全版共通 |
| sourceとbinaryの整合 | PASS。CIは6 binaryについてclean source・実VCS stamp・hashを計測前後に検証。保存されたstampにも版・Go・OS・arch・CGO・clean状態が整合 |
| 定義した実行を完了 | PASS。matrix126＋除外pilot12＋再利用108＝246。153の親commandは全てexit0。欠測・余分なcellなし |
| SQL／transaction／隔離／cleanup oracle | PASS。元のassertを保持し、子processの失敗で停止する配線。再利用108の結果も全てPASS |
| native platformと版 | PASS。native x86_64／Ubuntu24.04、Go1.26.8、Python3.14.8をreceiptで照合 |
| resource／予算／後片付け | PASS。Go mappingは測定分各版96作成＝96解放、各cell終了時active/reserved/RW/release failureは0。CIのowned temp除去stepもsuccess |
| 全試行の保存・集計 | PASS。138 matrix JSONを再集計し既存cells/summaryと一致。再利用各54 JSONの中央値・資源値も照合 |

binaryそのものはartifactに含めない設計のため、レビュー側で6実行fileのhashを再計算したわけではない。
その部分は固定SHAのCIコードが行った計測前後検証と保存stamp／hashが証拠。
SQLのPASSはこの有限workloadでの機能確認であり、一般的なWasm／共有メモリ保証やQualificationではない。

## 4テスト全体：中央値

ms、各版n=3、pilotは除外。Goは既存のproduct wall、Pythonは既存observer込みsuite wall。
言語間は違う計測境界なので順位づけしない。

| 言語・条件 | mode | v0.5.0 | v0.5.1 | v0.5.2 | v0.5.1比 |
| --- | --- | ---: | ---: | ---: | ---: |
| Go Light | Fresh | 1,359.86 | 350.38 | 326.78 | −6.7% |
| Go Light | Fork | 743.44 | 580.00 | 365.74 | −36.9% |
| Go 10 MiB直列 | Fresh | 3,956.35 | 2,863.04 | 2,893.17 | +1.1% |
| Go 10 MiB直列 | Fork | 1,762.87 | 1,595.28 | 1,284.08 | −19.5% |
| Go 10 MiB・4並列 | Fresh | 1,791.46 | 1,316.60 | 1,288.90 | −2.1% |
| Go 10 MiB・4並列 | Fork | 1,399.29 | 1,188.85 | 945.24 | −20.5% |
| Go 100 MiB直列 | Fork | 10,298.44 | 9,886.47 | 9,515.04 | −3.8% |
| Python Light | Fresh | 539.28 | 559.04 | 536.91 | −4.0% |
| Python Light | Fork | 1,002.84 | 741.18 | 527.80 | −28.8% |
| Python 10 MiB直列 | Fresh | 5,141.56 | 5,065.53 | 5,045.52 | −0.4% |
| Python 10 MiB直列 | Fork | 2,469.76 | 2,151.36 | 1,914.01 | −11.0% |
| Python 10 MiB・4並列 | Fresh | 2,652.97 | 2,126.37 | 2,171.73 | +2.1% |
| Python 10 MiB・4並列 | Fork | 2,168.58 | 1,931.88 | 1,627.93 | −15.7% |
| Python 100 MiB直列 | Fork | 15,393.21 | 14,645.36 | 15,003.23 | **+2.4%** |

v0.5.0→v0.5.2のGo Light Freshの大きな差は、旧版での約1秒の起動区間も含む。
Goの測定分・混合suiteのstart観測は各版96件、900ms以上はv0.5.0で9件、v0.5.1/v0.5.2で0件。
異なる規模／直列・並列を混ぜた観測数であり、一般のtail発生率や不在を保証する比率にはしない。
v0.5.2のLightではGoはFresh 326.78msの方がFork 365.74msより短く、
PythonはFresh 536.91ms／Fork 527.80msと近い。準備がごく軽い場合にもForkが必ず有利になるとは言わない。

## 準備を再利用するPython workflow

以下は**v0.5.1との対比較だけ**、通常計測各6回の中央値、ms。
4テストmatrixとは別schema。資源観測は別の各3回なので、下表の時間に混ぜない。

| 条件 | 全体：v0.5.1→v0.5.2 | Snapshot | 子Fork起動・1子 | 子Close・1子 |
| --- | ---: | ---: | ---: | ---: |
| 小・2子 | 520.99→304.42（−41.6%） | 222.72→5.11 | 53.72→53.70 | 4.74→4.71 |
| 中・2子 | 5,656.19→5,519.82（−2.4%） | 259.37→4.26 | 54.89→54.95 | 4.52→4.57 |
| 100 MiB・16子 | 55,848.54→56,115.58（**+0.5%**） | 504.51→7.75 | 53.99→58.24 | 4.06→4.11 |

Snapshotは小・中・大の全6対それぞれで短縮。ここでは約98%短縮したが、
大規模の全体は速くなっていない。v0.5.0との別対比較では全体が小−59.1%、中−8.7%、大−2.0%だった。
その比較windowのv0.5.2数値を上のv0.5.1比較と混ぜない。

大規模v0.5.1比較の6対を同じ反復番号で引くと、Snapshot差は各−494〜−535ms。
一方、seed区間差は−56〜+1,582ms、子16個の起動時間合計の差は−22〜+142msだった。
利益が他区間に相殺された場所までは分かるが、なぜその区間が増えたかはこの計測で確定しない。
中央値同士の差や合計を、全体中央値の厳密な分解として扱わない。

Goのmatrix Snapshot中央値もLight 221.88→3.68ms、10 MiB直列260.14→6.90ms、
4並列用基準259.88→6.50ms、100 MiB 475.36→8.50msだった。
macOSでの所有権変更の利益がUbuntuでも現れたという判断材料であり、OS間の絶対時間の比較ではない。

## メモリ・確保量

Goの同じobserver、各n=3の中央値、MiB。RSSはprocess high-water、allocationは累積量で別指標。

| 条件 | RSS：v0.5.0→v0.5.1→v0.5.2 | 累積allocation：同順 |
| --- | ---: | ---: |
| Light Fresh | 299.5→157.0→156.3 | 604.0→23.1→23.3 |
| Light Fork | 464.4→166.4→163.4 | 479.0→20.3→18.7 |
| 10 MiB直列 Fork | 573.7→202.0→200.5 | 666.7→114.0→113.9 |
| 10 MiB・4並列 Fork | 888.2→467.2→467.3 | 663.5→112.9→112.7 |
| 100 MiB Fork | 1,178.4→510.0→515.3 | 2,027.1→843.8→859.6 |

大きな資源削減は主にv0.5.0→v0.5.1で得たもの。v0.5.2がさらに全面的なメモリ削減をもたらしたとは言わない。
GoのGC後heap最大は測定分で約0.35MiB以下、mappingの作成・解放は一致した。
これは今回の回収確認であり、すべてのworkloadでのleak不在や即時RSS低下の保証ではない。
Pythonの資源観測は生存host群の合計RSSの有限samplingで、Python本体・page cacheを含む総メモリや厳密なpeakではない。
詳細はreview-summaryのreuse_detailsへ保存した。Linux PSSとmacOS physical footprintは別物として扱う。

## 残件・検出範囲・次の判断

- 今回のUbuntu性能確認は、合意したscopeに対して完了。改善が安定しない大規模Pythonの観測も保存済み。
  原因未確定を、計測そのものが未完了であることや、悪化が単なるnoiseであることと混同しない。
- 100 MiB Fresh、追加profiling、Testcontainers／pgmemとの比較は未実施でscope外。
  再発待ちで閉じた100 MiB Go Freshを今回の別ケースで再開しない。
- CIの負例・identity／完了数／mapping／既存SQL oracleは入力の取り違えや機能失敗を検出する。
  改善率の採否、少数試行の代表性、大規模悪化の原因は自動gateではなくHuman Reviewの対象。
- 公開API、契約、generated source ownership、license/provenance入力の変更はなし。
  公開ガイドに今回のruntime変更と矛盾する箇所は生じていない。新たな採用・再承認条件は見つからなかった。
- 「Snapshot単体ではなく全体を見る」という既存方針は維持する。今回、小規模全体には明確な利益、
  大規模には利益が相殺される例、子の起動・Closeには残る時間があることまで判断できる。
  主に子起動／SQLが残るという既存の見立てと整合するが、その内部原因を調べた証拠ではない。
- [mainの既存残件](https://github.com/masahitojp/mariamem/blob/be5fddcbf878f248ab721f52f5a1c536068deec9/docs/project-status.md)には別途、子Fork起動／Closeの帰属確認が0.5.x残件として記録されている。
  今回の完了でその別作業を消したり、修正の実装を承認済みにしたりしない。
  このReviewでは結果の受理を求め、main統合・リリース・新しい実験は求めない。

## 再照合

```sh
python3 docs/reviews/ubuntu-product-performance-verify.py.txt
```

保存済みartifactのhash、固定入力、6 binaryのstamp、全246実行、欠測・重複、再集計を検査する。
guest・benchmarkの再実行は行わない。hash照合・文書参照・公開source・diff検査も行い、
レポートと証拠を実験ブランチに保存する。初回workflow定義エラーの記録は事前scopeに残す。
