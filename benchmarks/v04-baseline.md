# v0.4 performance/resource baseline

v0.3.0 公開済み成果物と current main を固定ローカル環境で測定。製品・runtime・cache・API・Snapshot/Fork の挙動は変更していない。

製品ソース: `400b7f564277b0627c3f0400c3e07e18fa0598d8`。ブランチ: `v0.4/baseline`。測定日: 2026-10-01。
固定参照: MacBook Air M1、16 GiB、macOS 27.0 (26A428) arm64、Go 1.26.8、Python 3.14.7。
公開 native / wheel の SHA256 は GitHub Release の digest と照合済み。公開 guest に既存の段階計測マーカーがあり、追加 instrumentation は不要だった。

## 再現・比較契約

公開 v0.3.0 native と wheel を使う。Go は main の public API、SQLAlchemy は installed wheel の consumer 経路。両経路を混同しない。
各コマンドを順に単独実行し、回帰チェックを並行させない。将来の spike も同じ fixture、境界、回数、toolchain、sampling を使い、ソース・成果物ハッシュと環境差を記録する。

```sh
GOTOOLCHAIN=go1.26.8 /path/to/python benchmarks/v04_baseline.py \
  --native-dir /path/to/native --runs 30 --scaling-runs 10 \
  --json benchmarks/results/v04-baseline.json
# installed v0.3.0 wheel + SQLAlchemy/PyMySQL/pytest; clear native overrides
/path/to/python benchmarks/v04_orm.py --runs 3 --json benchmarks/results/v04-orm.json
/path/to/python benchmarks/v04_report.py benchmarks/results/v04-baseline.json \
  benchmarks/results/v04-orm.json --output benchmarks/v04-baseline.md
```

生データは ignored results に保存。比較用の PID を除いた観測値・分布・ハッシュは [v04-baseline-values.json](v04-baseline-values.json)。失敗・遅い試行の除外はしない。
startup は2 warmup + 30独立 Go プロセス。各プロセスで fresh Start、1,000行 fixture 作成、cold Snapshot、prepared Fork を行う。OS/AOT/file cache は flush しない。
fixture は既存 InnoDB benchmark_rows (INT PK / VARCHAR(64)、32文字 payload)、1,000行 batch、commit、COUNT 確認。Snapshot は SQL 接続の切断 acknowledgement 後に開始し、source を消費する。
API 復帰と最初の SQL 成功は別の境界。Start→SELECT 1 は空 DB、Start→fixture はschema/seed/COUNTを含む。prepared Fork→COUNT は fixture preparation を除外する。Snapshot の時間を Fork に暗黙に含めない。

## 起動 (ms)

| 境界 | n | min | p50 | p95 | max |
|---|---:|---:|---:|---:|---:|
| Start→SELECT 1 | 30 | 297.5 | 308.5 | 335.3 | 339.8 |
| Start→1,000行 fixture ready | 30 | 299.3 | 312.2 | 342.9 | 400.4 |
| cold Snapshot 作成 | 30 | 370.5 | 404.6 | 473.3 | 479.1 |
| prepared Fork→COUNT | 30 | 278.7 | 288.7 | 349.2 | 392.7 |
| Snapshot 作成 + Fork→COUNT (paired sum、seed除外) | 30 | 658.3 | 692.6 | 791.4 | 825.7 |
| Start API 復帰 | 30 | 287.7 | 301.6 | 329.9 | 334.5 |
| Fork API 復帰 | 30 | 271.4 | 280.6 | 342.9 | 386.6 |

## 孤立 DB scaling

各 concurrency は1 warmup + 10独立試行、round-robin。1,000行 prepared snapshot の独立 Fork を同時に開始し、全 DB の COUNT が成功するまで保持。G(0) は live runtime のない Go snapshot holder、G(n) は host + n runtimes。
CPU は G(0)→all-ready カウンタ取得の host + runtime 累積 CPU 差。最終 SQL 後のカウンタ収集も含む。teardown・fixture preparation は含まない。sampling 50 ms + scan overhead。
主メモリは process-tree physical footprint。shared pages/OS accounting の影響があり、exclusive allocation ではない。peak は観測した最大値。Close 後の host heap retention と runtime 残留を分ける。

| DBs | ready ms p50/p95 | CPU s p50/p95 | CPU s/DB p50/p95 | incremental MiB p50/p95 | MiB/DB p50/p95 |
|---:|---:|---:|---:|---:|---:|
| 1 | 283.6 / 296.9 | 0.320 / 0.360 | 0.320 / 0.360 | 267.5 / 290.0 | 267.5 / 290.0 |
| 4 | 427.8 / 476.7 | 1.785 / 1.925 | 0.446 / 0.481 | 1124.8 / 1169.1 | 281.2 / 292.3 |
| 8 | 860.2 / 893.2 | 4.602 / 4.749 | 0.575 / 0.594 | 2220.1 / 2322.6 | 277.5 / 290.3 |
| 16 | 1889.6 / 1981.7 | 9.463 / 9.654 | 0.591 / 0.603 | 4493.2 / 4527.8 | 280.8 / 283.0 |

