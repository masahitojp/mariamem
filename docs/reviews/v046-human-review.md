# v0.4.6 — Product Usability & Validation / Human Review

## Human decision（承認済み）

POはGo LoadSnapshot、Go/Python guide、Go 1.27.x互換性、型・Product Validation結果、
既知の制約とv0.6.0への積み残しをすべて承認した。追加承認待ちはない。
統合準備を進めるがmainへの統合・version更新・tag・publishは別工程。
Go toolchain性能調査は独立した測定branch/reportで管理し、この承認を再審議しない。

## 推薦

Go `LoadSnapshot` と利用ガイドの整備を採用候補とする。Go最低版、mysqlドライバー、
生成コード・MariaDB guest・mmap・Snapshot形式は変更しない。mainへの統合・リリースは未実施。
基準mainは `0fef33c752053d3bd1e180f9e46f4a301cfcd5eb`、実装branchは
`experiment/v046-usability`。これは開発候補の受入結果であり、最終公開成果物の認定ではない。

速度差は利用価値の根拠として扱う。軽いテストではFresh、準備が重いテストではSnapshot/Fork、
共有DBではリセット責任と引き換えに短い実行時間、という選択を支える。
MariaDBバージョン・設定・分離モデルが違う比較からエンジン自体の速度優劣は導かない。

## 1. Ubuntu Go 1.27.2

Ubuntu 24.04 linux/amd64で `GOTOOLCHAIN=local`、実際のcompilerは
`go version go1.27.2 linux/amd64`。外部module（replaceなし）のimport/build、
普通のアプリのbuild/run、SQL、Snapshot/Fork、新LoadSnapshot、複数接続、
commit/rollback、繰り返しClose、失敗時cleanupに成功。FD 13→13、goroutine 2→2、
一時ディレクトリの残留0。

Docker Desktop/Rosettaによるarm64 Mac上のx86_64実行であり、cross-compileではない。
**native Ubuntu runnerでの最終成果物認定を代替しない。** 私有module proxyのv0.4.5表記は
開発ソースのfixtureであり、公開v0.4.5 tagの検証ではない。
macOS Go 1.26.8/1.27.0/1.27.1/1.27.2の完了済みconsumer結果は受容し再調査しなかった。
新APIは別途macOS Go 1.26.8と1.27.1で確認した。

## 2. Go LoadSnapshot

`LoadSnapshot(ctx, path, opts) (*Snapshot, error)` を追加。
既存 `internal/snapshot.Import` による完全検証・コピー・所有FDの確立を再利用し、
MariaDBを起動せずSnapshotを取得する。公開wrapperは31行、生成/runtime変更は0。
optionsは既存defaults、legacy/platform拒否、importエラーは既存HostError契約を使う。

import後の元ファイル編集/削除に依存しない。Closeは所有FDを解放し、明示的永続成果物を
削除しない。Forkは独立した可変DB。親Close後も既存childは利用可能。
ctxはimport前後で確認し、完了直後のcancel時には取得backingをCloseする。
既存のcopy/hash自体を途中中断する新機構は追加していない。

検証：正常import、defaults、不正manifest/guest/content、欠損、cancel、invalid options、
legacy拒否、所有FD解放、反復Close、Close後Fork拒否、永続path削除後の利用。
実DBではPersist→元DB/保存Snapshot Close→Load→元path削除→二つFork→親Close→
commit/rollback→child間非干渉まで通過した。

## 3. Go/Pythonシナリオ

| シナリオ | Go | Python |
| --- | --- | --- |
| Fresh→SQL→Close | PASS | PASS |
| Prepare→Snapshot→Fork→Test→Close | PASS | PASS |
| Persist→Load→Fork→Test→Close | PASS（新API） | PASS（既存API） |
| child変更→新Snapshot→Fork | PASS | PASS |
| 複数接続・commit/rollback | PASS | PASS |
| 親Close・child独立・failure cleanup | PASS | PASS |

GoのFocused integrationとPython26 testsで確認。構文は異なるが、この製品契約で
重大な機能差は見つからなかった。Pythonは3.14での限定受入であり全Python版認定ではない。

## 4. ドキュメント

