# Use-case / isolation research discovery

調査対象: current main `c8bd25a56e9d5221abaf40b2c98102bd60c217ae`。2026-10-07 にコード・既存 compact reports・指定された公式文書を読み取り。runtime tests、benchmarks、production/docs 編集は実施していない。以下は discovery と判断材料であり、製品方針の採択ではない。

## 証拠の読み方

- **実証**: repository の実行可能な consumer acceptance と、その既存公開結果がある。新規 consumer 需要とは区別する。
- **機構実証**: synthetic workload / lifecycle acceptance で機構は確認済み。実アプリ需要・性能一般化は未実証。
- **妥当な用途候補**: SQL/connection/isolation 特性や他製品の実例からの推論。mariamem の consumer compatibility / 実需の証拠ではない。
- **API自己確認**: 既存 API を直接 exercise する例・acceptance。存在や動作の証拠であって、それを残す product requirement ではない。

利用者は現状 maintainer 一人という会話の証拠がある。audit中の追加回答では、path writes / Destination、Snapshot.open、class/session mutable sharing のどれにも意図的な実務依存はない。conceptとともにAPI designを取り込んだとのこと。従って既存acceptanceはコードbehaviorのみでuser demandではない。read/import境界を残すという以前の明示選好は判断inputだが、実需の証拠に格上げしない。

## 代表12用途の matrix

共通原則: 各テスト内部での複数接続・commit・rollback は本物。cleanup のために commit を偽装しない。baseline を共有しても mutable child を test 間共有する必要はない。通常の cleanup は pool/client を閉じて database を破棄、template はその所有 scope の終わりに Close。

| # / 用途・証拠 | baseline / 作成者 | 共有してよい / 隔離する state | cleanup / real commit | Fresh / prepared 再利用 | filesystem artifact / 再現性 |
|---|---|---|---|---|---|
| 1 軽量CRUD / 実証 | 空DB＋小schema・必要最小data / test code | setup code / DB・schema・session・test mutations | test終了でDB破棄 / Yes | Fresh十分なことが多い。安いsetupにtemplateを強制しない | 不要 / schemaとfixture code |
| 2 migration-heavy / 機構のみ | application migrations / test suite setup | 完了したschema baseline / 各testのDDL・data | testでchild破棄、setup scopeでtemplate破棄 / Yes | 重いsetupなら再利用有用。現報告はone CREATE TABLEで重いmigrationを実測していない | 不要 / migration history・revision・実行順 |
| 3 realistic business fixtures / 小ORM実証・大規模候補 | users/address等factory/seed / setup code | immutable seeded baseline / business mutations | test / Yes | 共通seed再利用。SQLAlchemy/GORMでは2モデルの小seed実証。実business suite一般化不可 | 不要 / factories、inputs、clock/random方針 |
| 4 application独自接続のAPI/HTTP / 用途候補 | migrated+seeded / suite setup | template / app全接続が使用するtest専用DB | app停止・poolClose後DB破棄 / Yes | Freshも可、重いbaselineはtemplate有用 | 不要 / setup code＋app config。本repo HTTP consumerは未確認。ORM自身のpool/複数connectionは実証 |
| 5 transaction/constraint / 実証 | schema＋参照row / test/setup | schema・seed baseline / transactions・locks・session state | test / commitとrollbackの効果を観測 | Freshとprepared双方実証 | 不要 / SQL/ORM操作。cleanup rollbackとbusiness rollbackを混同しない |
| 6 pytest-xdist/parallel / 実証＋spike機構実証 | workerごとにsetupしてtemplate / fixture code | worker lifetimeのbaseline / testごとのDB | test、worker/sessionのtemplate teardown / Yes | worker内再利用。cross-process artifact共有は必須ではない | 不要 / fixture code。installed-wheelの2workers loadscope acceptanceあり。Owned spike4hostworkersはxdist自体の実行ではない |
| 7 large prepared/dump-derived / synthetic大data実証、dump需要未実証 | deterministic generatorまたはsanitized dump / setup | prepared initial state / child data・growth | test+template scope / Yes | 重いloadの償却に有用。ただしquery scan費は残る | SQL/data入力fileは有用。prepared artifactは必須ではない / generatorまたはdump origin・sanitization・hash・migration |
| 8 common baseline read-heavy / 機構実証 | deterministic dataset / setup | immutable template / 各childのruntime/session、可能なwrite | test / normally Yes | 再利用可。大COUNTは反復でも約338–357msでquery費を消せない | 不要 / dataset recipe。read-only workloadを理由にmutable DB共有をdefault化しない |
| 9 write-heavy / isolation機構実証 | schema・seed / setup | initial template / INSERT/UPDATE/DELETE、schema、growth | test / Yes | Fresh可、template有用。各childが大きくdirty化すればmemory/resource gainは限定 | 不要 / workload code。spikeの8MiB growthは大量write一般性能証明ではない |
| 10 failed assertion debugging / cleanup実証、inspection未実証 | failing test途中のmutable state / test | 通常は共有なし / failure stateを次testへ漏らさない | failure時もDB破棄。診断保存が必要なら破棄前の明示処理 / Yes | Fresh/preparedどちらも可 | logは既存。失敗dataの後日inspection needsは別候補 / revision、fixture入力、操作、error、guest等。Snapshot作成はsourceを消費するので診断の透過性はない |
| 11 external fixed artifact/regression / API自己確認、実需未実証 | format/storage再現file / regression作者またはartifact producer | read-only入力 / import後child | import handle+testDB、外部入力fileは作者所有 / Yes | importは固定format/壊れたinput regressionで意味がある。普通のbusiness fixtureに必須ではない | 有用な場合あり / authoritative historical byte fixtureならorigin・期待behavior・hashを明示。derived cacheなら再生成recipe＋source/guest keyを明示 |
| 12 intentional shared mutable across tests / API自己確認、需要未実証 | class初回methodがschema作成 / preceding test | 現APIは同じmutable DBをclassで共有 / class外のみ | class teardown / Yes | TestSharedは同じDB継続が必要な例。単一scenario test内なら同目的をより明確に表現できる | 不要 / 順序と前提をcode化しないと単独実行・並列・rerunが不安定 |

