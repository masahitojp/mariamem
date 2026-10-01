# v0.4 generated-Go candidate — FD follow-up and public-boundary measurement

> **更新:** `023796b9`のFD停止条件は本follow-upで解消し、correctness gate後に
> selected local candidateの公開API計測を実施した。最新結果は末尾の
> 「Directory-FD identity fix / integration continuation」を参照。以下の初回記録は履歴として保持する。

## 初回integration結果 (023796b9)

**NOT READY — BLOCKERS REMAIN**。

既存ORMを実験経路で通すところまで進んだが、追加のdirectory-FD補完が
rename/path reuse下で別のファイルを開くことを決定的に再現した。
製品化に必要な「file identity/offset handling correct」の条件を満たさない。
既存の意味を弱めず互換性ギャップを報告する停止条件に従い、ここで統合を停止した。
生成Goを製品経路へ有効化していない。production-quality candidateの完成や、
全失敗経路の無漏出を宣言するものではない。

設計は [production architecture](../docs/v04-generated-go-architecture.md)、
数値・ケース結果は [evidence](v04-generated-go-candidate-evidence.json)、
再現方法は [FD gate](spikes/generated-go-integration/README.md) を参照。

## 入力 / 環境

開始HEAD `8b368a79eb3a0070f84168b1c70a1e2896e4a5ca`。
branchは `v0.4/generated-go-integration`。採用した各spikeの正確なSHAは設計文書に記録した。
macOS27.0 (26A428)、Apple M1 arm64、16GiB、Go1.26.8、Python3.14.7。
Ubuntu24.04 x86_64の候補acceptanceは未実施。

- legacy-EH WASM SHA256: `6a2e1a8c00da1953cf0379e6cf5464c0f3f3668de674467673ee701230dd27d3`
- converter: `shibukawa/wasm2go-fork` commit `ac98bcf00c17d8531f0c071a9836d0b50975e7ff`
- imported-memory / import-function-index patchesは既存spikeのものを使用。
- full guestの生成Goに診断用hostを追加してcompile/link、fresh guestを実行した。
  使用バイナリと生成baseのhashはevidenceに記録した。

## 設計 / build-provenance gate

採用方針は生成Go guest subprocess、既存host/MySQL-wire、cold prepared files、
各childのfresh memory/thread/TLS/FD/runtime状態。
公開Go/Python APIやcold Snapshotのsource消費・transaction拒否・rollback option・
build identity・検証・所有権を維持する。ready heap、live threads、waitersを複製しない。

設計文書を作成してから診断を始めた。今回の自動setupは**FD監査の再現用**であり、
MariaDB sourceから配布artifactを生成するproduction pipelineではない。
以下は互換性ゲート後の未完了release blockersである：

1. canonical source/overlays → pinned WASIXCC/legacy sysroot/Binaryen → WASM →
   pinned converter/patches → Go → native bundleの自動再生成と両platform acceptance。
2. 各段階のinput/tool/patch/source inventory/checksumを連結するprovenance。
3. 実行されるcompiled guestと、検証されるmodule/build identityの結合。
   診断argv adapterはmodule引数を実行しないため、製品trust contractを満たさない。
4. runtime kindを明示するbundle/cache/download/wheel対応、全notice/source/license review。
   MariaDB/lite4mariadbのGPL由来義務は独立に残る。

legacy EHは内部build bridgeとする。Wasmer7.4.2によるこの中間artifactの検証は利用できない。
静的feature/import検査、生成codeのcompile、primitive regression、正常guestとの
observable behavior比較を代替検証とする。same-runtime検証の実績は主張しない。

## Aria互換性の切り分け

同じSQLを正常Wasmer guestと生成Go guestに送った。
未修正の生成GoではInnoDBの単純SQLは通るが、`DESCRIBE`、`SHOW COLUMNS`、
`information_schema.columns`、Aria INSERT/SELECTが1030 / errno29 (I/O error)。
Wasmerでは成功し、不存在tableのDESCRIBEは期待どおり1146だった。

I/O traceではAriaのMAI/MAD作成、read/write/seek、8192-byte化は正常だった。
MariaDB `mysys/my_symlink.c` の`my_realpath()`からのfilesystem probeを追った結果：

