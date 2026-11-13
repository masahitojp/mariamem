# 両製品で監査triggerを外した対照 — 2026-11-13

結論: 監査triggerを両方から外しても、Fork後サンプル投入の差は残った。pgmem36.072ms、mariamem68.589ms、約1.90倍。監査ありは36.893/73.930ms。監査はmariamem側の費用の一部だが、投入差の主因を監査だけで説明する結果ではない。

推奨: 監査なしの対照を切り分け結果として保存し、次に検討するなら残した合計再計算triggerを双方で外す対照が有用。今回それは実行していない。残差をMariaDBエンジン単体の差とは判定しない。製品の監査機能削除やmain採用は行わない。

## 対照

前回の条件を近づけたharness（be114ac4e07b3195d6b5ed0243adb341e220c8b8）をそのまま土台にし、両方の監査INSERT/status UPDATE triggerだけをSnapshot前にDROPした。

- PG: DROP TRIGGER orders_audit ON orders
- Maria: DROP TRIGGER orders_audit_insert / orders_audit_update

合計SUM再計算trigger、audit_logテーブルと索引、PGのlog_order_status関数定義は残す。PGも共有DB用に1 Forkする、日時はstatement開始基準、Maria監査列ENUM・IF本体・商品名生成列索引という直近の設定も維持。公式定義との比較ではなく、前回の比較用条件を揃えた双方の監査あり/なしである。

DROPはschema/master preparation後・Snapshot前で、import計測に含む。従って全体時間にはDROP DDL費用も含まれ、監査実行費用だけの時計ではない。LoadSampleの40注文INSERT・100明細INSERT・100在庫UPDATE、1 transaction・3 prepared statements再利用は変えない。計測中のDDL、補修、監査行の補填、trigger復元はしない。

監査を削除すると監査行が生成されないため、各製品のwrite_test.goの監査行数に関する2箇所の期待値だけを、AUDIT_OFF=1で0へ変更。query自体は実行して0をassertし、テストをskipしていない。注文・明細・合計・在庫・独立性などの他assertionは維持。従って70シナリオ成功であり、「元の監査あり機能の全assertionを無変更で満たした」という主張ではない。

## 実測

各条件1 warmup後、順序を回転・反転した固定5組。M1/16GiB/macOS27.2.1、Go1.27.4、CGO0、GOMAXPROCS8/GOGC100、test.parallel8。通常Maria16MiB/interpolateParams=true/canonical writeVec、observer・SQL profilingなし。各製品で同じbinaryのAUDIT_OFF=0/1切替。

| 5プロセスの中央値 | PG監査あり | PG監査なし | Maria監査あり | Maria監査なし |
|---|---:|---:|---:|---:|
| サンプル投入 ms | 36.893 | 36.072 | 73.930 | 68.589 |
| sampleのプロセス別中央値の範囲 ms | 35.092–40.293 | 34.491–38.313 | 69.539–81.692 | 63.013–81.606 |
| 全thread合計CPU ms | 1407.758 | 1407.014 | 2435.800 | 2343.457 |
| process wall ms | 414.878 | 415.419 | 507.658 | 484.861 |

sampleは各プロセス内21ロードの中央値をさらに5プロセスで中央値化した。各段階や子DBの時間は重なるので、足してwall差を作らない。

同じroundの監査なし−あり:

| round | PG sample ms | Maria sample ms | PG CPU ms | Maria CPU ms |
|---|---:|---:|---:|---:|
| 0 | −4.221 | −18.679 | +55.062 | −151.488 |
| 1 | +0.420 | −5.341 | +37.122 | −144.219 |
| 2 | −0.955 | −1.563 | −46.355 | −119.845 |
| 3 | −1.869 | +8.205 | +5.530 | −85.545 |
| 4 | +1.420 | −1.808 | +29.443 | −58.354 |
| ペア差の中央値 | −0.955 | −1.808 | +29.443 | −119.845 |

Mariaのsampleは4/5組で短縮、CPUは5/5組で減少。CPU差の方向は共通だが、sample差には反転と大きな幅がある。独立中央値の73.930→68.589（−5.341ms）だけを正確な監査費用としない。PGのsampleは3/5組で短縮、CPUは4/5組で増え、今回の小さい比較では明瞭なCPU短縮を確認できない。

