# v0.4 generated-Go candidate — integration gate

## 結果

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