| 段階 | 発見 / 結果 |
| --- | --- |
| 元のMemFS | regular/missing双方のreadlinkに`fs.ErrInvalid`を返し、errno変換がEIO29へ落ちる |
| readlink補完 | regular→EINVAL28、missing→ENOENT44。決定的な縮約は修正前FAIL、修正後PASS |
| 次の失敗 | libcが`/mariadb`のdirectory FDを開き、`data`をそのFDから開く。dirFD3のみ許すpath処理がEBADF8 |
| relative-FD補完 | open/readlink/statをdirectory objectから解決。上記schema SQLとAria INSERT/SELECTが成功 |
| 追加の契約監査 | 解決とopenの間にrename/path reuseを入れると、directory FDが別のdirectoryへ実質的に再束縛される。FAIL |

MariaDB source、SQL、同期、timeoutは変更していない。これらの補完は診断moduleにのみ存在する。

## 停止したFD契約

再現順序：`a/value=original` → `a`をdirectory FDとしてopen → descriptorからpathnameを解決 →
`a`を`original`へrename → 新しい`a/value=replacement`を作成 → 同じdirectory FDから`value`をopen。

| 実装 | 読めた内容 |
| --- | --- |
| native `openat`相当 (`os.open(..., dir_fd=...)`) | `original`、PASS |
| 補完した生成Go adapter | `replacement`、FAIL |

test hookはdescriptor→path解決とopenの境界でfilesystem変更を行う。
確率、sleep、guest address、MariaDB symbolに依存しない。
自動setupした別moduleでも`go test -race`で同じFAILを再現した。
Go race detectorの警告はなく、個別mutexがあっても残るfilesystem TOCTOUである。

object identityからpathnameを毎回探すだけでは不十分。
製品化にはdescriptorに固定されたatomicなpath resolutionとoperationが必要。
rename/unlink/path reuse、close/dup、rights、offset、error処理を一貫した契約で検証する。
pathname retryや特定MariaDB directoryへの特別扱いは対処にしない。
今回の小さなadapterを安全な実装として昇格させず、通常経路を維持した。
これはwasm2go自体の実行不可能性の証明ではない。採用アーキテクチャは維持する。

## 互換性 / lifecycle preflight

公開wrappers・既存hostと、上記診断guest/file-transfer adapterを接続した。
Snapshotはguestの通常shutdown後に`/snapshot-out/data`をexportし、Forkは検証されたfilesを
別MemFSへcopyしてfresh guestを開始した。live execution stateは再利用していない。
このcopy adapterはproduction prepared-file mappingsの実装ではない。

| 検査 | 実測結果 / 限界 |
| --- | --- |
| SQLAlchemy dogfood | Start/Fork/Fork/Start、各11件PASS、計44件。CRUD、relationship、tx、rollback、制約、metadata reflection、pool/session、rowcount、shutdown |
| GORM dogfood | Start/Fork/Fork/Start、各8 subtests PASS。repeated AutoMigrate/schema discovery、CRUD/relations、tx/rollback/errors、sessions、shutdown |
| GORM cleanup observer | Wasmer名filterを廃止し全direct childrenを検出。上記4回を再実行しPASS、各caseとsuite終了後のchild一覧は空 |
| generated guest既存integration | Go race PASS (20.749s)、Python timeout/multiclient 3 PASS (1.59s)。capacity/MaxSessions、session isolation、Snapshot/Fork、fatal timeout/deadline/cancelとprocess回収、repeated Close |
| generated auth key self-test | exit0 |
| directory-FD契約 | FAIL。従って上記はpreflight evidenceであり製品acceptance PASSではない |

SQLAlchemyの0.2.0 version assertionだけを現在の0.3.0へ更新した。
SQL、model、DDL checkfirst、GORM AutoMigrate、transaction/assertionは弱めていない。

### shim監査状態

imported memory、thread spawn/TLS、atomic/futexの縮約実績は以前のspikeを維持。
通常worker exit/join、MemFSの通常I/O、fresh runtime、normal shutdownはpreflightでも通過。
path_open2/readlink/relative FDは上記で具体的なproduction blockerを発見した。
signals、abnormal worker exit、timer/wake競合、startup cancellation、forced Close during
startup、partial FS initialization、corrupted prepared files、全面的なdescriptor/thread cleanupは
production candidateとして未完了。既存hostで通ったfatal query cancellationと混同しない。

legalなInnoDB page-cleanerの約1秒condition-variable raceは変更していない。
今回のFD不具合を理由にfutex/condvar調査を再開していない。