監査なし同士のsample独立中央値差は32.517ms、同じroundの差の中央値は33.485ms。全5組でMariaのsampleが長い。CPUも監査なしでMariaが約1.67倍、全5組で大きい。監査削除で差が消えたとは言えない。

wallは大きく揺れており、今回はsample/CPUを中心に判断する。PG監査なしround1は828.676msで、他4回396.241/408.237/415.419/450.741msに比べ長かったが、除外も再試行もしていない。その原因は未調査。Mariaも監査ありround2の586.020msを残した。wallのペア差中央値はPG+0.541ms、Maria−7.525msで、監査削除による全体短縮は一貫しない。過去の約50msの全体差から、今回の異なるcohortのwall差を変化量として論じない。

共有hostで背景負荷・温度を統制した保証はない。固定回数以外の追加performance反復なし。全24プロセス成功、計1680 leafシナリオ（primary1400/warmup280）。生trace/output、全process/各組差は[runs](runs.json)と[summary](summary.json)。

## 整合性確認

性能用と別binaryのwitnessを4条件で実行し、全て成功。

- PG監査trigger: あり1、なし0。Maria: あり2、なし0。
- 全条件で40注文、100明細、注文合計不一致ゼロ、500商品の在庫が期待値どおり。
- サンプル投入後の監査行はあり40/なし0。
- その後statusを単独変更すると、ありは41/なしは0。

監査なしを再現するための補填は一切しない。witness追加SQL/カウンタは性能用binaryへ入れていない。基本シナリオでは元と同じLoadSampleを走らせており、監査削除によるアプリSQL往復数削減はしていない。

直近の条件ではUPDATE OF status指定により合計UPDATE時の監査triggerは既に発火しない。今回sampleから省かれた主な監査処理は40件の注文INSERTに伴う監査行追加と索引更新。これは「明細のSUM合計triggerを外した対照」とは別である。

既存MDEV-42129の追加調査・修正・起票はしていない。今回の監査なしは機能を意図的に除いた診断条件であり、監査ありSQLの一般的な意味一致やバグ解消を主張しない。

## 解釈と残る仕事

監査はMaria側でCPU費用を持つことを支持する結果だが、sampleに残る約1.90倍の差を説明しきれない。残したSUM合計trigger、注文/明細/在庫の更新、制約・索引、driver・wire・guest実行系などをこの対照でさらに分けたわけではない。以前の別cohortのguest/通信内訳から今回値を引かない。次の合計trigger対照を行うなら、外した場合の合計期待値とtest本体の扱いを事前に定める必要がある。今回それは開始していない。

## 出自と再現

build前にgit_identity.pyで確認。

- Maria source_commit `0f5b26f370875d26bd337031f48856d8f57c10db`
- guest SHA256 `5f8b711f8efe31529c12847a093e92b8f962598e035cb1d5e253e41093feee20`、再生成なし
- PG source_commit `a61005d37d01e6671f814fe8ca828222e8147df4`
- PG v1.18.2 tag_object_sha `145e5d2fc70983b89a4bdd8438e547fcd60244ed`
- donor比較 `be114ac4e07b3195d6b5ed0243adb341e220c8b8` / benchmarks/modelcase-matched-20261113

PGは保持済みGit objectからgit archiveで復元し、donorのpg-seed.go.txt/pg-fixture.go.txtを配置。Mariaはdonorのharnessを配置後、setup.pyでDROP切替と監査期待値を追加した。完成harness、PG変更ファイル、元ファイル、patch、archive/binary hashes、inputs/identityを保存。

新workspaceに製品pinのworktreeとPG sourceを配置し、この記録をevidence、harnessをtemp/mariaへコピー。PGのstore/seed.goはpg-seed.go.txt、fixture_test.go/write_test.goはpg-*.txtの完成形か保存したoriginalを使い、setup.py（originalから再生成）、build.py、witness.py、measure.py、analyze.pyの順に実行。全条件でMODELCASE_MATCHED=1/MARIA_AUDIT_OF=1。容量10GiB/空き12GiB、build1800秒、各測定130秒。buildはworkspace runner、witness/measureは直接監視、計測前後にdisk guard。全測定は同じsandbox外権限で実行。

解析再確認はこのディレクトリで`python3 analyze.py`。製品runtime、main、CI、releaseは変更していない。
