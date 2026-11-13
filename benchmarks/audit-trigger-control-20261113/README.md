# PostgreSQL監査triggerを全UPDATE発火にした対照 — 2026-11-13

結論: 発火条件を揃えるとpgmemのサンプル投入は35.325→37.276msへ増えたが、mariamem79.733msとの差は大きく残る。監査triggerの発火条件だけでは投入差を説明できない。残差をエンジン単体の差とは判定できず、driver・通信・SQL方言と実装の差を含む。

推奨: 公式定義を引き続き基準として保存し、この対照は別条件として併記する。発火条件の差だけを解消策として追わず、既存の明細INSERT内訳と合わせてguest側SQL処理を次の調査対象にする。追加の製品実装やtrigger書換えの採用は行わない。

## 条件

同じpgmemバイナリで起動時環境変数AUDIT_ALL_UPDATESを0/1に切り替える。変更は移植元の監査trigger DDLに対する下記1箇所のみ。log_order_status関数本体、合計SUM trigger、データ、制約、index、prepared statement、70テストは変更しない。

```sql
-- pg-official: 公式
AFTER INSERT OR UPDATE OF status ON orders
-- pg-all: 対照
AFTER INSERT OR UPDATE ON orders
```

mariaは前回と同じ通常製品sourceと移植harness。監査triggerは既存の全UPDATE発火、DSN interpolateParams=true、16MiB、canonical writeVec。空Write省略・IPC観測・SQL profiling・新しいengine patchなし。Maria側には測定overlayを入れていない。

独立の検証バイナリで監査関数入口を数えた。合計だけのUPDATEは公式0回、対照1回。status変更では両方1回、監査行が1件増える。pg_get_triggerdefでも実際の発火条件を確認。[公式witness](witness-0.txt)、[対照witness](witness-1.txt)。このカウンタはperformance binaryに入っていない。

## 結果

M1/16GiB/macOS27.2.1、Go1.27.4、CGO0、GOMAXPROCS8/GOGC100、test.parallel8。同じhostで1 warmup/条件の後、3条件の順序を回転・反転した固定5組。以下は5プロセスの中央値。sampleは各プロセス内21ロードの中央値を、さらに5プロセスで中央値化した値。

| 指標 | pgmem公式 | pgmem全UPDATE発火 | mariamem通常 |
|---|---:|---:|---:|
| サンプル投入 ms | 35.325 | 37.276 | 79.733 |
| サンプルのプロセス別中央値の範囲 ms | 33.699–37.515 | 32.912–39.361 | 73.802–82.097 |
| process wall ms | 396.302 | 418.174 | 479.947 |
| 全thread合計CPU ms | 1355.457 | 1379.985 | 2422.038 |
| 公式recorder elapsed ms | 346.194 | 360.766 | 468.500 |

中央値同士では投入差44.408→42.457ms、倍率約2.26→2.14倍。これは独立中央値の記述で、差の4.4%を因果的に説明したという意味ではない。全体wallの差は83.645→61.773msとなるが、重なるsampleや他段階の和でwall差を説明しない。

同じroundのpg-all − pg-official:

| round | sample ms | wall ms | CPU ms |
|---|---:|---:|---:|
| 0 | +3.947 | +14.013 | +89.120 |
| 1 | +2.729 | +39.533 | +79.611 |
| 2 | −0.239 | −9.634 | +60.558 |
| 3 | +1.899 | +21.872 | +41.009 |
| 4 | −0.787 | +43.445 | −10.269 |
| ペア差の中央値 | +1.899 | +21.872 | +60.558 |

sampleは3/5組、wallとCPUは4/5組で増加した。小さいsample効果には反転があり、正確な追加費用を高精度に確定するデータではない。一方、mariaとの約42msの投入差が残ることは今回の全プロセスの範囲でも明瞭。共有hostで背景負荷や温度を統制した保証はない。

全18測定プロセス、計1260 leafテスト成功。primary1050、warmup210。失敗したprimary、再試行、事後除外なし。Maria warmup wall1570.528msも保存し、事前に定めたwarmupとして扱った。[runs](runs.json)、[summary](summary.json)、全trace/outputを保存。

## 何が揃い、何が残ったか

監査triggerが合計UPDATEでも呼ばれる条件を揃えた。PostgreSQLは関数内IFでstatus変更を判定し、MariaDBはINSERT SELECT WHEREで判定するため、関数本体の実装までは同じではない。またPostgreSQL now()とMariaDB CURRENT_TIMESTAMP(6)、SQL型・算術・索引表現、driver、wire、guest実行系、Snapshot/Forkのモデルも完全同一ではない。

したがって、分かったのは「この発火条件差は大きな投入差の主因ではない」。残りが純粋なengine差なのか、engineを包む実装差なのかは、この対照だけでは分からない。前回のitem100件に対するguest処理約31ms/通信約4msという観測は別cohort・隔離条件であり、今回の79.733msへ足したり引いたりしない。前回の約12.5msのSUM以外のtrigger費用から、今回のpgmem差約1.9msを引くこともできない。

次へ進む場合は、guest側の注文UPDATE・audit判定・SUMを同一engine内の対照でさらに分ける条件を先に決める。エンジン単体比較を主張するにはdriver/transportを除いた境界と、両側に同じ意味のSQL・検証条件を設けた別の測定が必要。その追加調査・実装は今回開始していない。

## 出自・再現・実行制約

[inputs](inputs.json)、[Maria identity](maria-identity.json)、[pgmem identity](pg-identity.json)をbuild前に確認。source_commitとtag objectは別欄で保持。

- maria source_commit `0f5b26f370875d26bd337031f48856d8f57c10db`
- pgmem source_commit `a61005d37d01e6671f814fe8ca828222e8147df4`
- pgmem v1.18.2 tag_object_sha `145e5d2fc70983b89a4bdd8438e547fcd60244ed`
- Maria harnessは`d73acc145acfdd8a0f1303d82cc03e78bfffb0f1`の`benchmarks/empty-write-pgmem-20261113/harness`を変更せず使用。今回もharnessを保存。

新しい使い捨てworkspaceに製品pinのworktreeとtemp/pgmemの固定cloneを用意し、harnessをtemp/maria、この記録をevidenceに置く。setup.pyでpg-overlay.jsonを作り、build.py、witness.py、measure.py、analyze.pyの順に実行。ビルド用private cache、容量10GiB/空き12GiB、各計測130秒timeout。measure.pyは各プロセスの前後でdisk guardを実行。解析だけなら`python3 analyze.py`で保存済みtraceから再計算可能。

workspace runnerは最初、worktreeをcwdとするのに相対script pathを指定したため起動前に失敗した。その後は手動監視で同じ予算内のビルドを直接実行。最初のsandbox内warmupもlocalhost bind拒否でテスト開始前に停止した。両失敗記録を保存し、正式な18プロセスは全て同じsandbox外権限で実行した。計測binaryの同一性は[binary hashes](binary-hashes.json)に保存。製品、main、CI、releaseは変更していない。