## benchmark status / 比較

correctness gate失敗のため、30-run Start/child、×1/4/8/16、SQLAlchemy10/50/100の
**canonical production benchmarkは実施しない**。性能で未解決の契約違反を正当化しない。
ORM acceptance runnerのwall timeはsuite benchmarkとして使用しない。

| 指標 | Wasmer v0.4 baseline | 過去の生成Go / prepared-files spike | 今回のproduction candidate |
| --- | --- | --- | --- |
| Start → first SQL p50/p95 | 308.5 / 335.3ms | direct ready約40ms、wire/verification/SQL約99ms median | 未測定 |
| prepared child → SQL p50/p95 | Fork→COUNT 288.7 / 349.2ms | prepared files 34.2 / 37.8ms | 未測定 |
| incremental memory/DB | ×16約280.8MiB | generated physical約89MiB、RSS約108MiB；prepared physical77.16MiB | 未測定 |
| ×16 ready total | 約4.5GiB | generated physical約1.375GiB | 未測定 |
| SQLAlchemy100 tests | Start約39.0s / Fork約43.1s | 同じproduction suite境界の数値なし | 未測定 |

physical footprintとRSS、COUNTとfirst SQL、directとpublic wire境界を交換可能な値と扱わない。
古い数値はhistorical referenceのまま。新しいcanonical v0.4 referenceは未成立。
pgmem/Testcontainersとの製品比較・marketing claimは行わない。

## 通常経路の回帰 / release gate

- canonical `scripts/verify.py check`: Go test/vet PASS、Python368 PASS / 3 opt-in SKIP、public-source PASS。
- 通常Wasmer `scripts/verify.py integration`: Go race PASS (8.818s)、Python3 PASS (2.41s)。
- `git diff --check`: PASS。
- 生成moduleは独立`go.mod`、templatesは`.go.txt`、artifactsはignored build内。通常build discoveryから隔離。
- 既存の未追跡npm filesは内容を保って一時退避し、確認後復元。runtime/API/guest/cache設定/MaxSessionsへの変更なし。

最優先blockerはgeneric filesystem/FD契約の正しい実装と決定的な回帰検証。
その後にcompiled-guest trust binding、再現可能なproduction pipeline、両platformとfailure-path
acceptanceを完了し、初めてcanonical benchmarksへ進む。これらの後続統合作業は開始していない。

**NOT READY — BLOCKERS REMAIN**

## Directory-FD identity fix / integration continuation

開始SHA: `023796b9e357ff2dfae9894c3b4e52d75c39db20`。同じbranchで修正。通常runtime、main、guest/MariaDB source、public API、SQL、futex/condvar/timeout、MaxSessionsは変更していない。

### 原因とgeneric修正

旧adapterはopened `memFile.node`からpathnameを探し、FS lockを解放した後にその名前をopenした。個々のoperationのmutexでは、この間のrename + name reuseによるTOCTOUを防げない。

directory FDを元のMemFS nodeへ固定し、component traversalとopenを同じtree lock内で行う。parent identityはrename時に更新。unlink済みnodeはopen参照の寿命まで保持し、そのdirectoryへの新規作成はENOENT。root preopenも実際のFD table entryにし、close/dup/reuseで古いrootを復活させない。path文字列はdiagnostic/access-hook labelだけで、object探索に使わない。対応しないFS bindingはENOTSUPで拒否する。

旧決定的reproducerは旧moduleでFAIL (`replacement`)を再確認した。修正後は同じrename/name-reuse順序を必ず実行して`original`を読む。nested open、parent移動、unlink、FD close/dup/reuse、並行rename、stat/readlinkも検査する。MariaDB path/addressの特別扱いはない。

### 継続した候補の境界

FD gate後、checksum結合・private prepared-filesを持つselected local candidateを構築した。通常runtimeには組み込まず、NativeDir overrideで既存Go/Python wrapperとhostへ接続した。歴史的bundle filenameの`wasmer-headless`は実際の生成Go executableであり、Wasmerもshell adapterも起動しない。manifestは`runtime_kind=generated-go` / `public_release_ready=false`。