## 重要な現在の lifecycle

`Snapshot` は copy-live ではない。正常作成は source database を消費して閉じる。query/handshake/session cleanup が busy のときは拒否。transaction は明示rollback以外で拒否し、拒否はsourceを保持する。poolを閉じ、`wait_disconnected()` 後に作るのがnormal setup。従って reusable baseline の準備は「migration/fixtureをcommit→setup client/poolを閉じる→Snapshotにhandoff」と説明する必要がある。snapshot前後に元Databaseが共存する図は誤解を作る。

詳細な actual behavior: `tests/snapshots.py:79`以降の admission拒否、`127` rollback snapshotでsourceTCP閉鎖、`144` session variables/temp tablesが復元されない、`151` sibling commit隔離、`156` modified child→新Snapshot。`mariamem.go:10` package契約、`snapshot.go:30` context/default timeout説明。

## mutable class helper を KEEP する最も強いケース / REMOVE する最も強いケース

**KEEP側**: 明示的に一連の長いworkflowの進行stateを検査する複数methodなら同じDBが便利。各stepごとに高価なserver/libraryを再作成しなくてよい。既存 installed consumer acceptance は実際にclassに残るschemaを次methodで読むため、除去はこの契約・testを変える。frameworkがユーザー所有のclass/session fixtureを完全禁止する必要もない。

**ただし需要の限界**: 発見したのはAPI exercise `TestShared`だけ。実business consumerがこのhelperを要求した証拠はない。速度のためにbaseline setupをclassでreuseすることとは別問題。順次workflowは一つのtest内で同じmutable Databaseを使えばcore instance契約のまま表現できる。