READMEは共通のDisposable DB説明と両言語Fresh例、Go guideはPython知識不要の
Snapshot/Fork・永続化・Load・cleanup、Python guideはpytest固有説明を維持。
永続化は高度な任意機能。公開v0.4.5と新API開発候補を区別した。
README/言語guideのコードを実APIで実行し、Goは外部proxy moduleを利用した。
Go 1.27.x一律unsupportedという現行指示を削除し、歴史的release reportには更新注記を付した。

## 5. 型互換性

INT/BIGINT unsigned最大値、FLOAT/DOUBLE、DECIMAL、DATE/DATETIME/TIMESTAMP、
日本語VARCHAR/TEXT、BLOB/BINARY/BIT、NULLをGo/Pythonで往復。
native MariaDB 12.3.3との同じdriver内比較では、観測値と取得したcolumn metadataが一致した。
Goのdefault parseTime=falseでは日時はbytes、Pythonではdate/datetime、DECIMALは
Go bytes/Python Decimalというdriver固有表現を保持する。
全MySQL型/metadata互換性を保証する結果ではない。

## 6. Product Validation

詳細条件・raw JSON・CPU/resource境界は
[測定報告](../../benchmarks/v046-product-validation.md)と
[compact evidence](../../benchmarks/v046-usability-evidence/README.md)。
各suiteは4テスト、Forkには一度のPrepare+Snapshot費用を含む。秒、通常3試行中央値。

| workload | Go Fresh | Go Fork | Python Fresh | Python Fork | Python Testcontainers fresh | Python shared+schema reset |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| light | 0.393 | 0.962 | 0.684 | 1.305 | 22.410 | 7.052 |
| 10 MiB / 8 tables / serial | 3.491 | 2.115 | 4.273 | 2.373 | 24.309 | 9.701 |
| 同fixture / 4並列 | 2.029 | 2.657 | 2.070 | 1.719 | 9.741 | 7.515 |
| 100 MiB / serial（1試行） | 30.198 | 11.826 | 33.476 | 13.001 | 39.654 | 15.902 |

10 MiB serialでは準備再利用でGo約39%、Python約44%短縮。100 MiBでは約61%短縮だが
1試行の探索結果。軽い準備ではSnapshot費用を回収できずFreshが短い。
Go並列ではForkが中央値で遅く、ばらつきも大きい。万能なFork優位は示していない。

nativeは12.3.3、embeddedは13.1。InnoDB poolは128 MiB対16 MiB、Docker VM、
ファイル/永続性設定も違う。Testcontainersは毎回独立server、sharedは一つのserverで
schema作成/dropを繰り返す。sharedのstartupを除いた10 MiB suite残りは約1.866秒。
Python Forkの2.373秒との差は、独立DBを毎回捨てる価値を判断する材料になるが、
sharedにはリセット・共有server状態・失敗後始末の責任が残る。
性能だけで異なる分離契約を等価とは扱わない。

## 7. 限界 / v0.6.0 Discovery

合成fixtureと限定trialによる結果。実アプリmigration/ORM、collation/timezone/fractional time、
JSON/spatial/型の境界値・metadata breadth、first-use/build費用、他のnative設定は未完了。
次のDiscoveryで実consumerを増やす。migration相当のschema作成は含むが、
Django/Alembicの実migration acceptanceではない。
Snapshot性能改善、runtime/guest更新、dependency更新、追加APIはこのbranchに含めない。

## 8. release readiness / Human decision

開発候補としてHuman Review可能。推奨判断は「Go LoadSnapshot・ガイド・検証資産を
最小変更として統合へ進める」。main merge、version bump、release notes、native macOS/Ubuntu
最終artifact qualification、公開tag consumer確認、Release CIは別のrelease準備/承認工程。
現在のGo最低版1.26.0 / mysql v1.9.3を維持する。

実行した検証：root/snapshot unit、focused SQL/session/Snapshot/Fork integration、
Owned snapshotのrace、Go vet、Python scenarios、両言語doc例、source/license oracle16件、
canonical docs/public-boundary checks。doc/Python unit組は33 passed +6 subtests。
生成/runtime入力が変わらないため、full guest/race/release qualificationは繰り返していない。

実験完了にはcompact証拠のcommit/pushとworktree/cache/tempの廃棄を含む。
歴史的mac互換性証拠とGit historyを保持し、生成環境を成果物として保持しない。
