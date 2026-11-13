# 全ユーザーtriggerなしの明細INSERT — 2026-11-13

結論: 全てのユーザー定義trigger（監査と合計更新）を除くと、明細100件INSERTの差は大きく縮んだが、差そのものは残る。並列8ではPG10.758→5.924ms、Maria31.769→13.285ms。独立中央値の差は21.011→7.362ms。逐次でもPG6.923→3.810ms、Maria18.025→7.183msで、残差は3.373ms。

推奨: triggerを通る合計更新処理の経路が差を広げていたことを支持する結果として保存する。triggerなしでも残るINSERTの費用は、driver・通信・SQL実行・制約・索引などを含み、エンジン単体へ帰属しない。次へ進むならtriggerなしINSERTの通信/SQL境界を分けることが候補だが、今回その追加計測は実行していない。

## 測定対象

専用の2つのprobeを両製品で同じ方式で実装。元の70アプリテストやその全体wallの比較ではない。合計更新をなくすとアプリの期待値が変わるため、テストを補修で通すことはせず、合計未更新の状態をそのまま検証する。

1. **raw_insert**: 1DBあたり明細100件のprepared INSERT呼び出しとloopの経過時間。親注文40件の作成、入力配列の生成、BEGIN、PREPARE、stmt.Close、COMMITを除く。1 transaction/1再利用statement/100 Exec。商品在庫UPDATEは行わない。
2. **sample_probe**: 既存store.LoadSampleを無変更で呼ぶ全区間。40注文INSERT/100明細INSERT/100在庫UPDATE、BEGIN/PREPARE/COMMIT・接続等を含む従来の投入処理。別の新しいDBへ投入する。

ユーザー定義triggerは全て除くが、FK/CHECK等の制約・既存索引は残す。PGのFK実装が使う内部constraint triggerは除いていない。ここでの「triggerなし」はSQLで定義した監査・合計triggerなしという意味である。

- PGはorders_auditとorder_items_totalをDROP。
- Mariaはorders_audit_insert/updateとorder_items_total_insert/update/deleteの5個をDROP。
- DROPはmaster準備後・Snapshot前。audit_logテーブル/索引や関数定義は残す。

基準はbe114ac4e07b3195d6b5ed0243adb341e220c8b8の条件を近づけたharnessで、SUM方式・監査あり。両側共有DB用1 Fork、PG statement_timestamp、Maria UPDATE OF status/監査ENUM/IF本体/lower(name)生成列索引を維持。Aの加算更新やBの追加明細索引は使っていない。

## 干渉を避ける手順

各workloadごと8個の新しいDBを用意。全Forkを終え、rawでは全DBの親注文作成とBEGIN/PREPAREまで終えてから計測を開始する。parallel=1または8のsemaphoreで操作数を制限する。どちらも8DBを保持するので、P1は「DB1個だけの最小メモリ環境」ではない。

rawの全8バッチが完了するまで、どのDBもCOMMIT/検証/Closeへ進まない。sampleも全LoadSampleが終わるまで検証/Closeしない。外側のFork/準備/commit/oracle/Close呼び出しをtimed raw INSERTへ重ねない。Close内部の非同期資源回収の完了まで両製品で揃えた保証ではない。

同じprocessでrawを先、sampleを後に実行。Snapshot後の共有DBは作るが使わず、各probeは独立した子DBを使う。各workloadの検証とCloseを完了して次へ進む。修復SQL、監査行補填、trigger復元なし。

## 結果

各P/armで1 warmupの後、4条件の順序とP1/P8の順序を変えた固定5組。Go1.27.4、M1/16GiB/macOS27.2.1、CGO0、GOMAXPROCS8/GOGC100。PはSQL操作の並列度で、GOMAXPROCSはP1でも8を維持。通常Maria16MiB/interpolateParams=true/canonical writeVec、IPC observer/SQL profilingなし。同一製品の同一binaryでTRIGGERS_OFF=0/1切替。

各processの8DBの中央値を、さらに5processで中央値化。単位ms/DB。

| 並列度 | 条件 | PG raw100 INSERT | Maria raw100 INSERT | PG sample全体 | Maria sample全体 |
|---|---|---:|---:|---:|---:|
| 1 | triggerあり | 6.923 | 18.025 | 19.165 | 34.389 |
| 1 | triggerなし | 3.810 | 7.183 | 14.840 | 21.810 |
| 8 | triggerあり | 10.758 | 31.769 | 33.631 | 61.668 |
| 8 | triggerなし | 5.924 | 13.285 | 25.830 | 39.708 |

triggerなしrawのMaria/PG比はP1約1.89倍、P8約2.24倍。100件を100で割るとP1はPG約38.1µs/件、Maria71.8µs/件。これはclient往復・driver・loop込みの平均であり、SQL内部CPU時間ではない。

P8 rawでは、独立中央値差が21.011→7.362msへ縮んだ。同じroundごとに `(Maria on−PG on)−(Maria off−PG off)` を計算しても5/5組で縮み、中央値13.772ms（各組12.013/14.232/13.772/13.847/12.841ms）。P1 rawも5/5組で差が縮み、縮小量の中央値7.691ms。両製品ともtriggerを外すとraw/sampleが全てのP・5組で短くなった。