CPU/DB の p50 は ×1 の0.320 sから ×16 の0.591 sへ1.85倍。CPU合計は29.6倍。8 CPUの同一環境での実測であり、原因の帰属はこの表からは断定しない。

| DBs | G(0) MiB p50/p95 | G(n) total MiB p50/p95 | peak total MiB p50/p95 | after Close MiB p50/p95 | after Close − G(0) MiB p50/p95 |
|---:|---:|---:|---:|---:|---:|
| 1 | 8.1 / 8.3 | 275.6 / 298.2 | 275.7 / 298.2 | 9.6 / 9.8 | 1.4 / 1.8 |
| 4 | 8.2 / 8.4 | 1133.1 / 1177.0 | 1133.1 / 1178.4 | 10.3 / 10.6 | 2.1 / 2.6 |
| 8 | 8.0 / 8.4 | 2228.0 / 2330.6 | 2228.0 / 2330.6 | 11.1 / 11.6 | 3.0 / 3.5 |
| 16 | 8.1 / 8.3 | 4501.3 / 4535.8 | 4504.7 / 4535.8 | 11.8 / 12.3 | 3.8 / 4.2 |

起動中のカウンタ scan は 41 回 temporarily unavailable。G(0)/ready/after-Close の必須取得は全試行成功。欠損は0として補完せず、sampled peak は過小観測の可能性を含む。PIDを除いたtimelineと欠損時刻も比較JSONに保持。

40/40 measurement batches 成功。全 Close 後に runtime descendants は0。長寿命 host の leak soak は測っていない。

## SQLAlchemy representative workload

v0.3 dogfood の `test_03_update_commit_and_delete` を直接呼ぶ。User/Address schema、1組の seed、通常の QueuePool と SQLAlchemy Session を利用。relationship read/join、update+commit、delete+commit、最終 COUNT を両経路で同じように実行。
fresh は Start + schema/seed、prepared は Start + 同じ schema/seed + Snapshot をスイート冒頭に1回行い、各 test で Fork。両方とも fixture COUNT確認、同じ CRUD、pool dispose、WaitDisconnected、Close、PID消滅・一時ディレクトリ削除の確認を含む。prepared setup/Snapshot と最終 Snapshot cleanup は suite total に含む。
各サイズ3スイート。mode順序を交互に切り替え、1 test warmup は集計から除外。pytest runner overhead は含まない。SQLAlchemy 経路は Python wrapper + 別 Go host であり、Go core の起動値とは直接比較しない。

| tests | mode | suite s p50/p95 | setup s p50/p95 | per-test ready ms p50/p95 | CRUD ms p50/p95 |
|---:|---|---:|---:|---:|---:|
| 10 | start | 3.845 / 3.871 | 0.000 / 0.000 | 361.3 / 382.4 | 7.4 / 11.3 |
| 10 | fork | 4.965 / 5.627 | 0.785 / 0.787 | 366.8 / 408.7 | 7.1 / 10.6 |
| 50 | start | 19.515 / 19.558 | 0.000 / 0.000 | 363.3 / 390.1 | 7.6 / 11.6 |
| 50 | fork | 22.233 / 22.657 | 0.802 / 0.847 | 368.4 / 398.4 | 7.0 / 8.6 |
| 100 | start | 39.012 / 39.016 | 0.000 / 0.000 | 364.1 / 389.0 | 7.7 / 11.8 |
| 100 | fork | 43.142 / 44.037 | 0.861 / 0.863 | 370.0 / 401.1 | 7.1 / 15.1 |

packages: {'mariamem': '0.3.0', 'SQLAlchemy': '2.0.54', 'PyMySQL': '1.2.3', 'pytest': '8.4.2'}。全18 measurement suites / 960 isolated tests成功。MariaDB: `13.1.0-MariaDB-embedded`。

## Architecture attribution

通常測定とは別に5独立試行で既存 guest/host stages を取得。以下は p50/p95 ms、nested scopes は重なるので合計しない。小標本は概算の帰属用。

