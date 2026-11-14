# pgmem comparison after buffer-pool zeroing adoption — 2026-11-14

**結論:** PR176採用後mainと、従来のshibukawa/pgmem v1.18.2を同じMacで比較した。
アプリsuite全体の中央値はP1で1371.46対826.17ms、P4で682.65対472.99ms、
P8で579.43対486.64ms。P8の差は92.78ms（mariamemが19.1%長い）。
アプリ内のP8 Forkは34.10対29.26msだが、サンプル投入は105.08対50.01ms。
注文取得・売上集計にも差が残る。Fork初期化だけが現在の差ではない。

**推奨:** 今回の採用と再比較は完了とする。追加のゼロ初期化変更をこの結果だけで
進めず、次に改善を選ぶなら、投入・注文取得・売上集計について既存の切り分けと
Issueを参照する。ここでは新しい原因調査、Issue変更、Releaseを開始しない。
単一Mac・各3processの観測であり、P8に遅い個体もある。前回の別cohortとの増減を
今回のbuffer変更だけに帰属させない。

[集計JSON](summary.json) / [比較CSV](summary.csv) / [全子CSV](children.csv) /
[全span CSV](spans.csv) / [固定計画](plan.json) / [ソースと入力](inputs.json) /
[取り込み記録](integration.json)

## 対象と条件

| 対象 | 固定したソース |
|---|---|
| mariamem | main source_commit `bb1e937ae75b5788c8548a52987d9d42f78292d5`、PR176 squash merge |
| mariamem guest | `77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450`、MariaDB12.3.3 |
| pgmem | v1.18.2、source_commit `a61005d37d01e6671f814fe8ca828222e8147df4`、PostgreSQL18.3 |
| pgmem tag object | `145e5d2fc70983b89a4bdd8438e547fcd60244ed`。tag objectとcommitを分離して確認 |
| app harness | mariamem側はCI済み候補0dea912dの保存済みsuite、pgmem側は同tagの公式bench/modelcaseからの対照 |
| lifecycle harness | 保存済み6211dc9eの公開API probe。mariamem側の内部timing recorder接続を除去。エンジンoverlayなし |

macOS arm64、Go1.27.4、CGO0、GOMAXPROCS8/GOGC100。P1/P4/P8、両対象を交互に
各3計測process＋1warmup、各々suite/lifecycleを実行した。計測36、warmup12、
破壊対照2の計50process。Go build/依存取得は全部終えてから実行し、実行中の
再帰的な容量走査は0回。容量16GiB・空き8GiBの検査は実行前後、実行中は軽量な
空き容量検査のみ。同じ共有Macのbackground activityは[事前snapshot](ambient-before.json)
に保持する。無負荷・専有hostの証明ではなく、その値から変動原因も断定しない。

公式modelcaseの10scenario・70test body、20writer Fork＋1reader Fork、21回の
サンプル投入を両対象で一致確認した。masterは20categories/500products/1000users、
サンプルは決定的な40orders。両方ともSnapshot後の元DBを退役させ、reader用も
新しいForkを作る。pgmemの公式定義をそのまま再現した数値ではなく、従来の
条件合わせを維持したadaptationである。

mariamemの`MODELCASE_MATCHED=1` / `MARIA_AUDIT_OF=1`を維持し、監査は
UPDATE OF status、監査statusのenum、lower(name)用indexとIF内INSERTを使用。
pgmemは公式trigger/index定義。mariamemは通常DSNのinterpolateParams=true、
pgmemはpgx5.11.0の通常動作。pgxとtransitive依存は従来比較のlockへ固定した。
異なるSQL構文・照合/型/index実装・optimizer・driverを同一エンジン条件とはしない。

## アプリsuite全体

`trace.elapsed_ms`の3process中央値。起動、初期data、Snapshot、reader Fork、
サンプル、全testとAPI cleanupを含む。個別span時間の合計ではない。

| 並列 | mariamem ms | pgmem ms | 差 ms | mariamem / pgmem |
|---|---:|---:|---:|---:|
| 1 | 1371.46 | 826.17 | +545.29 | 1.660 |
| 4 | 682.65 | 472.99 | +209.65 | 1.443 |
| 8 | 579.43 | 486.64 | +92.78 | 1.191 |

P8の全3processはmariamem579.43/563.01/776.27ms、pgmem486.64/499.72/429.02ms。
遅い個体を除外していない。今回のsuiteでは全並列度の全3ペアでmariamemの方が
長かった。元のbuffer変更のA/B系列を差し替えず、このcross-engine比較から
採用前後の因果効果を計算しない。

## アプリ内の工程

各対象・Pの3processで同じ種類のspanを集めた1回あたりのp50 ms。
boot/import/Snapshot/reader Forkは各3標本、writer Forkは60、sampleは63標本。
同一process内の標本は独立反復ではない。並列spanは重なるため、下表を足して
suite全体や差分の内訳にはできない。