- 実行前にmodule SHAをcompiled guest input SHAと比較。違うmoduleはguest entry前に拒否した。既存artifact identity/checksum・Snapshot build/inventory/hash検証は残す。
- accepted生成Go/assembly全inventoryをinstallerで検証し、source adaptationを自動適用する。正しい2-patch converterを再実行し、48 output filesのbyte一致を確認した。
- prepared cold filesは子専用MemFS nodesとMAP_PRIVATE viewへ接続。fresh linear memory / thread / TLS / FD / offset / wait queue。file growthは子ownedのstorageになる。
- 子間/base不変、growth/rename、一方のmapping Close、partial invalid treeの検査を追加。join全完了後だけmappingを解放する。
- I/O diagnostic overridesを計測candidateから除去した。build/guest inputはStart時間に含めない。

### 再実行したcorrectness gates

| 検査 | 結果 |
| --- | --- |
| 決定的FD reproducer | before FAIL / after PASS。race detector警告なし |
| focused FS / primitive tests | FD 8件 + prepared-files 2件と既存primitiveがrace PASS。readlink errno regression PASS。合法な1秒ordering testも維持 |
| generated-Go Start/Fork integration | Go race PASS、Python 3 PASS。capacity/session/Snapshot/timeout/deadline/cancel/repeated Close・回収 |
| SQLAlchemy dogfood | Start/Fork/Fork/Start、11×4=44 PASS。ORM semantics変更なし |
| GORM dogfood | Start/Fork/Fork/Start、8×4=32 PASS。repeated AutoMigrate/schema discovery/cleanupもPASS |
| existing raw-wire acceptance | 38 checks PASS + SQL/protocol checks。CLIENT_FOUND_ROWS/auth/reconnect/error behavior |
| existing Snapshot acceptance | 50 checks PASS。transaction拒否/rollback option/source消費/build mismatch/corruption/concurrent children/isolation/close |
| 通常Wasmer integration | Go race PASS、Python 3 PASS。正常経路は維持 |
| normal checks | Go test/vet、Python 368 PASS / 3 SKIP、public-source PASS |

### 公開Go API計測 (ms)

同じlocal reference、同じ既存goisolation 1,000行fixture/SQL検証。2 warmup + 30独立runnerでStart、schema/seed、cold Snapshot、prepared Fork。OS cachesはflushしない。最初のpilotはconverter replayとの重複を理由に**全体**を無効として保存し、他のジョブ終了後に全30回を再実行した。遅い試行を選別していない。

| 境界 | n | min | p50 | p95 | p99 | max | ≥900ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Start→SELECT 1 | 30 | 81.6 | 86.1 | 692.9 | 1089.8 | 1090.9 | 2/30 |
| Start→fixture COUNT | 30 | 85.6 | 90.0 | 1109.6 | 1124.4 | 1128.9 | 4/30 |
| cold Snapshot取得 | 30 | 4942.3 | 5148.1 | 6669.3 | 6970.0 | 6975.8 | 30/30 |
| prepared Fork→COUNT | 30 | 147.5 | 150.3 | 168.3 | 180.9 | 185.4 | 0/30 |

Startの2/30 (~6.7%)、seededの4/30 (~13.3%)は約1秒のcluster。既知の合法InnoDB raceは変更していない。このrun自体はtraceなしなので、全slow trialの原因を新たに証明したとは言わない。Start p95 692.9msはfast/slow間のlinear interpolationで、典型的な独立clusterを表す値ではない。

別の30独立Startでready countersを測定。SQL後のcounter取得/observer/version queryをCPU終点に含め、teardownは除外。
CPU p50/p95 0.105/0.142 CPU-sec。増分physical p50 90.40MiB、ready process-tree physical 94.95MiB、RSS 123.83MiB。
counter probeのStart分布は別sample setでp50/p95 83.7/1086.8ms、≥900msは4/30件。30件のtail率は不安定であり、primary latency runと合成しない。

### Prepared child scaling

各×1/4/8/16は3独立group。fixture preparation/Snapshotを除き、既存public Fork→COUNTまで測る。CPUはhost+guest、全ready取得まで。physicalはmacOS accountingでexclusive private allocationではない。RSSをphysicalの代用にしない。

| DBs | group ms p50/p95 | CPU-sec p50 | increment MiB/DB p50 | ready total physical MiB | ready RSS MiB | after Close − baseline MiB |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 153.7/166.6 | 0.187 | 86.19 | 94.47 | 131.53 | 1.14 |
| 4 | 192.9/909.4 | 0.853 | 85.61 | 350.97 | 476.48 | 1.61 |
| 8 | 329.5/1001.5 | 1.909 | 85.56 | 692.68 | 936.34 | 3.20 |
| 16 | 660.0/678.2 | 3.824 | 85.25 | 1372.00 | 1852.05 | 3.81 |

