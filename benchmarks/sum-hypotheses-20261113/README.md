# SUM仮説A/B — 監査復帰・両側加算更新とMariaカバリング索引

結論: Aではmariamemの投入が5/5組で短くなり、両製品のsample差も5/5組で縮んだ。ただし差の縮小はペア中央値6.391ms、加算方式でも独立中央値差30.927msが残る。SUMは費用差の一部だが、再集計が差の主因という仮説を強く支持する結果ではない。Bは今回の小規模投入では改善せず、追加索引の採用を推奨しない。

推奨: Aは有用な切り分け結果として保存し、一般的なtrigger書換えの採用とは分ける。次に調べるなら、Aでも残った注文行UPDATE等の費用を両側で分ける価値がある。今回その追加実験は行っていない。エンジン単体の差とはまだ判定しない。

## 条件

監査なし実験からの継ぎ足しではなく、監査ありの比較用harness `be114ac4e07b3195d6b5ed0243adb341e220c8b8`から再構成。監査INSERT/status UPDATE trigger、audit_logと索引を全条件で維持し、元の70テスト・期待値を無変更で実行した。[テストsource照合](test-source-check.json)にhashを保存。

共有DBは両側ともSnapshot後に1 Fork。MariaはUPDATE OF status、監査列ENUM、IF本体、lower(name)生成列索引。PGはstatement_timestamp()、MariaはCURRENT_TIMESTAMP(6)の従来比較用設定を維持。通常Maria16MiB/interpolateParams=true/canonical writeVec、IPC observer/SQL profilingなし。

### A: INSERT時のSUMを加算更新へ

```sql
-- Maria INSERT triggerのUPDATE
UPDATE orders
SET total_cents = total_cents + NEW.quantity * NEW.unit_price_cents,
    updated_at = CURRENT_TIMESTAMP(6)
WHERE id = NEW.order_id;
```

PGも同じ加算式とWHEREに変更し、日時は比較用条件のstatement_timestamp()を維持。元の合計関数が3イベント共用なので、TG_OP='INSERT'の場合に加算UPDATEしてRETURNする分岐を追加した。UPDATE/DELETE時のSUMは両側とも残す。従ってPG側の差には分岐の費用も含み、純粋なSUM内部だけの時計ではない。

### B: Maria SUMを残し、索引を追加

```sql
CREATE INDEX idx_order_items_covering
ON order_items(order_id, quantity, unit_price_cents);
```

Aと組み合わせず、SUM基準に追加。既存のPRIMARY/order_items_order_id/order_items_product_idは残し、FORCE INDEXは使わない。索引作成はSnapshot前、明細が空のmigration時。投入での追加索引更新費用を含むnet比較である。

## 結果

M1/16GiB/macOS27.2.1、Go1.27.4、CGO0、GOMAXPROCS8/GOGC100、test.parallel8。各条件1 warmup後、5条件を循環させた固定5組。各製品は同一binary内のSUM_EXPERIMENT切替。sampleは各プロセス内21ロードの中央値をさらに5プロセスで中央値化した。

| 5プロセス中央値 | PG SUM | PG A加算 | Maria SUM | Maria A加算 | Maria B索引追加 |
|---|---:|---:|---:|---:|---:|
| サンプル投入 ms | 33.543 | 33.320 | 71.195 | 64.247 | 73.869 |
| 全thread合計CPU ms | 1369.774 | 1342.370 | 2300.741 | 2122.989 | 2329.462 |
| process wall ms | 403.449 | 388.698 | 437.662 | 428.722 | 452.657 |
| sampleプロセス中央値の範囲 ms | 32.439–38.084 | 30.583–41.477 | 67.489–75.184 | 60.040–70.610 | 69.497–90.255 |

### Aの判断

独立中央値でsample差は37.652→30.927ms、倍率は約2.12→1.93。大幅な解消ではない。Mariaのsampleは5/5組、CPUも5/5組で短縮。PG sampleは2/5組で短縮し、ペア中央値は+0.041msとほぼ横ばい。PG CPUは4/5組で短縮。

| round | PG加算−SUM sample ms | Maria加算−SUM sample ms | 両製品のsample差の縮小 ms |
|---|---:|---:|---:|
| 0 | +2.211 | −7.726 | +9.937 |
| 1 | −4.764 | −11.155 | +6.391 |
| 2 | +8.510 | −3.242 | +11.752 |
| 3 | +0.041 | −4.574 | +4.615 |
| 4 | −5.127 | −6.542 | +1.415 |
| ペア中央値 | +0.041 | −6.542 | +6.391 |

右列は各roundで `(Maria SUM−PG SUM)−(Maria加算−PG加算)`。異なる指標の中央値同士を引いて作った値ではない。CPU差の縮小も5/5組で同方向、ペア中央値117.741ms。一方wallの差の縮小は一貫せず、同じ因果主張をしない。

