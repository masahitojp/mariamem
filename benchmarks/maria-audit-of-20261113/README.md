# MariaDB監査triggerをUPDATE OF statusに揃えた比較 — 2026-11-13

結論: MariaDB側の監査triggerをpgmem公式に合わせると、サンプル投入の中央値は105.687→87.829msに短縮した。pgmem公式は40.765msで、変更後も約2.15倍の差が残る。発火条件の移植差は費用の一部だったが、それだけでは差を説明できない。

推奨: 今回の限定したモデルケースでは変更後を「発火条件を揃えた比較」として保存し、従来定義も別条件として残す。ただし一般用途への採用は今回判断しない。12.3.3の既知不具合[MDEV-42129](https://jira.mariadb.org/browse/MDEV-42129)があり、列指定の順番によって監査triggerが発火しない。Humanの指示に従い既存issueを読むだけとし、追加調査・起票・修正は行っていない。

## 設定変更

[元のschema](schema/maria-original.sql)から[揃えたschema](schema/maria-matched.sql)への変更は以下の1箇所。INSERT監査trigger、statusが実際に変わったかの判定、SUM合計trigger、その他のSQL・制約・indexはそのまま。

```sql
-- 変更前
CREATE TRIGGER orders_audit_update AFTER UPDATE ON orders
-- 変更後
CREATE TRIGGER orders_audit_update AFTER UPDATE OF status ON orders
```

trigger本体:

```sql
FOR EACH ROW
INSERT INTO audit_log(order_id, old_status, new_status)
SELECT NEW.id, OLD.status, NEW.status
WHERE NOT (NEW.status <=> OLD.status);
```

MARIA_AUDIT_OF=0/1で同じmariamemバイナリを切り替える。Migrate時に上記DDLだけを置換し、Snapshot前に設定する。pgmem側は公式ソース・公式DDLのまま。前回の「PostgreSQL側を全UPDATE発火にする対照」とは別の実験であり、前回値を流用していない。

MariaDBにUPDATE OF指定がないという以前の説明は誤りだった。今回、実際の12.3.3 embedded guestがこの構文を受理し、期待する基本発火条件になることを実行確認した。

## 同じ回で測った結果

M1/16GiB/macOS27.2.1、Go1.27.4、CGO0、GOMAXPROCS8/GOGC100、test.parallel8。各条件1 warmupの後、順序を回転・反転した固定5組を測定。IPC observerやSQL profilingはなし。mariamemは通常DSNのinterpolateParams=true、16MiB、canonical writeVec。空Write省略等の未採用候補を混ぜていない。

| 5プロセスの中央値 | pgmem公式 | mariamem従来定義 | mariamem UPDATE OF status |
|---|---:|---:|---:|
| サンプル投入 ms | 40.765 | 105.687 | 87.829 |
| サンプルのプロセス別中央値の範囲 ms | 35.857–45.987 | 93.885–121.181 | 83.664–103.584 |
| process wall ms | 458.356 | 611.245 | 572.795 |
| 全thread合計CPU ms | 1430.963 | 2858.123 | 2692.518 |
| 公式recorder elapsed ms | 400.010 | 601.849 | 563.170 |

sampleは各プロセス内21ロードの中央値を、さらに5プロセスで中央値化した。独立中央値同士では変更後のsampleは約16.9%短縮、wallは約6.3%短縮。pgmemとの差はsample47.064ms、wall114.440ms残る。これらの独立中央値差を因果的な寄与率や区間和にはしない。

同じroundの変更後 − 従来定義:

| round | sample ms | wall ms | CPU ms |
|---|---:|---:|---:|
| 0 | −37.517 | −144.589 | −440.427 |
| 1 | −18.677 | −36.670 | +104.941 |
| 2 | −5.083 | −45.672 | −157.862 |
| 3 | −14.589 | −234.879 | +26.199 |
| 4 | −6.056 | +0.394 | −343.396 |
| ペア差の中央値 | −14.589 | −45.672 | −157.862 |

sampleは5/5組で短縮、wallは4/5、CPUは3/5。特にwallは大きく揺れ、CPU改善も一貫していない。共有hostで背景負荷・温度を統制した保証はない。過去の79.7ms等との直接比較はしない。今回の同じ回の対照を優先する。固定回数以外の追加performance反復、失敗したprimaryの再実行、事後除外はない。warmupは全て記録した。

## 正しさと既知の制約

性能用とは別の検証バイナリで、実際のSHOW CREATE TRIGGERとserver versionを確認。その後trigger本体の入口にカウンタを付けた。性能用バイナリにはカウンタ・追加検証SQLは入れていない。

| 操作 | 従来のtrigger入口回数 | UPDATE OF指定のtrigger入口回数 | 監査行 |
|---|---:|---:|---|
| total_centsとupdated_atだけUPDATE | 1 | 0 | 両方追加なし |
| status単独の値変更 | 1 | 1 | 両方1行追加 |
| status=statusの単独指定 | 1 | 1 | 両方追加なし |

[従来witness](TestAuditWitness-0.txt)、[変更後witness](TestAuditWitness-1.txt)は両方PASS。`UPDATE OF`は値の変化ではなくSET対象列を条件にするため、status=statusでも発火し、本体の判定で行追加を抑える。

一方、指示前に行った追加の列順確認では、`SET total_cents=total_cents,status=...`で従来は監査されるが、UPDATE OF指定は入口0回・監査行0件だった。[変更後のFAIL](TestStatusSecond-1.txt)をそのまま保存。これは[既存MDEV-42129](https://jira.mariadb.org/browse/MDEV-42129)と一致する症状。既存issueの扱いに限定し、原因追加調査・修正・起票はしていない。一般のUPDATEで意味が完全一致するとの受け入れはできない。

今回の元モデルケースでstatusを変更するCancelOrder/ShipOrderは、どちらも`SET status=...`の単独指定。この既知の列順問題を含むSQLは性能コーパスにない。元の70テストをそのまま使った全18プロセスは成功、計1260 leaf assertions（primary1050、warmup210）。このPASSと、追加の列順検証FAILは別の事実である。全検証PASSとは報告しない。

## 解釈と次の条件

変更は合計UPDATEの際に余分だった監査triggerの実行を省く。今回の5組ではsample短縮の方向が共通で、移植差に費用があったことを支持する。ただし「SUM以外のtrigger費用約12.5ms」といった以前の別cohort・別境界の観測から今回の差を引かない。

残差にはSQL本体の実装（PostgreSQLの関数内IFとMariaDBのINSERT SELECT WHERE）、型・日時・算術・index表現、driver・wire・guest実行系、Snapshot/Forkモデルの差がある。条件を一つ揃えた結果であり、残りをエンジン単体の性能差とは呼ばない。今後その主張をするには、driver/transportを除く境界とSQL意味を揃えた別計測が必要。今回、その追加調査やengine修正は開始していない。

## 出自・再現

build前にscripts/git_identity.pyでidentityを確認した。

- maria source_commit `0f5b26f370875d26bd337031f48856d8f57c10db`。[identity](maria-identity.json)
- canonical guest SHA256 `5f8b711f8efe31529c12847a093e92b8f962598e035cb1d5e253e41093feee20`。guest再生成なし。
- pgmem source_commit `a61005d37d01e6671f814fe8ca828222e8147df4`、v1.18.2 tag_object_sha `145e5d2fc70983b89a4bdd8438e547fcd60244ed`。[identity](pg-identity.json)
- pgmemは保持済みGit objectのgit archiveから復元。[archive](archive.json)にarchive SHA256を保存。nested cloneや新しい上流sourceは使っていない。
- Maria harness元は`13632c900df99268fc7ad8e3c60573154a5e00f4`の`benchmarks/audit-trigger-control-20261113/harness`。[差分](harness.patch)、[入力](inputs.json)、[binary hashes](binary-hashes.json)。

新managed workspaceに製品pinのworktree、temp/pgmemにpgmem固定sourceを配置。この記録をevidence、harnessをtemp/mariaにコピーし、setup.py、build.py、witness.py、measure.py、analyze.pyを順に実行する。setup.pyは保存済み元seedから再生成する。witness.pyは別binaryを作る。列順の既知FAILを記録し、基本発火witnessの失敗なら停止する。

buildはworkspace runnerで1800秒、容量10GiB/空き12GiB。witness/measureは直接監視、各測定130秒timeoutと前後disk guard。pgmem起動のlocalhost待受を含め、全計測プロセスを同じsandbox外権限で実行した。

解析再確認はこのディレクトリで`python3 analyze.py`。全trace、output、witness結果を保存。製品runtime・main・CI・releaseは変更していない。