12/12 groups成功。全Close後はrunnerだけでguest descendants 0。残った数MiBはcallerのGo heap/bookkeepingで、長期leak-free保証にはsoakが必要。macOSのこのcounterではprivate dirtyは取得できず、物理の内訳を過剰に断定しない。sampled peak、raw counters、sampling gapsはJSONに保持。

### SQLAlchemy suite (seconds)

v0.3 dogfoodの同じ`test_03_update_commit_and_delete`。Startはschema/seed込み、Forkはスイート冒頭のbase preparation/Snapshotと最終cleanup込み。接続/relationship/CRUD/commit/dispose/WaitDisconnected/Close/PID消滅・temporary directory削除を両方同じ条件で検査。各3 suites、1-test warmup除外、18 measurement suites / 960 isolated testsすべて成功。

| tests | mode | suite p50/p95 | setup p50 |
| ---: | --- | ---: | ---: |
| 10 | start | 2.35/3.21 | 0.00 |
| 10 | fork | 7.71/7.89 | 5.28 |
| 50 | start | 9.87/11.51 | 0.00 |
| 50 | fork | 15.98/16.33 | 5.47 |
| 100 | start | 25.38/26.35 | 0.00 |
| 100 | fork | 26.00/26.65 | 5.20 |

### 境界差とrelease前の説明が必要な差

- Wasmer baseline Start→SQL p50 308.5msに対し、このselected candidateは86.1ms。prepared Fork→COUNTは288.7→150.3ms。Start p95は335.3→692.9msで、合法な約1秒tailを含む。
- ×16のprepared増分physicalは280.8→85.25MiB/DB、total physical約1.34GiB。CPUは9.46→3.82 CPU-sec。過去のdirect prepared-files 77.16MiB/34.2msと公開APIの85.25MiB/150.3msを同一境界とは扱わない。
- 1回の既存timingによる概算: native resolution/hash約48.6ms、host Snapshot validation約62.2ms、spawn→guest ready約35.5ms、client/SQL等残差。これらでpublic Forkの約150msを説明できる。検証を省略して34msへ見せていない。
- **Snapshot取得は悪化:** Wasmer p50 404.6ms → candidate 5148.1ms。1回のtraceではdrain→export/guest-stop約4914.6ms、publish約242.8ms。guest shutdown/file-copy/native-export envelopeが大半だが、各内部費用はまだ分離していない。root cause確定/改善なし。これはready-memory reentryで解決しない。release前のperformance blockerとして残す。
- SQLAlchemy100 suite p50: Wasmer Start約39.0 / Fork約43.1s → candidate 25.38 / 26.00s。Forkのsetupに約5秒Snapshotを含むので、childだけを抜いて勝利とは言わない。
- pgmem/Testcontainersの新測定やmarketing比較は行わない。現在のlocal selected candidateの比較値であり、最終product benchmarkの宣言ではない。

### 残るrelease gates

FD bugは解消し、**v0.4統合は計測まで再開できた**。normal runtimeにはまだ有効化していない。canonical MariaDB source→legacy-EH WASM→pinned converter→bundleの完全自動pipeline、runtime-kind付き配布/cache/wheel、notice/source/license review、exact-byte Ubuntu x86_64/macOS15 arm64 acceptance、signals/abnormal worker/cancellation/lifecycle soak、完全なWASIX FS rights/path契約が未完了。今回のbindingとconverter output replayだけで全pipeline完了とは言わない。既存nativeファイルのhistorical名もlocal compatibility bridgeである。

Snapshot exportの約5秒regressionは追加のrelease前調査事項。性能で権限/検証/SQL意味を弱めない。このtaskでは無関係な最適化やruntime redesignを行わない。ready heap、live threads、TLS、waitersの複製も行わない。

最終ソースから再構築したnative bundleは測定bundleと全4artifactがbyte一致した。

最終testsとartifact hashesは[evidence](v04-generated-go-candidate-evidence.json)の`fd_followup`。raw resultsはignored benchmarks/resultsへ保存、再現コマンドは[README](spikes/generated-go-integration/README.md)。

