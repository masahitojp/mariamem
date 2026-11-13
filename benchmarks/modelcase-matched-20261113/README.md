# SQLとSnapshot後の共有DBを近づけた比較 — 2026-11-13

結論: pgmemもSnapshot内部で停止・コピー・再起動する。公式modelcaseは、その再起動済み元サーバーを読取共有DBに使う。mariamemはSnapshotで元DBを消費するため、新しいForkを共有DBにする。この外側の使い方は既存APIだけで近づけられた。pgmem側も元サーバーをCloseし、Snapshot.Forkを1回行って共有DBに使う条件を実装した。Snapshot内部の再起動は依然残り、実装内部まで同じにしたわけではない。

同時に限定したSQL条件を寄せた比較では、pgmemのサンプル投入31.759ms、mariamem68.483ms。約2.16倍の差が残る。純粋なengine差とは呼べない。今回のMaria側追加変更は、既にUPDATE OF statusにした前回条件に対して一貫した速度改善を示さなかった。推奨は公式条件とこの比較用条件を別々に保存し、残差を調べる際はdriver/transportとguest側処理を区別すること。今回、製品の内部実装変更や新たな原因調査は行っていない。

## 今回近づけた条件

| 項目 | 変更前 | 比較用条件 |
|---|---|---|
| pgmemの読取共有DB | Snapshotが再起動した元サーバー | 元サーバーClose後に新しいForkを1つ作る |
| PGのアプリ日時 | now(): transaction開始基準 | statement_timestamp(): statement開始基準。Maria側CURRENT_TIMESTAMP(6)の基準へ近づける |
| Maria監査ログのstatus列 | VARCHAR(20) | 同じ4値・同じ並びのENUM |
| Maria監査trigger本体 | INSERT SELECT WHEREで判定 | IFで判定後にINSERT VALUES |
| Maria商品名索引 | 通常name列の索引 | lower(name)のvirtual生成列name_lowerに索引 |
| Maria商品名検索 | WHERE lower(name) LIKE ... | WHERE name_lower LIKE ... |

両Maria条件とも監査UPDATE triggerはAFTER UPDATE OF status。SUM合計triggerは変更なし。日時の置換はPGのアプリmigration全体（defaultとtrigger/view定義内）で行い、migration管理表のメタデータdefaultはそのまま。比較用のPGでもSnapshot内部の再起動を省略していない。再起動した元サーバーのCloseと共有用Forkの費用は全体時間へ含め、traceでもsnapshot_source_close/reader_forkとして記録した。

pgmem公式のライフサイクルとSQLを維持する条件、および前回のMaria UPDATE OFのみの条件も同じ回に残した。切替用コードは各製品で同じバイナリに入っており、環境変数MODELCASE_MATCHEDで選ぶ。MariaはMARIA_AUDIT_OF=1固定。公式条件とは公式SQL/使用手順を維持する意味であり、切替コードすらない元のバイナリを指すわけではない。

## 実行による設定確認

性能用とは別のwitnessバイナリで4条件とも確認した。[witness結果](witness-results.json)、各witness-*.txt/trace.jsonに保存。

- 読取用reader_fork: PG公式0回、PG比較用1回、Maria両条件1回。再起動したPG元サーバーを閉じた後も、Forkから共有サンプルを投入して読める。
- 全条件で40注文・100明細・40監査行、注文合計の不一致ゼロ。
- Maria比較用で監査列がENUM、監査triggerがIF判定であることを実際の定義で確認。
- Maria生成列の値とlower(name)の不一致ゼロ。
- 選択的prefix `product 499%`のEXPLAINでは、PGはproducts_name_lowerのIndex Scan、Maria比較用は同名索引のrangeアクセス。全ての検索prefixで常に同じplanを使うとの保証ではない。
- PG比較用の実際のrefresh_order_total定義にstatement_timestamp()が入ることを確認。