**REMOVE側**: builtin `mariamem_class_fork`は前testのmutationを次testへ引き継ぐ。test名の単独実行・順序変更・失敗後rerunを弱める。function scoped `mariamem_class_connection_info`は接続切断を待つだけでdata/schemaをresetしない。名称が「classでsetup once」やDjango setUpTestData風の独立性を想像させる。用意したbaselineを各testでForkする機構は既にあり、shared mutable helperをcoreにする理由は弱い。

根拠: `python/mariamem/pytest_plugin.py:1` はpgmem-inspiredと明示、`36–45`はclassDB共有とwait-only、`docs/python.md:95`はshared mutationsを明示、`tests/consumer/test_database.py:74–79`は順序依存のschema継承。acceptanceが通ることは独立性を持つことと同義ではない。

## 公式reference再確認（2026-10-07）

指定URLを実際に読み直した。以下は約50–90words/page以下のparaphrase。framework機能はmariamem採択要件でも、mariamem consumer compatibilityの証明でもない。

| Framework | 公式で確認したbehavior | mariamemへの判断材料 |
|---|---|---|
| Django | TestCaseはclassと各testでnested atomic。setUpTestDataはclass baselineを一度作り、各testはrollbackで独立。TransactionTestCaseはtruncateでresetし、本物のcommit/rollbackが観測可能 | expensive baseline reuseとper-test isolationは別軸。test全体を外側transactionで包むと観測できないbehaviorがある。[Testing tools](https://docs.djangoproject.com/en/6.0/topics/testing/tools/#testcase) |
| Django keepdb | test database作成・削除をrun間で省き、migrationsを適用する。各testのcleanup policyを無効化する指定ではない | persistenceはsetup reuseであり任意mutation継承と同じではない。[Overview](https://docs.djangoproject.com/en/6.0/topics/testing/overview/#the-test-database) |
| Rails | fixture読み込みと通常のtest transaction rollback。parallel transaction時にwrapperを外す場合、data cleanupはユーザー責任。parallel processごとのDB/schemaも用意する | builtin unsafe sharingよりindependenceのためsetup再利用。[Testing Rails Applications](https://guides.rubyonrails.org/testing.html#transactions) |
| AdonisJS | migrate/seedをglobal setupで行い、各testでglobal transaction rollbackまたはtruncate | 高価なsetup共有をmutable mutation共有と混同しない。[Resetting state](https://docs.adonisjs.com/guides/testing/resetting-state-between-tests) |
| Laravel | RefreshDatabaseはschemaが最新なら再migrationせずtest transaction。非使用testが書いたrowは残り得る。Migrations/Truncationのfull resetは別 | cleanup境界を明示する価値。[Database Testing](https://laravel.com/framework/docs/database-testing)（読み取り時13.xへ解決） |
| Spring Boot | RANDOM_PORT/DEFINED_PORTのreal HTTPはclientとserverが別thread/transaction。test側@Transactionalではserver側transactionはrollbackされない | appをwhole isolated DBへ接続しcommitを許して破棄する用途を具体的に支持。ただしmariamem HTTP consumerは未実証。[Boot testing](https://docs.spring.io/spring-boot/3.5/reference/testing/spring-boot-applications.html) |
| Spring Context | 同config ApplicationContextのcacheはprocess内static。separate processではreuseできず、corrupted contextはDirtiesContextで除去 | runtime/serviceのreuseはDB data cleanup保証ではない。[Context Caching](https://docs.spring.io/spring-framework/reference/testing/testcontext-framework/ctx-management/caching.html) |
| Quarkus | @Transactional testは変更がpersistent、@TestTransactionはmethod終了でrollback。DB Dev Servicesは通常suite内reuse。cross-run container reuseはschema/data継承も伴うと警告し、不要ならORM/migration処理を推奨 | reusable serviceと独立test stateは別契約。[Application testing](https://quarkus.io/guides/getting-started-testing/#tests-and-transactions), [DB Dev Services](https://quarkus.io/guides/databases-dev-services/#reusing-dev-services) |

## Repeatability: fileが悪いわけではない

**test源泉としてのopaque prepared file**: `Snapshot.open('./mystery-state')`だけではschema/dataの意味・作成recipeが分からない。guest exact identityを必要とするphysical stateはupgradeのたびに解釈・再生成可能性も問われる。

**derived cache/artifact**: versioned migration/fixture/dumpから再生成でき、source/input/guest identityによりkey付けされ、deleteすればcache missとして作り直す。削除可能なためsource of truthを奪わない。将来需要はあり得るがcross-job cacheの実ユーザー・cache invalidation運用は未確認。通常Snapshotのpath writeを正当化する唯一の根拠にしない。

**historical bytes themselves are test input**: corruption/truncation/version mismatch等のstorage regressionは、old/invalid bytesを保存すること自体に意味がある。全てのfileを現sourceで再生成できるという条件は、このregression用途には過剰。かわりにorigin、hash、format、期待する拒否/成功を説明する。public prepared importerが必要かprivate storage regression toolingで足りるかは別判断。

**SQL/dump/data fixture**: migrationから独立したdata入力は正当。origin/licensing/sanitization/seed等を管理すればfixture codeと同等に理解可能。physical Snapshot import機能がなくても通常SQL接続でloadできる。この点は「path writeを除去すると大data fixture不可能」との推論を否定する。

**readerがあるからwriterを要求しない**: advanced external importerを維持する場合でも、normal Snapshotにexport producerを新設・温存してreaderを正当化しない。外部compatible artifactの現実の供給元・用途が未実証なら、その事実とguest/format互換範囲を明記してimportの必要性自体もchallengeする。read/importを残したいという選好とcore capabilityであるという結論は別。

## Code / evidence anchors

- `tests/consumer/test_database.py:17` default lifecycle、`32` temporary Snapshot sibling isolation、`49` explicit persistence API exercise、`59` per-function real transaction、`74` class mutation/schema sharing。
- `tests/verify_alpha.py:85` installed-wheel real xdist `-n 2 --dist=loadscope`; `87` migration override/seed生成、後半に意図的assertion/fixture failure cleanup。
- `docs/verification.md:34` historical installed consumer two-worker 7 tests PASS。現current source acceptance scriptとhistorical resultの区別を維持。
- `tests/consumer/test_sqlalchemy_dogfood.py:123–165` prepared session template/function child、`190–232` commit/no cleanup SQL→nextDB clean・business rollback、`234` constraints、`264` pool/session、`293` idle pooled socket Close。
- `tests/consumer/gorm/dogfood_test.go:94` AutoMigrate+seed、`157` template capture、`222` commit/next-test isolation。
- `docs/sqlalchemy-dogfood.md:57` このORM suite自体はxdistではない。`docs/project-status.md`はSQLAlchemy44/44 GORM32/32の既存acceptanceを記録し、Django/Alembicはfuture workload breadthとする。
- `benchmarks/practical-suite-comparison.md:12–31` synthetic scope、fresh/prepared/schema-reset契約、rollback非同値。`134` complex migrationsへの一般化禁止。
- `benchmarks/v043-characterization.md:23–43` deterministic minimal/10/100MiB、repeated COUNTとFresh対照、cold full scanとSnapshot異機構。
- OwnedPrepared evidenceは親auditが既存branch/CI packetを参照してfan-inする。本discoveryは再実験・production化を行わない。

## 収束前に明示する不確実性

1. 「migration-heavy/business/API HTTP/dump」にはstrong product fitがあり得るが、現在の実consumer幅はSQLAlchemy/GORMの小seedまで。契約を用途に合わせてもcompatibilityの約束を増やさない。
2. `Snapshot.open`とpath-writeのexisting acceptanceは能力の確認。cache、CI artifact reuse、dump cache、failure inspectionの実user workflowは未発見。
3. freshかpreparedかはsetup費とchild数依存。今回のauditでbenchmark crossoverを推定・再測定しない。
4. child個別DBはそのDB外のapp caches、files、queues、clock、other servicesをisolateしない。DB isolationとtest全体のisolationを同一視しない。
5. database Closeとdriver/poolCloseの所有責任は別。API/HTTP testではapp background workを停止してからdisposalする必要がある。非協調hard failureの強制回収は未保証。