| 工程 | P1 maria / pgmem | P4 maria / pgmem | P8 maria / pgmem |
|---|---:|---:|---:|
| 起動 | 44.44 / 52.86 | 45.96 / 54.08 | 46.65 / 53.89 |
| schema＋master準備 | 32.44 / 70.10 | 32.57 / 72.74 | 31.97 / 73.47 |
| Snapshot | 5.75 / 16.26 | 6.05 / 16.36 | 5.82 / 16.94 |
| reader Fork | 17.12 / 9.59 | 16.73 / 9.56 | 17.25 / 9.50 |
| writer Fork | 15.66 / 9.21 | 25.31 / 19.17 | 34.10 / 29.26 |
| サンプル投入 | 37.49 / 20.73 | 61.27 / 33.00 | 105.08 / 50.01 |

P8のtest bodyを同じscenarioで比較すると、注文取得は4.055/0.345ms、
売上集計は19.454/0.824ms。一方、商品上位取得は1.738/2.325ms、新規注文の
本体は2.134/2.197msであり、全SQLが同じ比率で遅いわけではない。
ここでのサンプル投入は既存triggerありの1回分全体であり、INSERTだけやtriggerだけの
費用ではない。今回CPU profile・実行計画・driver追加比較は行っていない。

## 別fixtureのFork→first SELECT→cleanup

app suiteとは別の共通probe。1000行の整数tableをSnapshotし、各processで48子を
P個のworkerがFork→接続→SELECT1→aggregate/isolation検査→更新検査→cleanupする。
各cell144子のp50。appの40注文や実アプリSQLの値とは混ぜない。

| 並列 | Fork maria / pgmem ms | first SELECT完了まで maria / pgmem ms | cleanup maria / pgmem ms |
|---|---:|---:|---:|
| 1 | 15.86 / 6.02 | 16.43 / 9.44 | 1.985 / 0.108 |
| 4 | 26.44 / 12.73 | 27.85 / 20.56 | 4.039 / 0.198 |
| 8 | 42.39 / 25.73 | 51.44 / 44.10 | 6.649 / 0.618 |

pgmemの公開Close後にもmodule/共有領域の解放が続く既知の差は残る。
今回も内部observerやdrainを追加しておらず、cleanupの値を同じ資源解放完了保証の
比較とは扱わない。process wall/CPUも`records.json`に保存したが、RSS低下や
全background解放までを測った値ではない。

P8 lifecycleのmariamemには約447/444msの子もあり、記録上の長い区間は
SELECT1後の検証・更新SQL群約402/392ms。対応するcleanupは約7.9/3.4msである。
個別SQL・guest内部の原因は分離していない。pgmemにもFork約173msの子がある。
全標本を保持し、これを既存の長いCloseと同因・解消済みとは扱わない。

## 正しさ・保存・再現

suite全process PASS、全864計測子でoracle・分離・cleanup PASS。
両対象のcorrupt-seed対照は期待どおり非ゼロ終了し、失敗を検出できた。
これは有限fixtureの検証であり、全SQL/全故障を保証する新しいQualificationではない。

`analyze.py`が完全matrix、同じscenario/span件数、全子oracleを検査し、
summary/CSVを再生成する。`verify_saved.py`は全保存hashと集計の再現を検査する。
元/公開hashとpath・行末空白の正規化は`publication.json`に記録。
再生時に元のbinary/実行sourceへ新しい実行結果を付け替えない。

新たに実行する場合は、repoのexperiment-workspace helperで容量16GiB・空き8GiBの
作業領域を作り、`temp/product`へ上記mariamem commit、`temp/pgmem`へ上記pgmem tagを
clean checkoutする。`scripts/git_identity.py`でsource commit/tag objectを再確認する。
`harness/{maria-suite,pg-suite,lifecycle}`をtempへcopyし、go.modの`<WORKSPACE>`を
新作業領域の絶対pathへ置換する。`build.py`/`measure.py`/`analyze.py`と固定planを
その作業領域のevidenceへcopyする。Go1.27.4でhelper `run --timeout 1800`から
build.pyを実行し、全build終了後measure.py、analyze.pyを実行する。
再帰容量guardはbuild中と測定前後だけにし、測定中はmeasure.pyの軽量検査を使う。
普通のローカルDB待受を使える環境が必要である。

mariamem sourceは取り込みmainのまま。guest/host/pgmemエンジンへの計測overlayはない。
初回pg suiteビルドのbenchmark-only依存差とsum不足は**測定前**に修正した。
`pre-pin-builds.json`は未計測バイナリ、`binaries.json`が実計測バイナリのidentity。
既知のConnector/Python/OpenSSL4、MDEV-42129、保留#143の調査は再開していない。