| cost / boundary | Start | Fork |
|---|---:|---:|
| native resolution/verification | 44.3 / 46.9 | 44.0 / 44.8 |
| host process spawn | 1.1 / 1.2 | 1.2 / 1.2 |
| guest MariaDB init | 210.8 / 231.0 | 55.9 / 89.0 |
| guest bootstrap/ready | 0.2 / 0.3 | 0.2 / 0.3 |
| restore copy | 0.0 / 0.0 | 74.7 / 77.9 |
| pre-main/runtime/ready envelope residual | 40.6 / 45.8 | 39.8 / 40.0 |
| host snapshot validation | — | 62.3 / 63.9 |
| remaining caller/host/client intervals | 6.8 / 9.8 | 6.6 / 7.9 |

runtime envelope residual は host spawn-return→guest-ready から guest main→ready-prepared の実測 duration を引いた値。Wasmer/WASIX/CRT・static constructors・ready delivery・scheduling が含まれ、runtime creation の専用 timer は存在しない。
guest main→restore開始、open準備、bootstrap、host wire/API handoff、client handshake/COUNT は残余の小さい区間として JSON に保持。MariaDB init は InnoDB を含み、個別エンジンの所有コストは未帰属。
host/guest clock の絶対原点は合わせない。CPU/メモリを guest init/restore の各境界に割り当てる instrumentation はないため、段階別 memory/CPU の精度は主張しない。Snapshot export ack はshutdown+export、publish はcopy+inventory/hashを含む。

## 回帰確認

canonical `scripts/verify.py check`: Go tests/vet と `go test -race ./benchmarks/goisolation`、Python 368 passed / 3 skipped、public-source check 成功。`git diff --check` 成功。実 DB の COUNT、Snapshot consumption、session isolation、runtime cleanup は各 benchmark の既存 correctness checks も通過。
最初の予備測定は回帰チェックと一部並行したため不採用。採用値は単独再測定。既存の未追跡 npm ファイルが public-source 検査を妨げたため、検査中だけ退避し、その後復元した。

### Current bottlenecks

Fork の時間コストを実測 p50 順に並べる（独立scopeのため合計値ではない）:

1. guest / restore_complete: 74.7 ms。
2. host / metadata_snapshot_validated: 62.3 ms。
3. guest / server_init_complete: 55.9 ms。
4. api_startup / native_resolved: 44.0 ms。
5. startup_envelope / outside_recorded_guest_interval: 39.8 ms。

Start の MariaDB init: 210.8 / 231.0 ms。Snapshot 作成: 404.6 / 473.3 ms。
資源の最大実測規模は ×16: ready total 4501.3 / 4535.8 MiB、CPU 9.463 / 9.654 s。時間とbyteを単一順位にはしない。

### Candidate v0.4 KPIs

以下は比較対象の現状値（p50/p95）。改善の合格閾値は未設定。

| KPI | current baseline |
|---|---:|
| single DB Start→SELECT 1 | 308.5 / 335.3 ms |
| Start→1,000行 fixture ready | 312.2 / 342.9 ms |
| prepared Fork→COUNT | 288.7 / 349.2 ms |
| cold Snapshot | 404.6 / 473.3 ms |
| ×1 incremental memory/DB | 267.5 / 290.0 MiB |
| ×16 incremental memory/DB | 280.8 / 283.0 MiB |
| ×16 ready total / peak total | 4501.3 / 4535.8 (ready), 4504.7 / 4535.8 MiB |
| ×16 group-ready | 1889.6 / 1981.7 ms |
| ×16 CPU total / per DB | 9.463 / 9.654 (total), 0.591 / 0.603 s |
| ×16 after Close footprint / increment | 11.8 / 12.3 (total), 3.8 / 4.2 MiB |
| runtime descendants after Close | 0 (40/40 batches) |
| SQLAlchemy 100 tests start suite total | 39.012 / 39.016 s |
| SQLAlchemy 100 tests fork suite total | 43.142 / 44.037 s |

### Architecture questions

- 外部 runtime 境界を除く spike は、pre-main envelope と CPU、per-DB footprint のどこを削減できるか。MariaDB init の実測部分はどれだけ残るか。
- CoW/shared prepared state は、同じ fixture・独立 DB semantics で ×1/4/8/16 の incremental footprint と total peak を下げられるか。初回書き込み後のコストはどう変わるか。
- runtime sharing は CPU/DB と ×16 group-ready、Close 後の保持量を改善するか。1 DB の failure/teardown が他 DB に波及しないか。
- restore-path redesign は restore copy と snapshot validation、Snapshot publish の各コストをどれだけ下げるか。検証・mutation拒否・Snapshot source consumption を保てるか。
- 同じ SQLAlchemy CRUD の10/50/100 suitesで、setup+Snapshotを含む総時間とcleanupまで改善するか。prepared手法の償却がどのサイズから現れるか。
- 長寿命 host の反復作成/Close でも runtime 残留0を維持し、host retained memory が増え続けないか。

採用 architecture は未選択。上記の実測境界・資源指標で個別 spike を比較する。