Aは「SUMを省くとMariaで費用が減る」を支持するが、「両製品の大きな差の主因はSUM」は支持しきれない。残差には注文/明細/在庫更新、制約・索引、trigger周辺、driver/wire/guest実行系等が含まれる。

### Bの判断

Mariaのsample独立中央値は71.195→73.869ms。追加索引のsample差は5組中4組で増加し、ペア中央値+2.540ms。wallも4/5組で長く、ペア中央値+12.849ms。CPUは3/5組で増え、ペア中央値+36.094ms。今回の固定コーパスでは採用する根拠がない。

| round | B−SUM sample ms | wall ms | CPU ms |
|---|---:|---:|---:|
| 0 | +2.540 | +12.849 | −20.976 |
| 1 | +19.060 | +62.648 | +183.823 |
| 2 | +6.886 | +17.599 | −45.282 |
| 3 | −5.687 | +11.900 | +36.094 |
| 4 | +2.427 | −2.010 | +72.246 |

独立のwitnessで、同形SUMクエリのEXPLAINは基準がorder_items_order_id、Bはidx_order_items_coveringを選び、BのExtraはUsing indexだった。trigger内部の実行計画を直接観測したものではない。追加索引は存在し、optimizerが同形クエリで選択できる状態だったが、投入全体のnet改善はなかった。読み取り短縮と索引更新費用は今回別々に計っていないため、「索引更新が何msかかった」とは断定しない。

1注文1〜4明細という今回の小さいデータでの結果であり、大量明細の注文や読取中心の用途でカバリング索引が不要との一般化はしない。

## 正しさと範囲

別のwitness binaryで5条件全て成功。

- 実際のtrigger/function定義を読み、SUM/加算の設定を確認。
- 全条件でサンプル40注文/100明細/40監査行、注文合計の不一致ゼロ、500商品の在庫一致。
- 新注文に1/2/3個×100の明細を逐次追加し、途中合計100/300/600を確認。
- 明細数量UPDATEで合計900、明細DELETEで700を確認。AでもUPDATE/DELETE側のSUMが維持される。
- 監査ログは新注文で41行、status単独変更で42行に増える。監査を戻していることを確認。
- Bの追加索引が3列で存在し、既存2本の明細索引が残ることを確認。

途中合計を確認する追加SQLはwitnessだけ。性能用には検証SQL、補修、trigger復元を入れていない。LoadSampleの40注文INSERT/100明細INSERT/100在庫UPDATE、1 transaction/3 prepared statements再利用は全条件同じ。

全30計測プロセスが成功、元の70 leafテストは計2100件（primary1750/warmup350）。failure/retry/事後除外なし。PG SUM round0のwall1007.242msは他4回381.572–415.829msより長かったが残した。原因を追加調査しておらず、特にwallではこの外れ値と共有hostの負荷・温度の未統制に注意する。結果を見て反復を追加していない。[summary](summary.json)に全process・各round差・差の縮小を保存。

Aの加算は正しい既存totalを前提とする。元のSUMのように手動で壊れたtotalを再構築する性質はなく、数値境界等の一般的な意味の差も残る。今回のPASSはこのコーパスの整合性であり、一般的なアプリSQL置換の採用ではない。既存MDEV-42129の追加調査・起票・修正はしていない。

## 出自・再現

build前にscripts/git_identity.pyで確認。

- Maria source_commit `0f5b26f370875d26bd337031f48856d8f57c10db`
- guest SHA256 `5f8b711f8efe31529c12847a093e92b8f962598e035cb1d5e253e41093feee20`、再生成なし
- PG source_commit `a61005d37d01e6671f814fe8ca828222e8147df4`
- PG v1.18.2 tag_object_sha `145e5d2fc70983b89a4bdd8438e547fcd60244ed`
- baseline harness `be114ac4e07b3195d6b5ed0243adb341e220c8b8` / benchmarks/modelcase-matched-20261113

PGは保持済みGit objectからgit archiveで復元。donorのpg-seed.go.txt/pg-fixture.go.txtとMaria harnessを使い、setup.pyでA/Bを追加。完成harness、PG変更ファイル、original/patch、archive/binary hashes、inputs/identityを保存。

新workspaceに製品pinのworktree、PG pinのtemp/pgmem、この記録をevidence、harnessをtemp/mariaへ配置。PGのstore/seed.goとfixture_test.goへ保存したpg-seed.go.txt/pg-fixture.go.txtを配置。setup.py（originalから再生成）、build.py、witness.py、measure.py、analyze.pyの順。MODELCASE_MATCHED=1/MARIA_AUDIT_OF=1で監査ありの比較用条件を固定し、SUM_EXPERIMENTだけsum/incremental/coverへ切替。PG cover条件はない。

容量10GiB/空き12GiB、build1800秒、各測定130秒timeout。buildはworkspace runner、witness/measureは直接監視し、計測前後にdisk guard。全計測を同じsandbox外権限で実行した。解析のみならこのディレクトリで`python3 analyze.py`。製品runtime・main・CI・releaseは変更していない。