**NOT READY — BLOCKERS REMAIN**

## Snapshot regression local attribution

対象SHA `c21ec0a3ee05f098e63f69521524e21c0ec4cf82`。同じmacOS arm64 reference環境、公開APIの1,000-row fixture → Snapshot → Fork/COUNTを使用。通常candidateを変更せず、独立した診断moduleにtimestampとファイル拡張counterだけ追加した。性能修正、MariaDB設定変更、同期変更は行っていない。

**原因を確認:** `generated/base/base.go` の `memFile.writeAt` はファイルが伸びるたびに `make([]byte, end)` し、既存内容を全コピーする。`guest/snapshot_fs.inc` の `snapshot_copy` は通常どおり64 KiB単位で書き込むため、コピー先MemFSで二次的な累積コピーが発生する。FD identity修正とは別の、既存のファイル拡張実装の問題である。

### 内部費用の分離

CPU profileなしの2回。requestの4-byte headerは分割Readにも対応して検出。`snapshot-out/data` の最初のmkdirをguestコピー開始とした。この位置は `guest/resident.inc` のsession/thread drainと `l4m_close()` の後。復元用ファイルの内容や書き込み順は変更しない。

| phase | trial 1 | trial 2 |
| --- | ---: | ---: |
| guest request → copy開始（shutdown等） | 1.55 ms | 1.08 ms |
| copy開始 → guest return / worker join | 5821.40 ms | 4965.20 ms |
| うちMemFS grow allocation + 既存内容copy | 5764.04 ms | 4917.91 ms |
| native filesystem export | 168.40 ms | 133.87 ms |
| host guest-stopped → snapshot-published | 283.30 ms | 298.08 ms |
| public Snapshot全体 | 6401.82 ms | 5534.94 ms |

grow処理がguest copy envelopeの約99%を占める。残差には新しい書き込み内容のcopy、metadata、GC、プロセス終了、host/client処理と計測がある。hostの `export_acknowledged` はprocess finishも待つため、guestのackだけの時間ではない。診断の2回をcanonical 30-run benchmarkの置き換えにはしない。

各Snapshotでcopy先ファイルのgrowは2216回、累積allocation約75.54 GiB、既存内容copy約75.40 GiB。最大要因は96 MiBの `ib_logfile0`: 1536回、既存内容copy **71.95 GiB**。redo log growだけでtrial 1の約5.53秒を使った。巨大な最終Snapshotや常駐memoryという意味ではなく、同じ内容の繰り返しallocation/copyである。

### 最小のalgorithm確認

同じMemFS、同じ96 MiBの内容をwrite形状だけ変えて生成。すべてSHA-256一致。各1回の診断で、product benchmarkや提案するguest変更ではない。

| write単位 | grow回数 | 累積既存copy | wall | CPU | GC回数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 64 KiB | 1536 | 71.95 GiB | 4939 ms | 5.352 s | 760 |
| 1 MiB | 96 | 4.45 GiB | 343 ms | 0.393 s | 48 |
| 96 MiB（1 write） | 1 | 0 | 10.7 ms | 0.0108 s | 1 |

ソース、実際のSnapshot counter、同じbytesの最小再現が一致するため、原因は確定。別途CPU profileを取得したが、この環境のGo toolchainに `pprof` toolがなくsymbol解析は未実施。profileによる関数割合は主張しない。直接のgrow時間と最小実験のprocess CPUで判断した。

### 調査結果と範囲

- 同期timeoutやMariaDB shutdownが約5秒regressionを作っている証拠はない。既知の合法なInnoDB startup tailは変更せず、再調査していない。
- 修正候補はgeneric MemFSの拡張allocationを償却すること。ただしlogical sizeとcapacity、zero-filled holes、truncate/regrow、append/offset、prepared mapping ownership、child isolationを保つ必要がある。**今回その修正は実装していない。**
- 2回ともSnapshotとFork→COUNT成功。調査用patchとevidenceだけを保存し、production/runtime pathsは変更なし。広いORM/regression suiteやcandidate benchmarkは再実行していない。
- [counter evidence](v04-snapshot-attribution.json) と [診断再現手順](spikes/generated-go-integration/snapshot-audit.md) を参照。Snapshot性能blockerは原因判明、未修正。release readinessは引き続き **NOT READY — BLOCKERS REMAIN**。