既存のUPDATE OF列順不具合[MDEV-42129](https://jira.mariadb.org/browse/MDEV-42129)は既知制約として維持。Humanの指示に従い追加調査・起票・修正・再検証を行っていない。元の70テストのstatus更新は単独SETで、列順問題の一般的な解消や受け入れは主張しない。

## 計測

M1/16GiB/macOS27.2.1、Go1.27.4、CGO0、GOMAXPROCS8/GOGC100、test.parallel8。各条件1 warmup後、順序を回転・反転した固定5組。IPC observerなし、Maria通常DSN(interpolateParams=true)、16MiB、canonical writeVec。空Write省略など未採用runtime候補なし。全24プロセスの70テストが成功（計1680 leaf tests、primary1400/warmup280）。失敗・再試行・事後除外なし。

| 5プロセス中央値 | PG公式 | PG比較用 | Maria UPDATE OFのみ | Maria比較用 |
|---|---:|---:|---:|---:|
| process wall ms | 408.241 | 389.783 | 450.211 | 436.570 |
| 全thread合計CPU ms | 1344.208 | 1367.929 | 2314.801 | 2353.081 |
| サンプル投入 ms | 35.860 | 31.759 | 69.018 | 68.483 |
| test本体 ms | 0.777 | 0.8075 | 1.8605 | 1.809 |
| 共有DB用Fork ms | なし | 8.541 | 15.840 | 15.922 |

sample/testは各プロセス内の段階中央値を、さらに5プロセスで中央値化した補助値。重なる区間を足してwallを作らない。共有Forkも含む全体のAPI手順の比較であり、Close後の内部資源回収が両製品で同時刻に完了するとの保証ではない。

比較用同士の独立中央値差はwall46.787ms（Mariaが約12.0%長い）、sample36.724ms（約2.16倍）、CPU985.152ms（約1.72倍）。同じroundの差の中央値はwall52.618ms、sample32.331ms、CPU993.120ms。5組すべてでMariaのwall/sample/CPUが大きかった。

Maria比較用 − UPDATE OFのみの各組:

| round | sample ms | wall ms | CPU ms |
|---|---:|---:|---:|
| 0 | +2.913 | −13.641 | +38.280 |
| 1 | +5.732 | +87.829 | +16.877 |
| 2 | +1.914 | −38.274 | +105.491 |
| 3 | −4.870 | −4.396 | +8.990 |
| 4 | −1.053 | +5.605 | −10.536 |
| ペア差中央値 | +1.914 | −4.396 | +16.877 |

従って今回の追加SQL変更を性能改善として採用する根拠は弱い。CPUは4/5組で増え、sampleは2/5組しか短縮していない。独立中央値のsample69.018→68.483msだけを見て高速化成功とはしない。

PG比較用は追加の共有Forkがあってもwallが4/5組で短かった。ただし日時基準等も同時変更しており、共有Forkを追加すれば速くなるとの因果主張はしない。CPUは4/5組で増えた。共有hostの負荷・温度を統制しておらず、小さい差は揺らぎを含む。前回の87.8ms等を今回値から差し引かない。全プロセスと各組差は[summary](summary.json)、[runs](runs.json)と生trace/outputに保存。

## 残る違い・次へ進む条件

textとVARCHAR、照合順序・Unicode比較、ENUMの物理表現、timestamp型の厳密な意味、整数集計の型、移植した集計SQLの形、1関数共有と操作別triggerの違いは残る。生成列索引とPG式索引も同じ物理実装ではない。今回のASCIIモデルデータのテスト成功を、一般のSQL意味一致とはしない。

driver/各wire/内部通信/guest実行系、Snapshot内部処理、各製品のメモリ・資源の通常設定、非同期回収の完了境界も残る。資源を同じ値に強制してはいない。今回の目的は既存APIと低リスクなharness変更で比較条件を近づけること。エンジンだけの差を判定するには、さらに境界と意味を決めた別計測が必要。その追加計測は今回開始していない。

## 出自と再現

build前にgit_identity.pyでsourceを確認。

- Maria source_commit `0f5b26f370875d26bd337031f48856d8f57c10db`
- guest SHA256 `5f8b711f8efe31529c12847a093e92b8f962598e035cb1d5e253e41093feee20`、再生成なし
- PG source_commit `a61005d37d01e6671f814fe8ca828222e8147df4`
- PG v1.18.2 tag_object_sha `145e5d2fc70983b89a4bdd8438e547fcd60244ed`
- Maria harness元: `79c092c60bdfba4861627c37d08a0a04f810892e`の`benchmarks/maria-audit-of-20261113/harness`

inputs.json、identity、archive/binary hashesを保存。PGは保持済みGit objectからgit archiveで復元。setup.pyは保存済み元ファイルから設定切替を生成するので、保存した完成harnessからも再生成できる。変更は*.patchと*.go.txtに保存した。

新workspaceに製品pinのworktreeとPG pinのtemp/pgmemを用意し、この記録をevidence、harnessをtemp/mariaへコピー。setup.py、build.py、witness.py、measure.py、analyze.pyの順。容量10GiB/空き12GiB、build1800秒、各計測130秒timeout。buildはworkspace runner、witness/measureは直接監視し、計測前後にdisk guard。全計測は同じsandbox外権限で実行。解析だけならこのディレクトリで`python3 analyze.py`。

製品runtime、main、CI、releaseは変更していない。実験ブランチの比較用変更である。