P8 sample全体も、独立中央値差28.037→13.878msへ縮んだ。triggerなしの倍率は約1.54倍。P1 sampleの残差は6.969ms、約1.47倍。同じ組の差や範囲は[summary](summary.json)、差の縮小は[gap-reduction](gap-reduction.json)。独立中央値を足し引きしてsampleの費用をrawへ正確に分解しない。

主なraw中央値のprocess間範囲:

| 条件 | PG ms | Maria ms |
|---|---:|---:|
| P1 off | 3.779–3.907 | 7.006–7.776 |
| P8 off | 5.560–6.989 | 12.670–13.975 |
| P8 on | 10.651–11.278 | 30.069–32.535 |

process全体のCPU/wallも資源確認用に保存したが、そこには親準備・Fork・2workload・oracles・失敗するFK/CHECK試験等も含む。raw INSERT単体のCPUや元70テストの全体wallとして扱わない。前回の71ms等を今回の専用probeと直接差し引かず、元suiteが何ms速くなるとの推定もしない。

## 解釈

rawの親注文と監査行は計測前に作成する。明細INSERT時に監査UPDATE triggerはUPDATE OF statusのため通常発火せず、rawで大きく省かれる経路は合計triggerのSUM＋注文行UPDATEとtrigger処理である。親準備で作られた監査行やmetadata/cache状態の差も存在するので、rawの差を純粋なtrigger内部だけの時計としない。

前回AはSUMを加算へ変えても注文行UPDATEを残した。今回はその合計更新経路ごと外した。両者は異なるcohort・計測区間のため、前回の約6.4msを今回の13.8msから引いてUPDATEの費用と確定することはできない。定性的には、trigger経路が費用差を広げる一方、基本INSERTにも残差がある。

外部キー、CHECK、主キー・二次索引、AUTO_INCREMENT/sequence、型・照合順序、prepared wire、driver、組込み実行系、各製品の通常資源設定等は残る。今回の残差だけでMariaDBエンジン本来の性能を断定しない。共有hostの負荷・温度を統制した保証もない。

## 検証

全48process成功。各processはraw8DB＋sample8DBの16子DBを検証し、計768 DB oracles。raw100 INSERTバッチ384個、raw明細38,400件。sampleも384ロード。primaryは各workload320 DB、warmup64 DB。再試行・事後除外・追加performance反復なし。

各子DBで:

- user trigger数: PG on2/off0、Maria on5/off0。
- 注文40件、明細100件。監査はon40/off0。
- onはSUMと注文合計が一致、offは全注文のtotal_centsが意図どおり0。offが業務上の正しい合計を維持するという主張ではない。
- 商品500件の在庫はrawでは初期値100のまま、sampleでは予約数量分を減らした期待値と一致。
- 存在しない注文へのINSERTとquantity=0のINSERTがFK/CHECKで拒否される。
- 子DBのstmt/transaction/db/serverのClose/rollbackエラーを確認。

元の70アプリテストの期待値を変更して通したものではなく、今回は専用2テストを選択した。既存MDEV-42129の追加調査・起票・修正もしていない。

## 出自・再現

build前にgit_identity.pyで確認。

- Maria source_commit `0f5b26f370875d26bd337031f48856d8f57c10db`
- guest SHA256 `5f8b711f8efe31529c12847a093e92b8f962598e035cb1d5e253e41093feee20`、再生成なし
- PG source_commit `a61005d37d01e6671f814fe8ca828222e8147df4`
- PG v1.18.2 tag_object_sha `145e5d2fc70983b89a4bdd8438e547fcd60244ed`
- baseline harness `be114ac4e07b3195d6b5ed0243adb341e220c8b8` / benchmarks/modelcase-matched-20261113

PGは保持済みGit objectのgit archiveから復元。donorのpg-seed.go.txt/pg-fixture.go.txtとMaria harnessへ、setup.pyでSnapshotへのprobe参照とDROP切替・専用probeを追加。完成harness、PG fixture/seed、共通probe template、original/patchを保存。

準備時に置換アンカーが2箇所あることを検出し、Snapshot側だけを選ぶよう修正。最終probe sourceを固定し、両binaryを改めてビルド。build前後のstore Go source hash一致を確認し、build-source-hashes.jsonとbinary-hashes.jsonを保存した。初回cache buildは計測に使っていない。

新workspaceへ製品pinのworktree、PG pinのtemp/pgmemを用意。この記録をevidence、harnessをtemp/mariaへ置く。PGのstore/seed.goとfixture_test.goへ保存したpg-seed.go.txt/pg-fixture.go.txtを配置。setup.py（originalから再生成）、build.py、measure.py、analyze.py、gap_reduction.pyの順に実行。共通probeはsetup.pyが製品別型/importへ置換する。MODELCASE_MATCHED=1/MARIA_AUDIT_OF=1、TRIGGERS_OFF=0/1、PROBE_ENGINE、LOAD_PARALLELをmeasure.pyが設定する。

容量10GiB/空き12GiB、build1800秒、各測定130秒timeout。buildはworkspace runner（最終sourceの再buildは直接監視）、計測は前後disk guardと直接監視で同じsandbox外権限。解析のみならこのディレクトリで`python3 analyze.py`、`python3 gap_reduction.py`。製品runtime・main・CI・releaseは変更していない。
