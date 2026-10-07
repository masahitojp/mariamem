## Recommended mariamem product model

mariamem は、テストごとに実際の MariaDB を所有し、使い終わったら捨てるための道具。
各 DB は可変で、アプリ自身の接続と本物の commit / rollback を使える。
軽い準備なら、テストごとに新しい DB を作ればよい。
高価な migration / fixture は一度準備し、不変の初期状態として共有できる。
共有するのは初期状態であり、あるテストの変更を次のテストへ渡すものではない。
初期状態から作る DB は毎回同じ状態で始まり、それぞれ独立して変更できる。
初期状態への変換には準備用 DB の利用を終える必要があり、成功するとその DB は閉じる。
接続・DB・初期状態は、それぞれの所有 scope の終わりに閉じる。
外部の初期状態を読む機能は明示的な advanced import とし、通常の保存・再開とは分ける。
失敗時の診断は別の責任とし、テスト状態を次のテストに残す手段にしない。

監査 baseline は current main `c8bd25a56e9d5221abaf40b2c98102bd60c217ae`。remote main も同 SHA。v0.4.3 は公開済みという maintainer の確認を現状の前提とする。既存 API は要件ではなく実装証拠。maintainer は今回、path writes / Destination、Snapshot.open、class/session mutable sharing に意図的な実務依存はなく、概念と API を一緒に取り込んだと明言した。以下は **提案であり採択・実装ではない**。

## Decision 1 — Core use cases

- **Recommendation:** 軽量 CRUD・SQL/transaction/constraint、アプリ自身が複数接続で commit するテスト、準備を共有して各テストを独立させる用途を中心にする。Fresh と prepared reuse のどちらも core workflow。HTTP、重い migration、dump は用途候補で、未実証の framework 互換性まで約束しない。
- **Strongest evidence:** SQLAlchemy/GORM は commit 後に cleanup SQL を行わず次 DB が初期状態に戻ることを既存 acceptance で確認。installed-wheel の実 pytest-xdist acceptance もある。Spring は real HTTP の server transaction が test transaction の rollback 外になると明示する。[Spring Boot testing](https://docs.spring.io/spring-boot/3.5/reference/testing/spring-boot-applications.html)
- **Strongest counterargument:** 現在の実 consumer は小さな ORM/SQL workload が中心。DB ごとの作成・メモリ費用が重く、軽い用途では既存 rollback 方式の方が安い可能性もある。
- **Concrete downside:** migration-heavy / HTTP を中心の用途候補に含めても、実アプリでの速度・互換性を保証するには後の workload evidence が必要。
- **Human decision:** 「本物の commit を許すテスト単位の DB 破棄」と「任意の baseline 再利用」を中心用途として採用するか、Yes / No？

## Decision 2 — Core concepts

- **Recommendation:** 必須概念は **可変で使い捨ての DB** と **不変で lifetime-bound の prepared baseline** の二つ。外部 import は advanced、診断は既存 logs を KEEP して新 artifact API は DEFER。baseline の物理保存先、runtime clone、cache manager はユーザーの必須概念にしない。
- **Strongest evidence:** 一つのテスト内部の stateful workflow と、別テストの初期状態はこの二概念で表せる。Django の class setup reuse も per-test isolation と両立する。[Django TestCase](https://docs.djangoproject.com/en/6.0/topics/testing/tools/#testcase)
- **Strongest counterargument:** cross-job artifact cache と失敗後の data inspection には別の永続 artifact 契約が便利。ただし mariamem の実利用は未発見。
- **Concrete downside:** Snapshot 作成成功は source を消費する。live DB の checkpoint としては使えず、failure data を後から見る機能も今回追加しない。
- **Human decision:** 二つの core 概念に絞り、import / diagnostics を通常 lifecycle の外側に置くか、Yes / No？

## Decision 3 — Snapshot/Fork naming

- **Recommendation:** **KEEP**。Snapshot＝不変の初期状態、Fork＝そこから新しい可変 DB を開始、と最初に定義する。Fresh は Start の説明語であり、新しい public symbol を作らない。
- **Strongest evidence:** 正しい lifecycle・初期状態・独立性は名前を変えずに説明できる。現在の混乱には path-save API と class-shared state が具体的に関与し、rename だけでは解消しない。
- **Strongest counterargument:** Template / Spawn は役割をより直接表す。Snapshot は非破壊コピーや checkpoint、Fork は Unix fork を連想させる。
- **Concrete downside:** 名前を保持する限り「Snapshot は source を閉じる」「Fork は新しい DB を起動する」を usage の近くで明記する必要がある。
- **Human decision:** 今回は Snapshot/Fork を保持し、定義と API で誤解を解消するか、Yes / No？

## Decision 4 — Go/Python/pytest API changes

| Material item | Recommendation | Reason / proposed boundary |
|---|---|---|
| Start/Database、Snapshot→Fork、function-scoped child fixtures | **KEEP / ALIGN** | 同じ logical lifecycle と ownership。Snapshot は lifetime-bound template に ALIGN。 |
| Python `db.snapshot(destination)`、Go `SnapshotOptions.Destination` | **REMOVE** | 通常 snapshot を arbitrary-path save にしない。v0.4.4 の template alignment に含める候補。 |
| Python `Snapshot.open(path)` | **KEEP, ADVANCED / ALIGN** | 明示 read/import のみ。一度成功したら元 path から独立する owned template。実需未確認の事実は残す。 |
| `Snapshot(path)`、`Database/start(snapshot=path or handle)` | **REMOVE as public entrances** | import は open、child 作成は fork に集約。closed handle を path として復活させる入口を排除。内部 handoff は public API と別。 |
| Go `Path()`、Python `path` / `manifest` / `validate()` | **INTERNALIZE** | 普通の利用で storage/manifest を理解させず、mutable path を template identity にしない。diagnostic metadata を出す必要性は別判断。 |
| `mariamem_class_fork` / `mariamem_class_connection_info` | **REMOVE** | class 内で同じ mutable DB を持ち越す builtin helper。class baseline が必要なら baseline の scope を変え、child は function のまま。 |
| `mariamem_server` | **KEEP / ALIGN** | baseline 準備専用の mutable builder。普通の test DB として session 共有する説明はしない。baseline 作成後は consumed。 |

- **Strongest evidence:** class fixture は実際に同じ DB を共有し、consumer `TestShared` が前 method の CREATE TABLE を次 method で読む。Python の constructor restore は closed persistent Snapshot の path を開き直せる。maintainer に意図的依存はない。
- **Strongest counterargument:** path-save、generic restore constructor、複数 method の一連 scenario は便利。reader だけ残すと、新 artifact の public producer がなくなる。実需要のない exact-guest physical artifact は guest upgrade で使えなくなり得る。open の KEEP は二つの core 概念から必須ではなく、以前の明示 read/import 選好による advanced 例外。
- **Concrete downside:** 対応する既存 API 自己確認テストと examples を変更する必要がある。import は既存 compatible artifacts の advanced 入力であり、新 cache/export 能力を約束しない。Go import の新 public API は需要未実証なので追加を DEFER。全 API 名・error 型・timeout default の統一は今回に詰め込まない。
- **Human decision:** 上表の KEEP/REMOVE/ALIGN を v0.4.4 の最小 public contract とするか、Yes / No？

## Decision 5 — OwnedPrepared/integrity direction

- **Recommendation:** **contract fit は Yes、productionization 候補として GO**。採用するのは「取得時完全検証→同じ backing を所有→independent children」という契約。spike history を丸ごと merge せず、承認後に current main 上の最小変更として扱う。
- **Strongest evidence:** exact spike `730b64db7059d0374e2e00680416de77cdb346eb` の両 OS CI で import 拒否、元 path 変更からの独立、sibling/order/generations/growth/parallel/Close/failure が PASS。ready p50 は Go 54–74%、Python 72–83%短縮。準備込み Python16-child suite は39–62%短縮。[OwnedPrepared CI](https://github.com/masahitojp/mariamem/actions/runs/37541652530)
- **Strongest counterargument:** 約800行の production-facing acquisition/handoff/lifetime code と一 file 一 FD の保持が必要。後発媒体破損を毎 Fork で検出する old check は戻らない。
- **Concrete downside:** 11-file fixture では11 FD/Snapshot。多数の table/同時 Snapshot の FD budget と回収失敗は正式実装の受入項目。重い100 MiB Go suite全体の改善は8–20%で、SQL scanは残る。spike の CI を別の main-based production candidate の exact-source acceptance として再利用しない。
- **Human decision:** 固定 integrity 契約を採択し、OwnedPrepared の最小 productionization を v0.4.4 の候補 scope に入れるか、Yes / No？

## Decision 6 — Documentation structure

- **Recommendation:** README/Go/Python guides＝WHAT/WHY/guarantees、architecture＝現在 HOW、少数の `docs/decisions/`＝今後も拘束する WHY、reports/release notes＝source/date 限定の history。project-status は現在の release・制約・選択済み方向に絞る。既存文書はまだ書き換えない。
- **Strongest evidence:** 90 Markdown を分類。current user links から v0.4.0 report の「その変更は CoW を導入しない」へ進み、現在の MAP_PRIVATE と突き合わせる必要がある。candidate/pending publication と旧 cleanup 方針への現行リンクも残る。
- **Strongest counterargument:** 同じ制約を WHAT/HOW/WHY に分割すると重複・同期コストが増える。少数の利用者には一枚の文書が便利。
- **Concrete downside:** canonical owner と cross-link を決めない単なるファイル分割は逆効果。過去測定を current に書き換えず、current entry point から外して source/status を明示する必要がある。
- **Human decision:** この責任分担を採用し、承認後は current contract/navigation を先に整理するか、Yes / No？

以下の appendices は現行挙動と提案を区別する。**今回変更したのは新規 audit report/evidence のみ**。production code、既存 docs、OwnedPrepared branch、version、main、release は変更しない。


## Appendix 1 — Full current public API inventory


All handles are explicitly closed by caller; no process-global GC/finalizer cleanup guarantee. DB mutable state is isolated per instance; Snapshot logical state is intended to be baseline-only but its external backing can be modified. Default scope is caller lifetime; Go has no test fixture scopes.

| Public syntax / reference | Lifecycle, ownership, state, cleanup | Python equivalent | Documented intent vs actual code | Demonstrated use / maintainer reliance |
|---|---|---|---|---|
| `Start(ctx, Options{}) (*Database,error)`; [mariamem.go:82](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/mariamem.go#L82) | Creates mutable DB + temp root; context governs startup only, successful DB outlives context; caller Close | `start()` / `Database()` | Documentation agrees; real MariaDB in caller process, local TCP listener | CRUD/protocol/ORM tests ([tests/gointegration/lifecycle_test.go:52](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/tests/gointegration/lifecycle_test.go#L52)); core desired |
| `Options{StartupTimeout}`; [mariamem.go:39](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/mariamem.go#L39) | Zero→120s; negative reject; bounds host/guest startup after setup; no lifetime timer | `startup_timeout=120` | Go zero default vs Python zero invalid; validation artifact/setup work occurs before startup timeout | Lifecycle/failure tests; U |
| `Options{ShutdownTimeout}`; same | Zero→30s; negative reject; Close creates independent background timeout, cleanup may exceed it | `shutdown_timeout=30` | Cooperative reclamation only, no hard failure guarantee | Lifecycle/timeout tests; U |
| `Options{QueryTimeout}`; same | Zero→30s; negative reject; interrupted active SQL invalidates entire DB | `query_timeout=30` | Driver SQL errors are separate from fatal host timeout | [mariamem_test.go:304](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/mariamem_test.go#L304) fake-backend invalidation and [tests/test_python_timeout.py:26](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/tests/test_python_timeout.py#L26) retained opt-in runtime diagnostic; desired constraint, exact value U |
| `Options{NativeDir}`; [mariamem.go:40](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/mariamem.go#L40) | Deprecated compatibility field; nonempty rejects startup | `runtime/module/wasmer_dir` rejected parameters | No working alternate runtime; retain/reject is a migration surface, not a runtime capability | [mariamem_test.go:521](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/mariamem_test.go#L521); explicit legacy retirement, field reliance U |
| `Database`; [mariamem.go:68](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/mariamem.go#L68) | Construct via Start, do not copy; owns runtime, mutable DB and temp files | `Database` | Zero value cannot operate, Close safe | API tests; core desired |
| `db.Close() error`; [mariamem.go:173](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/mariamem.go#L173) | Mutex serializes lifecycle; marks closed, stops runtime, removes DB temp; repeated calls return stored cleanup result | `close()` / `with` | Normal idempotency promised; timeout does not force in-process reclaim | Cleanup/error/concurrent tests; core desired |
| `db.Closed() bool`; [mariamem.go:166](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/mariamem.go#L166) | True for closed/nil backend/failed runtime | `closed` | Availability diagnostic, not just explicit Close flag | [mariamem_test.go:304](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/mariamem_test.go#L304); U |
| `db.Err() error`; [mariamem.go:143](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/mariamem.go#L143) | Preserves invalidation cause; clean Close/successful Snapshot returns nil; runtime watcher closes unexpectedly exited DB | Python has no `err` equivalent; `status()`/HostError | Cause retained through error chain; ordinary SQL does not invalidate | timeout/default lifecycle tests; U |
| `db.ConnectionInfo() ConnectionInfo`; [connection.go:9](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/connection.go#L9) | Detached value copy, available after Close; endpoint unusable after disposal | `connection_info()` rejects after Close | **Current language mismatch**: Go permits retained metadata, Python errors | [mariamem_test.go:64](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/mariamem_test.go#L64), [tests/consumer/test_database.py:17](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/tests/consumer/test_database.py#L17); U |
| `ConnectionInfo{Host,Port,User,Password,Database}`; [connection.go:10](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/connection.go#L10) | `127.0.0.1`, ephemeral port, `root`, empty password, `test`; user can alter copy, not DB | dict with same five keys | Local testing endpoint; not production credential/security provisioning | Driver/ORM tests; core desired |
| `db.DSN() string`; [connection.go:20](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/connection.go#L20) | Metadata remains usable as text after Close; string for go-sql-driver/mysql with `interpolateParams=true` | None; caller builds driver-specific args | Text protocol interpolation; explicit prepared statements unsupported | Go/GORM dogfood; U |
| `db.WaitDisconnected(ctx) error`; [mariamem.go:203](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/mariamem.go#L203) | Poll 5ms until host active connections=0; no implicit timeout; rejects closed/unusable; caller closes pool first | `wait_disconnected(timeout=5)` | Convenience admission/cleanup barrier, not rollback/reset | Snapshot and reconnect tests; documented preferred snapshot workflow |
| `db.Logs() string`; [mariamem.go:232](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/mariamem.go#L232) | Retains last 16 KiB including after Close; copies to string, no user path | `logs`, optional `log_path` | Bounded guest diagnostics, separate from DB data export | failure diagnostics tests; U |
| `SnapshotOptions{Destination}`; [snapshot.go:14](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/snapshot.go#L14) | Empty→owned temp; explicit absolute path created exclusively; existing path rejects without overwrite/source consumption | `snapshot(destination=None)` | Both languages expose path write; **no Go arbitrary reopen API** | [tests/gointegration/lifecycle_test.go:222](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/tests/gointegration/lifecycle_test.go#L222); **confirmed no intentional reliance**, arbitrary write undesirable |
| `SnapshotOptions{Rollback bool}`; [snapshot.go:17](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/snapshot.go#L17) | False rejects open tx; true authorizes dropping unfinished tx during close/export | `rollback=False` | Not test-level isolation mode; controls snapshot acceptance only | [mariamem_test.go:153](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/mariamem_test.go#L153), [tests/snapshots.py:127](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/tests/snapshots.py#L127); U |
| `db.Snapshot(ctx, SnapshotOptions{})`; [snapshot.go:29](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/snapshot.go#L29) | Mutex holds; success consumes DB; host-accepted failure consumes DB; precondition failure leaves DB alive; complete export then validation | `db.snapshot()` | Cold files, not live runtime clone; no default Snapshot context deadline; copy/hash not cancellable | Fixture/SQLAlchemy baseline reuse; core desired |
| `Snapshot`; [snapshot.go:20](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/snapshot.go#L20) | Handle owns only empty-Destination temp root; explicit destination is externally lifetime-owned; no exported constructor | `Snapshot(path)` / `Snapshot.open(path)` | Logical reusable template, physical immutability not enforced; any external writer can change backing | Sibling tests; desired concept, present ownership not accepted future guarantee |
| `s.Path() string`; [snapshot.go:73](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/snapshot.go#L73) | Returns actual directory even after Close; normal temp disappears on Close; no mutation via handle itself | mutable `snapshot.path` attr | Public implementation/storage detail enables external edits; explicit path retained | Existing lifecycle/fixture checks depend on existence; maintainer relies on logical template, path need U |
| `s.Fork(ctx) (*Database,error)`; [snapshot.go:77](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/snapshot.go#L77) | Inherits all source options; concurrent startups permitted; RW read lock pins files through startup; Close waits admitted startups; created child independent | `s.fork(**options)` | Fork host verifies inventory/content every call then separately reopens/maps; no ready runtime cloning | Many integration/ORM workloads; core desired |
| `s.Close() error`; [snapshot.go:94](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/snapshot.go#L94) | Exclusive lock, idempotent stored result; owned temp deleted, explicit destination retained; later Fork rejects; already started child survives | `s.close()` / `with` | Go enforces Fork/Close startup pin; Python current code does not | [mariamem_test.go:362](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/mariamem_test.go#L362), runtime lifecycle tests; core desired |
| `ErrBusy`, `ErrTransactionActive`, `ErrClosed`, `ErrUnusable`; [errors.go:11](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/errors.go#L11) | `errors.Is`; busy/tx rejection does not consume DB; closed terminal; unusable retain cause | `Busy`, `TransactionActive`, generic HostError closed/unusable | Not all errors return a public sentinel (e.g destination); no error enum promised for all cases | API/lifecycle diagnostics tests; U |
| `HostError{Code,Stage,Closed,Err}` plus Error/Unwrap/Is; [errors.go:19](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/errors.go#L19) | Describes source consumed/unusable and failure boundary; joins cleanup cause; not an execution API | `HostError(code,stage,closed)` + Python cause | Some diagnostics still use historical `native_unavailable` category; ordinary SQL stays driver error | deterministic/root API tests; U |


### Python


| Public syntax / reference | Lifecycle, ownership, state, cleanup | Go equivalent | Documented intent vs actual code | Demonstrated use / maintainer reliance |
|---|---|---|---|---|
| `mariamem.start(**options)`; [python/mariamem/__init__.py:296](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/python/mariamem/__init__.py#L296) | Thin `Database(**options)` factory; starts mutable DB in dedicated packaged Go host; caller owns lifecycle | Start | No Fresh name; no shared daemon | Consumer CRUD/ORM; core desired |
| `Database(*,host_binary=None,runtime=None,module=None,log_path=None,wasmer_dir=None,query_timeout=30,startup_timeout=120,shutdown_timeout=30,snapshot=None)`; `__init__.py:33` | Constructor starts immediately; no idle/unstarted object; owns host process, reader thread, logfile and temp root | Database/Start/options | Python process boundary differs but same SQL/isolation concept | Lifecycle/consumer tests; core desired |
| `startup_timeout`, `query_timeout`, `shutdown_timeout`; `__init__.py:40` | Positive finite numeric seconds; zero/negative/inf/non-numeric reject; `bool` currently accepted because int subtype; startup wrapper wait adds15s; close control wait adds25s and exit wait5s | Go durations with zero default | Not whole-call wall-clock bounds: wheel resolve/hash precedes timer; Snapshot copy/hash outside guest deadline | Timeout diagnostics; exact numbers U |
| `host_binary=...`; `_artifacts.py:50` | Local executable path override; executable availability check; bypasses wheel platform/manifest/hash checks, host validates native platform on startup | No equivalent public Go executable selector | Documented developer override, not alternate supported runtime | [tests/test_python_diagnostics.py:166](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/tests/test_python_diagnostics.py#L166), dev benches; U |
| `runtime=...`, `module=...`, `wasmer_dir=...`; `__init__.py:38`, `_artifacts.py:51` | Any non-None value rejects; even empty string provided is rejected; no active compatibility runtime | Go deprecated NativeDir (empty accepted) | Migration tombstones; no capability exists | diagnostic/retirement tests; explicitly retired |
| `log_path=...`, `db.log_path`; `__init__.py:67` | Caller path absolute; parent dirs created; file exclusive `xb`, existing file rejects; explicit path retained, default removed with temp | Logs only, no public Go path choice | Diagnostic-only path write, distinct from unwanted Snapshot state writes | diagnostics/consumer cleanup; U |
| `with db` / `__enter__/__exit__`; `__init__.py:287` | Context calls close on exit; enter only checks `_closed`, not live process poll | Go defer Close | No GC cleanup guarantee; already terminated host may enter until operation diagnoses | Core consumer workflow |
| `db.close()`; `__init__.py:199` | Lock serializes controls; requests close, waits, finally disposes; repeated closed returns None; may raise on first cleanup/error but no saved close result | Close() error | Idempotent resource cleanup, **no repeated identical error contract** like Go; Python terminate/kill fallback exists | Consumer failure/timeout tests; core desired |
| `db.closed`; `__init__.py:174` | `_closed` or host poll!=None; true host death does not alone release wrapper resources | Closed() | Docs explicitly require close/status cleanup; no async wrapper autoreap guarantee | Timeout consumer tests; U |
| `db.status()`; `__init__.py:163` | Control lock; returns raw reply dict incl `id,ok,state,active_connections,busy`; closed/unusable raises; closed HostError disposes | Err + Closed + WaitDisconnected, no raw status equivalent | Partly leaked private control envelope; documented failure inspection but fields not comprehensive user contract | `wait_disconnected`, timeout checks; U |
| `db.connection_info()`; `__init__.py:184` | Five-key dict copy; errors once disposed/host exits | ConnectionInfo | Unlike Go unavailable after Close | Consumer metadata tests; core desired |
| `db.wait_disconnected(timeout=5)`; `__init__.py:189` | Poll status every5ms; positive finite seconds; timeout only checked after status response so not strict wall-clock bound; no reset | WaitDisconnected(ctx) | Barrier ensures sessions gone, not previous data changes gone | Fixtures and ORM; preferred barrier |
| `db.logs`; `__init__.py:178` | Last16 Ki characters while live via path and after close via retained string; caller `log_path` file preserved | Logs() last16KiB | Byte/character difference; disk can grow while running even though exposed tail bounded | failure diagnostics tests; U |
| `db.id`; `__init__.py:104` | Random ready token per host DB; writable Python attr; no lifetime resource | None | Intended public DB identity in inline comment, not storage/source identity | Consumer teardown audit uses token; real need U |
| `db.capabilities`; `__init__.py:106` | Tuple strings status/close/text-query/reconnect/snapshot/fork from host; assignable attr | None | No documented stable negotiation policy; native maximum connections not copied into attr | [tests/snapshots.py:81](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/tests/snapshots.py#L81); current feature probe, U |
| `db.diagnostics`; `__init__.py:108` | Mutable dict host_pid/runtime_pid; implementation detail, not DB identity | None | Explicit inline comment diagnostic-only | Consumer process-reaping audit; U |
| `db.snapshot(destination=None,*,rollback=False,timeout=120)`; `__init__.py:216` | Temp default vs persistent explicit; exclusive destination; success/accepted fail consumes host; busy/tx/destination rejection leaves source alive; timeout bounds guest export, not copy/hash; inherits host/timeouts into new Snapshot | Snapshot(ctx, options) | Same logical concept but different timeout ergonomics; `rollback` must bool | SQLAlchemy/consumer/tests/snapshots; baseline desired; **confirmed no intentional reliance on destination**, arbitrary write undesirable |
| `Snapshot(path)`; `snapshot.py:35` | Public constructor identical boundary to open; absolute exposed path; validates path now but owns no external files | None | Constructor is not documented canonical entrance; preserves external path and mutable attr | Internal `open` delegation; intentional reliance U |
| `Snapshot.open(path)`; `snapshot.py:43` | Reads and hashes external files; **does not copy/take ownership**; close doesn't delete external path | No public OpenSnapshot | Doc says hash/build compatibility; code checks hash syntax only, actual guest compatibility later in Fork host | Persistence/corruption feature tests; **confirmed no intentional reliance**; read/import acceptable preference, not demonstrated demand |
| `s.validate()`; `snapshot.py:47` | Returns self after rehash; rejects closed; reloads `manifest`; checks root inventory, types, format1/memory, declared hashes | No public equivalent | Does not freeze backing or bind runtime identity; Python bool/float equality accepted for version/bytes unlike Go JSON integer decode | [tests/snapshots.py:225](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/tests/snapshots.py#L225); U |
| `s.path`; `snapshot.py:37` | Public writable Path to live root; can be assigned to another root; temp owned only for internally-created object | Path() immutable Go string | Exposes mutable path trust boundary | cleanup/import/persistence acceptance; arbitrary source input acceptable, exposed backing need U |
| `s.manifest`; `snapshot.py:65` | Public mutable dict after validate; entries/hash/guest metadata; mutation doesn't rewrite file, later validate reloads | No public manifest | Internal format leaks into SDK; no manifest caller mutability/compatibility promise documented | corruption tests manipulate on-disk manifest, attribute requirement U |
| `s.fork(**options)`; `snapshot.py:68` | Rejects `_closed`, options override inherited host/timeouts, `snapshot=self` wins; returned DB owns child process | Fork(ctx) inherits options, no overrides | **No lock pins Snapshot through startup**; constructor reopens same path for Python hash then Go host hashes again | concurrency/sibling/ORM tests; core desired |
| `Database(snapshot=s)` / `start(snapshot=s)`; `__init__.py:62` | **Reopens `s.path` as new Snapshot even if s is closed**; original handle lifetime/lock/manifest disregarded; explicit closed persistent handle still viable as path | None, only s.Fork | Hidden alternate entrance weakens handle semantics; not same as using owned immutable resource | Benchmarks/direct constructor restore; product need U |
| `Database(snapshot=path)` / `start(snapshot=path)`; same | Implicit path read/validate + host restore; no independent owned copy; callers need not use Snapshot.open | None | Duplicates explicit import boundary; guest mismatch rejected during host start | `tests/snapshots.py` start helper; intentional reliance U |
| `s.close()` / context; `snapshot.py:74` | `_closed=True` before temp cleanup; no close lock/error caching; temp removed, external destination retained; already-mapped children survive unlink | Snapshot.Close | Python concurrency guarantee weaker than Go; possible Fork/Close startup deletion race remains | Consumer persistence/default cleanup; core desired |
| `HostError(message,*,code=None,stage=None,closed=False)`; `__init__.py:17` | RuntimeError subclass; attributes diagnostic; cause often chained; SQL errors separate driver exceptions | HostError | Some closed operations only generic HostError no code/closed flag; snapshot validate can raise ValueError/OSError/JSONDecodeError | diagnostic tests; U |
| `Busy`, `TransactionActive`; `__init__.py:25` | HostError subclasses selected from rejected reply code; precondition does not consume DB | ErrBusy/ErrTransactionActive | No Closed/Unusable exception subclasses/sentinels | [tests/snapshots.py:73](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/tests/snapshots.py#L73); U |
| `mariamem.__version__`; `__init__.py:14` | String distribution version, not guest/prepared-state identity | Module/tag, no public Version constant | Packaging version independent of runtime guest hash | consumers/package tests; U |


### pytest


Scope follows pytest fixture instance scope **per worker**, not global across xdist workers. Each DB handle is mutable unless otherwise stated. There are no automatic transactions, rollbacks, table truncates or schema resets at test teardown.

| Fixture / code reference | Scope, source, actual cleanup / shared state | Go equivalent / documented intent | Demonstrated use; intentional reliance |
|---|---|---|---|
| `mariamem_options`; `pytest_plugin.py:7` | session; default `{}`, caller override Start options; dict itself mutable; no resources | Caller Options; docs/python.md:69 agrees | Consumer override/start tests; U |
| `mariamem_server`; `pytest_plugin.py:12` | session; one mutable DB per worker; context close session end; can carry state between tests if used directly; successful dependent snapshot consumes it | Manually-owned setup DB; docs says Template DB | Fixture setup override; **confirmed no intentional reliance on sharing mutable state across tests**; setup helper itself remains separately useful |
| `mariamem_snapshot`; `pytest_plugin.py:18` | session; waits disconnected then consumes server into default empty temp Snapshot; one template per worker; context close session end | Caller baseline Snapshot; docs agrees | Migration/seed override [tests/verify_alpha.py:89](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/tests/verify_alpha.py#L89); desired baseline sharing |
| `mariamem_fork`; `pytest_plugin.py:25` | function; independent child from same template; DB discarded function end, real commits persist within test | Manual `s.Fork()` + defer Close | Consumer parameterized test isolation; core desired |
| `mariamem_connection_info`; `pytest_plugin.py:31` | function; dict of function DB endpoint, no connection owned/closed by plugin | ConnectionInfo | Consumer PyMySQL tests; core desired |
| `mariamem_class_fork`; `pytest_plugin.py:36` | class; **one mutable DB reused by all methods**, no per-method reset; discard class end; outside class pytest class-scope behaves per test item | No special Go counterpart; docs/python.md:74,97 explicitly says shared mutations | [tests/consumer/test_database.py:74](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/tests/consumer/test_database.py#L74) test_create schema then test_reuse observes it: order-dependent feature coverage; **confirmed no intentional maintainer reliance** |
| `mariamem_class_connection_info`; `pytest_plugin.py:42` | function-scoped metadata for same class DB; calls wait_disconnected before returning; **does not reset data** and does not own driver's connections | None; docs describes same class DB | Same order-dependent test; barrier is session cleanup only; **confirmed no intentional maintainer reliance** |

Package extras: `[pytest]` installs pytest>=7 only; `[test]` installs pytest>=7, pytest-xdist>=3, PyMySQL>=1.1,<2 ([python/setup.cfg:16](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/python/setup.cfg#L16)). Driver connections, pools and app processes remain owned by the test/application. `pytest -n 2 --dist=loadscope` merely keeps class methods on a worker; it does not make shared-class tests order-independent. [tests/verify_alpha.py:84](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/tests/verify_alpha.py#L84) demonstrates actual consumer serial/xdist runs, migration baseline and assertion/setup-error cleanup (existing evidence, not rerun).



### Completeness notes

上表は23 Go rows、29 Python rows、7 pytest rows（struct fields/exception methodsをgroup化）。各rowにsyntax、lifecycle、ownership、mutablestate、cleanup、counterpart、documented intent/actualbehavior、既存用途、maintainer relianceを記録する。Go scopeはcaller lifetime、Python scopeはcaller/context lifetime、pytestは表記scopeをworker内で管理。意図的実利用未確認のUはunusedを意味しない。targetedpath/import/sharedmutableはmaintainerが明示的に依存なしと回答した。

core SQL/multiclient/cancel/capacity/packaging/CLI/environment/incidentalnamesはAppendix4補足表。GoにOpenSnapshot/Fresh/SQLhelper/poolfactory/MaxSessionsoptionはない。Pythonにもbuiltindumpreader/reset/auto-rollback/diagnosticdataexportはない。db.logs / log_pathは既存診断、Snapshot write廃止提案の対象外。

## Appendix 2 — Go/Python parity matrix

ここでの parity は同じ意味・所有・失敗境界であり、同じ spelling、同じ timeout default、同じ例外型を強制するものではない。

| Boundary | Current Go | Current Python / pytest | Product-contract proposal / scope |
|---|---|---|---|
| 新 DB / Fresh | Start(ctx, Options{}) | start()/Database() | CORE。空の可変 DB を所有、Fresh symbol は追加しない。 |
| 接続所有 | ConnectionInfo/DSN、callerがpoolを作る | connection_info dict、callerがdriver/poolを作る | KEEP。app/pool/SQL接続のcleanupはcaller責任。mariamemはORMやHTTPappを自動管理しない。 |
| Close | stored cleanup errorを繰り返し返す | 最初にerrorあり得る、次はNone | KEEP。資源回収はidempotent、同じerror形式までは統一不要。 |
| Close後metadata | ConnectionInfo/DSNは返る | connection_infoは拒否 | v0.4.4 docs only。metadataが返ってもlive endpointではないと明示。収束は実需次第。 |
| 不可用state | Closed/Err sentinel＋cause、watcher cleanup | closed/status HostError、明示closeでwrapper cleanup | KEEP logical contract。中断SQL後はDB全体を捨てる。typed API全面統一はDEFER。 |
| startup timeout | caller ctx＋StartupTimeout zero→120s | positive seconds120、wrapper余裕あり | KEEP idiom差。whole-call hard deadlineを保証しない。 |
| query/shutdown | zero→30s/30s | positive seconds30/30 | KEEP。ordinary SQL errorはDBを生かす。active SQL cancellation/disconnect/timeoutは全DB invalidation。 |
| Snapshot deadline | ctxそのまま、追加defaultなし | guest export timeout=120s | docs only。copy/hash/cleanupは全体deadline外。bounded abortの新機構を今追加しない。 |
| Snapshot success/failure | success/accepted failureでsource consumed | 同じ。ただしPythonのlocalvalidation/exception種類に差 | CORE contractは共通。busy/transaction/destination pre-rejectionはsource保持。将来destination public removal後も適切なprecondition失敗を維持。 |
| transaction handling | Rollback=false、trueは未完了tx廃棄を許可 | rollback=False、true同様 | ADVANCED KEEP。通常はcommit/rollback→pool close→wait→snapshot。cleanup rollbackによるtest isolationではない。 |
| Snapshot storage | temp所有、Destinationは外部保持 | temp所有、destinationは外部保持 | ALIGN owned lifetime template; path writers REMOVE。physical ownershipは現在のcleanup ownershipとは別。 |
| arbitrary reopen | なし | Snapshot(path)/open(path)/Database(snapshot=path) | canonical explicit openのみADVANCED KEEP; alias入口REMOVE。Go public importer追加はDEFER。 |
| closed handle | Fork拒否 | fork拒否、Database(snapshot=handle)はpath再open | 復活入口REMOVE。閉じたtemplateから新childを作れない契約へALIGN。 |
| validation boundary | 作成時＋各Fork。guest比較はrestore | open時hash、実guest比較はFork時。Python＋host rehash | ALIGN取得時complete format/guest/inventory/hash validation、以後same owned backing。mainはまだ未変更。 |
| Fork/Close concurrency | RWLockでadmitted startupを保護 | Snapshotはlockなし。path削除とstartupが競合し得る | ALIGN両言語でCloseが新startupを止めadmitted useを保護。開始済みchildはtemplate Close後も継続。 |
| Fork configuration | 元Options継承、ctxだけcaller指定 | inherited defaultsをkwargsでoverride可 | guest/format互換性は共通必須。Python timeout/developer overrideはadvanced既存能力。Go opts追加はしない。 |
| template metadata | Path()実体path、manifestなし | path書換可、manifest mutable、validate public | INTERNALIZE。template編集/保存先を普通のAPIにしない。metadataを必要とするdiagnosticsは別途判断。 |
| pytest default | Goにはfixtureなし、callerがscope管理 | session-per-worker template＋function child | CORE logical parity。baselineは共有、child mutationsは共有しない。 |
| class/session mutable helper | callerが明示的にDBを長期所有できる | builtin class_fork/class_connection_info、server直接利用も可 | class builtin2個REMOVE。serverはsetup builderとしてKEEP。ユーザーのcustomscopeを禁止するものではない。 |
| observability | Logs last16KiB | logs last16Ki characters、optional logfile、id/status/capabilities/PIDs | logs KEEP、明示log pathはSnapshot state writeとは別。追加data export/debug APIはDEFER。transport fieldsをstablecore契約にしない。 |
| runtime override | NativeDir/env legacy reject | runtime/module/wasmer_dir/env reject、host_binary developer override | v0.4.4 keep-as-is guards。MARIAMEM_RUNTIME検査はGo APIだけという現状を記録。第二runtimeを設計しない。 |

### Proposed invariants by concept

| Concept / core? | Use cases / owner | Mutable / sharing | Cleanup / guarantee | Equivalent semantics |
|---|---|---|---|---|
| 可変で使い捨てのDB / CORE | CRUD、ORM、transactions、app独自接続。test/callerが所有 | mutable。同じtestのapp接続は同じDB、別testは別DB | callerはapp/background workとpoolを停止してDB Close。ordinary SQLエラーはrecoverable。active SQL中断はDB不可用になりreplacementする | Go Start/defer Close、Python start/with、pytest function child。Go/PythonともDB外のcache/files/queuesは隔離しない |
| 再利用する不変初期状態 / CORE optional workflow | expensive setup reuse。setup owner/session/class/workerが所有 | API-level immutable。schema/committed dataを共有、connections/temp tables/session vars/未完了txは継承しない | Snapshot成功はsource消費。template Closeで新Fork禁止、admitted startupを保護。既存childは継続し個別Close。通常operationはbackingを変更しない | Go Snapshot/Fork、Python snapshot/fork、pytest baseline scope長くchild scope短く |
| 外部初期状態import / ADVANCED | compatible fixed input/cache/regressionの候補、実務需要未確認。inputはcaller、取得後templateはmariamem | external inputを読む。成功後はowned template immutable、元inputを変更しても影響しない | open前returnにguest/format/inventory/content検証。external sourceは削除しない。Closeで内部owner解放。portable/upgradeable backup formatではない | Python explicit openをKEEP。Go public equivalentなしは明示例外で、需要なしに追加しない |
| failure diagnostics / 既存logs KEEP、新artifact DEFER | failing assertion/cause inspection。test/callerがlogを必要scopeに保持 | artifact read-only data等は将来別設計。mutable test stateを次testへ渡さない | 正常/失敗でDB cleanupを維持。capture_dataのAPIは今回は作らない。既存explicit log_pathはcaller所有 | Logs/logsでcauseを読む。process/PIDはimplementation診断、publicDB identityとは別 |

### Integrity and lifecycle boundaries

現行 main の full hash は file inventory/content/guest consistency を検査するが、後で別にpathをopen/mapするため concurrent external modification を完全に防ぐsecurity guaranteeではない。Go temp ownershipも cleanup/lifetime の制御であって filesystem content immutabilityではない。

候補はcreation/import時にowned実体を完全検証し、以後supported operationで不変な同じ実体を使う。取得後silent media corruptionを毎Fork再検出する保証をしない。format/size/guest/lifetime等のcheap checkは残せる。検証はmanifest整合性であり、fixtureのbusiness correctness、migration provenance、trusted作者を証明するものではない。

API read境界をKEEPしても、新export/cache producerを必要とする理由にはしない。既存compatible artifactを読む能力と、cross-job cache製品は別。SQL dump/data inputsは普通のSQL接続でloadする用途であり、Snapshot.openが任意のSQL dumpを読めるという意味ではない。

### Narrow API sketches (proposed, not implemented)

通常は現行名のまま `Start/start → setup commit → pool close → wait_disconnected → Snapshot/snapshot → Fork/fork → Close`。baselineを一度作り、each testは独立childを所有する。modified childを別baselineにしたい場合は、そのchildのsetupを終えて**新しいSnapshot**を作る。元templateは更新しない。

pytestは既存 `mariamem_snapshot` のscopeを選び、既存function-scoped `mariamem_fork`を利用する。classだけで準備したいならclass-scoped baselineをuser fixtureで作る。そのbuilderはfixture内でstartして閉じ、同じmutablechildをclassで共有する新builtin helperは作らない。xdistのsessionはworkerごとであり、cross-worker artifact共有を暗黙に入れない。


## Appendix 3 — Use-case matrix / repeatability / reference synthesis


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


### Reference framework synthesis


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


### Repeatability / files / artifacts


**test源泉としてのopaque prepared file**: `Snapshot.open('./mystery-state')`だけではschema/dataの意味・作成recipeが分からない。guest exact identityを必要とするphysical stateはupgradeのたびに解釈・再生成可能性も問われる。

**derived cache/artifact**: versioned migration/fixture/dumpから再生成でき、source/input/guest identityによりkey付けされ、deleteすればcache missとして作り直す。削除可能なためsource of truthを奪わない。将来需要はあり得るがcross-job cacheの実ユーザー・cache invalidation運用は未確認。通常Snapshotのpath writeを正当化する唯一の根拠にしない。

**historical bytes themselves are test input**: corruption/truncation/version mismatch等のstorage regressionは、old/invalid bytesを保存すること自体に意味がある。全てのfileを現sourceで再生成できるという条件は、このregression用途には過剰。かわりにorigin、hash、format、期待する拒否/成功を説明する。public prepared importerが必要かprivate storage regression toolingで足りるかは別判断。

**SQL/dump/data fixture**: migrationから独立したdata入力は正当。origin/licensing/sanitization/seed等を管理すればfixture codeと同等に理解可能。physical Snapshot import機能がなくても通常SQL接続でloadできる。この点は「path writeを除去すると大data fixture不可能」との推論を否定する。

**readerがあるからwriterを要求しない**: advanced external importerを維持する場合でも、normal Snapshotにexport producerを新設・温存してreaderを正当化しない。外部compatible artifactの現実の供給元・用途が未実証なら、その事実とguest/format互換範囲を明記してimportの必要性自体もchallengeする。read/importを残したいという選好とcore capabilityであるという結論は別。



## Appendix 4 — Current API → product concept mapping

全て**proposed分類**。CORE/KEEPは公開名を保つ、ALIGNは意味/ownerを合わせる、REMOVEはordinarypublic入口から除く、INTERNALIZEはHOWに閉じる、ADVANCEDは明示例外、DEFERは需要・scope待ち。renameは現時点で選択していない。

| Item | Language | Proposed classification | Concept / scope | Reason |
|---|---|---|---|---|
| API-01 `Start(ctx, Options{}) (*Database,error)` | Go | CORE | mutable disposable DB / keep as-is; docs only in v0.4.4 | 通常の作成・所有・test単位破棄。Python constructorの既存別入口は個別REMOVE候補。 |
| API-02 `Options{StartupTimeout}` | Go | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-03 `Options{ShutdownTimeout}` | Go | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-04 `Options{QueryTimeout}` | Go | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-05 `Options{NativeDir}` | Go | ADVANCED | legacy migration rejection guard / keep as-is in v0.4.4; removal DEFER to possible v0.4.5 only if coherent follow-up | 既に拒否する互換signature/環境guard。第二runtimeではない。owned baseline実装に無関係なので今まとめてAPI掃除しない。 |
| API-06 `Database` | Go | CORE | mutable disposable DB / keep as-is; docs only in v0.4.4 | 通常の作成・所有・test単位破棄。Python constructorの既存別入口は個別REMOVE候補。 |
| API-07 `db.Close() error` | Go | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-08 `db.Closed() bool` | Go | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-09 `db.Err() error` | Go | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-10 `db.ConnectionInfo() ConnectionInfo` | Go | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-11 `ConnectionInfo{Host,Port,User,Password,Database}` | Go | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-12 `db.DSN() string` | Go | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-13 `db.WaitDisconnected(ctx) error` | Go | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-14 `db.Logs() string` | Go | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-15 `SnapshotOptions{Destination}` | Go | REMOVE | no normal Snapshot path-write concept / fix in v0.4.4 after approval | arbitrary path-saveはcore用途不要、maintainer intentional relianceなし。 |
| API-16 `SnapshotOptions{Rollback bool}` | Go | ADVANCED | explicit unfinished-transaction discard before baseline / keep as-is; docs only in v0.4.4 | defaultはcommit/rollback/disconnect。Rollbackはsnapshot admissionだけを制御し、test reset modeではない。 |
| API-17 `db.Snapshot(ctx, SnapshotOptions{})` | Go | ALIGN | immutable lifetime-bound baseline → independent DB / fix in v0.4.4 after approval | 同じ検証済みbackingを所有。creation成功はsource消費、Closeは新startupを拒否してadmitted startupを保護し既存childは継続。 |
| API-18 `Snapshot` | Go | ALIGN | immutable lifetime-bound baseline → independent DB / fix in v0.4.4 after approval | 同じ検証済みbackingを所有。creation成功はsource消費、Closeは新startupを拒否してadmitted startupを保護し既存childは継続。 |
| API-19 `s.Path() string` | Go | INTERNALIZE | backing/validation implementation / fix in v0.4.4 after approval | path/manifest/edit/revalidateを普通のtemplate操作にしない。取得時検証とowner lifecycleで完結。 |
| API-20 `s.Fork(ctx) (*Database,error)` | Go | ALIGN | immutable lifetime-bound baseline → independent DB / fix in v0.4.4 after approval | 同じ検証済みbackingを所有。creation成功はsource消費、Closeは新startupを拒否してadmitted startupを保護し既存childは継続。 |
| API-21 `s.Close() error` | Go | ALIGN | immutable lifetime-bound baseline → independent DB / fix in v0.4.4 after approval | 同じ検証済みbackingを所有。creation成功はsource消費、Closeは新startupを拒否してadmitted startupを保護し既存childは継続。 |
| API-22 `ErrBusy`, `ErrTransactionActive`, `ErrClosed`, `ErrUnusable` | Go | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-23 `HostError{Code,Stage,Closed,Err}` plus Error/Unwrap/Is | Go | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-24 `mariamem.start(**options)` | Python | CORE | mutable disposable DB / keep as-is; docs only in v0.4.4 | 通常の作成・所有・test単位破棄。Python constructorの既存別入口は個別REMOVE候補。 |
| API-25 `Database(*,host_binary=None,runtime=None,module=None,log_path=None,wasmer_dir=None,query_timeout=30,startup_timeout=120,shutdown_timeout=30,snapshot=None)` | Python | CORE | mutable disposable DB / keep as-is; docs only in v0.4.4 | 通常の作成・所有・test単位破棄。Python constructorの既存別入口は個別REMOVE候補。 |
| API-26 `startup_timeout`, `query_timeout`, `shutdown_timeout` | Python | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-27 `host_binary=...` | Python | ADVANCED | developer override / observations / keep as-is; docs only in v0.4.4 | 既存診断・developer機能として記録。ID/PID/status transport fieldsをcore data/identity契約にしない。stable schema再設計はDEFER。 |
| API-28 `runtime=...`, `module=...`, `wasmer_dir=...` | Python | ADVANCED | legacy migration rejection guard / keep as-is in v0.4.4; removal DEFER to possible v0.4.5 only if coherent follow-up | 既に拒否する互換signature/環境guard。第二runtimeではない。owned baseline実装に無関係なので今まとめてAPI掃除しない。 |
| API-29 `log_path=...`, `db.log_path` | Python | ADVANCED | developer override / observations / keep as-is; docs only in v0.4.4 | 既存診断・developer機能として記録。ID/PID/status transport fieldsをcore data/identity契約にしない。stable schema再設計はDEFER。 |
| API-30 `with db` / `__enter__/__exit__` | Python | CORE | mutable disposable DB / keep as-is; docs only in v0.4.4 | 通常の作成・所有・test単位破棄。Python constructorの既存別入口は個別REMOVE候補。 |
| API-31 `db.close()` | Python | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-32 `db.closed` | Python | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-33 `db.status()` | Python | ADVANCED | developer override / observations / keep as-is; docs only in v0.4.4 | 既存診断・developer機能として記録。ID/PID/status transport fieldsをcore data/identity契約にしない。stable schema再設計はDEFER。 |
| API-34 `db.connection_info()` | Python | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-35 `db.wait_disconnected(timeout=5)` | Python | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-36 `db.logs` | Python | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-37 `db.id` | Python | ADVANCED | developer override / observations / keep as-is; docs only in v0.4.4 | 既存診断・developer機能として記録。ID/PID/status transport fieldsをcore data/identity契約にしない。stable schema再設計はDEFER。 |
| API-38 `db.capabilities` | Python | ADVANCED | developer override / observations / keep as-is; docs only in v0.4.4 | 既存診断・developer機能として記録。ID/PID/status transport fieldsをcore data/identity契約にしない。stable schema再設計はDEFER。 |
| API-39 `db.diagnostics` | Python | ADVANCED | developer override / observations / keep as-is; docs only in v0.4.4 | 既存診断・developer機能として記録。ID/PID/status transport fieldsをcore data/identity契約にしない。stable schema再設計はDEFER。 |
| API-40 `db.snapshot(destination=None,*,rollback=False,timeout=120)` | Python | ALIGN | immutable lifetime-bound baseline → independent DB / fix in v0.4.4 after approval | 同じ検証済みbackingを所有。creation成功はsource消費、Closeは新startupを拒否してadmitted startupを保護し既存childは継続。 destination指定writeはREMOVE; timeout/rollbackは別にKEEP。 |
| API-41 `Snapshot(path)` | Python | REMOVE | single explicit import / child creation boundary / fix in v0.4.4 after approval | public open(path)とfork()に集約。handleをpathとして再解釈するalternate入口を廃止。 |
| API-42 `Snapshot.open(path)` | Python | ADVANCED | external prepared-state read/import / fix in v0.4.4 after approval | KEEP boundary; full guest/format/inventory/content validation before return、元pathから独立。実需要未確認、producer/cache/portableformatを追加しない。 |
| API-43 `s.validate()` | Python | INTERNALIZE | backing/validation implementation / fix in v0.4.4 after approval | path/manifest/edit/revalidateを普通のtemplate操作にしない。取得時検証とowner lifecycleで完結。 |
| API-44 `s.path` | Python | INTERNALIZE | backing/validation implementation / fix in v0.4.4 after approval | path/manifest/edit/revalidateを普通のtemplate操作にしない。取得時検証とowner lifecycleで完結。 |
| API-45 `s.manifest` | Python | INTERNALIZE | backing/validation implementation / fix in v0.4.4 after approval | path/manifest/edit/revalidateを普通のtemplate操作にしない。取得時検証とowner lifecycleで完結。 |
| API-46 `s.fork(**options)` | Python | ALIGN | immutable lifetime-bound baseline → independent DB / fix in v0.4.4 after approval | 同じ検証済みbackingを所有。creation成功はsource消費、Closeは新startupを拒否してadmitted startupを保護し既存childは継続。 source options継承を既定に、Python child timeout/developer overrideはguest compatibilityを維持するadvanced既存能力; Goに同型optsを新設しない。 |
| API-47 `Database(snapshot=s)` / `start(snapshot=s)` | Python | REMOVE | single explicit import / child creation boundary / fix in v0.4.4 after approval | public open(path)とfork()に集約。handleをpathとして再解釈するalternate入口を廃止。 |
| API-48 `Database(snapshot=path)` / `start(snapshot=path)` | Python | REMOVE | single explicit import / child creation boundary / fix in v0.4.4 after approval | public open(path)とfork()に集約。handleをpathとして再解釈するalternate入口を廃止。 |
| API-49 `s.close()` / context | Python | ALIGN | immutable lifetime-bound baseline → independent DB / fix in v0.4.4 after approval | 同じ検証済みbackingを所有。creation成功はsource消費、Closeは新startupを拒否してadmitted startupを保護し既存childは継続。 |
| API-50 `HostError(message,*,code=None,stage=None,closed=False)` | Python | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-51 `Busy`, `TransactionActive` | Python | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-52 `mariamem.__version__` | Python | KEEP | DB lifecycle / connection / diagnostics / keep as-is; docs only in v0.4.4 | 通常利用に必要な lifecycle と client integration。言語別 error/default 差を無理に統一しない。 |
| API-53 `mariamem_options` | pytest | KEEP | fixture configuration / keep as-is; docs only in v0.4.4 | session-per-workerのStart設定。public alias/CLI optionは存在しない。 |
| API-54 `mariamem_server` | pytest | ALIGN | baseline setup builder / docs only in v0.4.4 | KEEP既存fixture名; session-per-worker準備用DB。snapshot後consumed、通常test用共有可変DBではない。 |
| API-55 `mariamem_snapshot` | pytest | ALIGN | immutable lifetime-bound baseline → independent DB / fix in v0.4.4 after approval | 同じ検証済みbackingを所有。creation成功はsource消費、Closeは新startupを拒否してadmitted startupを保護し既存childは継続。 |
| API-56 `mariamem_fork` | pytest | CORE | mutable disposable DB / keep as-is; docs only in v0.4.4 | 通常の作成・所有・test単位破棄。Python constructorの既存別入口は個別REMOVE候補。 |
| API-57 `mariamem_connection_info` | pytest | CORE | mutable disposable DB / keep as-is; docs only in v0.4.4 | 通常の作成・所有・test単位破棄。Python constructorの既存別入口は個別REMOVE候補。 |
| API-58 `mariamem_class_fork` | pytest | REMOVE | no builtin shared mutable test state / fix in v0.4.4 after approval | classで前testの変更が残る。baseline scope reuseと別で、意図的実利用なし。 |
| API-59 `mariamem_class_connection_info` | pytest | REMOVE | no builtin shared mutable test state / fix in v0.4.4 after approval | classで前testの変更が残る。baseline scope reuseと別で、意図的実利用なし。 |

### Other user-visible boundaries / incidental names

| Surface / actual behavior | Classification | Product boundary / proposed scope |
|---|---|---|
| MARIAMEM_NATIVE_DIR rejection、Go MARIAMEM_RUNTIME guard、Python runtime env not consulted | ADVANCED | legacy rejection guardを維持。第二runtimeなし、current migration guideで差を記録。 |
| MARIAMEM_TIMING_DIR instrumentation | INTERNALIZE | optional developer tool。core概念でも新performancepromiseでもない。 |
| packaged host flags --snapshot/--query-timeout/--startup-timeout/--shutdown-timeout、stdin control、ownerEOF/signals | INTERNALIZE | SDK内部protocol。actual read入口あり、standalone user CLIは未文書化。public pathwrite除去時の内部exportはimplementation所有temp先を使える。 |
| private imported ArtifactError、snapshot.digest/inventory、stdlib imports、PYTHON_VERSION | INTERNALIZE | intended公開ではなくincidentalreachability。snapshot helpersはowner実装内へ、全namespacecleanupはDEFER。 |
| SQL wire/local endpoint | KEEP | 127.0.0.1 TCP4/root/empty password/test DB。root以外やpassword付きauth、TLS/compression/multi-statementcapabilities、server Prepareを一般サーバー同等と約束しない。currentguestはmodifiedMariaDBalpha lineage。 |
| SQL command size | KEEP; docs only in v0.4.4 | internal/mysqlwire/wire.go:286でSQL1..1,048,576bytes。:50でframe受信上限1,048,577bytes、:22,58でresponsepacket上限16,777,214bytes。大dumpは一回の巨大SQL入力として任意に読めるとの保証なし。 |
| sessions / concurrency | KEEP | currentcapacity16、追加connectionはrecoverableMySQL1040。sessionsのtx/variables/temptablesは独立、同DB内sharedtablesへのcommitは見える。複数testsの同mutableDB共有をisolationと呼ばない。 |
| supported platform / packaging | KEEP | macOS15+arm64 / Ubuntu24.04x86_64。Go1.26.8/Python3.14でcanonicalvalidation。Python>=3.9metadataは全版検証の約束でない。現Go1.27arm64制約をguideに残す。wheelはhost executableを提供、driverはユーザー/extra。 |
| pytest plugin loading/extras/scopes | KEEP | python/setup.cfg pytest11 entrypoint。7fixtures/noaliases/noCLIoptions。session/class scopeはworker内。driver/pool/appをpluginが自動closeするとの保証なし。 |

refsや診断fieldsをpublictableで記録することは、新stableexportpromiseにすることではない。

## Appendix 5 — Suspicious / accidental API list

| ID | Evidence / not requirement | Classification proposal | Strongest KEEP case / why not core |
|---|---|---|---|
| S01 path writes | Go Destination、Python snapshot(destination)、persistent consumer自己確認。maintainer intentional relianceなし | REMOVE v0.4.4候補 | storage配置・cache producerには便利だが、実利用未確認。通常templateをsavepointにする必要なし。TMPDIR等既存環境の実装配置とpublicDB保存機能は分ける。 |
| S02 reopened Snapshot | Python openの既存能力。Go任意reopenなし、guest比較は現在Forkまで遅延 | ADVANCED KEEP / ALIGN、Go追加DEFER | fixed compatible inputを読む明示境界として整合する。reader存在はwriter/cacheを新設する理由ではない。需要未確認。 |
| S03 constructor restore | Python Database(snapshot=...)がhandleをpath再解釈、closed persistent handleを使える | REMOVE public duplicate entrance | generic factoryの便利さはあるが、open→forkの所有ルールを迂回する必要なし。 |
| S04 Snapshot(path) | openの別spelling、普通のguideに載らない | REMOVE public construction form | 短さ以外の用途なし。classの存在を消すのではなく取得方法をcreate/openに限定。 |
| S05 path/manifest/validate | 公開backing path、Python mutable manifest/path、再hashメソッド | INTERNALIZE | storage regression/debugで使えるが通常testの概念でない。internal testsはprivate fixtureで検証できる。metadata公開は別需要で判断。 |
| S06 class mutable helpers | class一DB、function info helperはwait-only。TestSharedで前methodのschema継承。pgmem-inspiredコメント | REMOVE two builtin helpers | 長いscenarioを分割する便利さ。需要なし、単独test/順序/再実行を弱める。single testの複数assertionで表せる。 |
| S07 session mariamem_server | session-per-worker mutable builder、snapshot成功後closed | ALIGN docs only | setup builderとして役立つ。普通testのsharedmutableDBとしては推奨しない。ユーザーが独自scopeでDBを共有する能力までは禁止しない。 |
| S08 legacy override arguments | NativeDir/runtime/module/wasmer_dirは既に拒否、環境検査も差あり | ADVANCED migration guard KEEP今期、cleanup DEFER | 明確なmigration errorに価値。OwnedPreparedに必要な変更ではないので一緒に全面constructor整理しない。 |
| S09 raw observability | Python status id/ok、capabilities、PIDs、id はGo等価なし | ADVANCED / stable schema DEFER | 有用なdiagnostic・feature probe。state identityやcontrol transportをcore user概念にしない。 |
| S10 timeout/cancel assumptions | Start contextはlifetimeではない、Snapshotのcopy/hashはdeadlineで中断不可、activeSQL中断は全DB失敗 | KEEP actual limits、docs only | conventional query cancellationとは違う。auditでhard-failure containmentを追加しない。 |
| S11 “native bundle” remediation | Python __init__.pyのstartup error文はmatching wheel/native bundleを案内する | wording fix in v0.4.4候補 | host-unavailable category自体は有用。retired bundleを現行修復手段として案内しない。error enum renameは不要。 |
| S12 incidental Python names | __all__なし、ArtifactError、snapshot.digest/inventory、stdlib modules/PYTHON_VERSION等が到達可能 | INTERNALIZE intended exports; DEFER mechanical cleanup | private toolingで使える。到達可能だからpublic requirementとはしない。既存課題に関係するsnapshot helpersだけ今期内側へ移す候補。 |

### Code vs docs: contradictions and scope ambiguities

ここでは literal contradiction と historical scope ambiguity を区別する。

1. **release status stale:** README:17–19、go guide:13、python guide:3–9、status:112–114 はcandidate/future publication。maintainer confirms v0.4.3 released、remote tag存在。今回原文を修正していない。
2. **verification timing omission:** python guide:60–62 はhash/guest compatibilityをまとめて説明。current Snapshot.openはhost guest equalityを判定しない（snapshot.py:60）、次Forkでhost Validateが判定。import前returnのcomplete compatibilityは候補の新契約。
3. **ownership wording:** Go temp/path cleanup owner、Python path readerはexact immutable backing ownershipと違う。current external edit検出はper-Fork hashだが、verify/map間のpath別openはTOCTOU全防御ではない。
4. **lifetime parity:** Go snapshot.go:83のRWLockとPython snapshot.py:68,74の非同期bool-only処理は同じ保証でない。source inspectionからのgapであり、新たなruntime failureを測定した主張ではない。
5. **same Python concept two semantics:** s.forkはclosedを拒否、Database(snapshot=s)はs.path再open。explicit persistent pathがあるとClose後のhandleをconstructor経由で再利用できる。
6. **fixture wording:** README:92–93はindependent fixturesと紹介、Python guide:97はclass mutations共有を明記。plugin actualbehaviorは後者。guideが誤記とは限らないがnormal product goalとの例外がentrypointで見えない。
7. **error categories overbroad:** Go guide:118のartifact_mismatch説明とrestore validationのhost_start/host_setup wrappingは一致しない場合がある。Python input validationはValueError/OSError/JSONDecodeError等もある。docsは現在の型/categoryを列挙し、将来error schemaを暗黙採択しない。
8. **CoW usability failure:** historical integrated report:115の“No CoW ... is introduced”はpre-sizing変更のscope。current prepared_files.go:47はMAP_PRIVATE。過去の変更説明を現在HOWとして読むと混乱する。文字列だけを「現行docがCoWを完全否定」と断定しない。
9. **navigation stale:** development:100からsuperseded cleanup文書へ、go-zero-setup historical bannerからretained legacy pathへ。old integration auditのNativeDir requiredもthen-current requirementであり、現行でnonempty NativeDirは拒否する。

## Appendix 6 — Documentation-content classification and cleanup plan

90/90 baseline tracked Markdownの全文を分類した。下の全file tableとJSONはaudience/layer/currentness/actionを保存。LICENSE/NOTICE/THIRD_PARTY_LICENSESとsource/provenance義務はMarkdown整理の外側でも維持し、削除・再解釈しない。

| Canonical owner after approval | What belongs | What leaves normal usage |
|---|---|---|
| README | purpose、installation/current support、最短Fresh例、baseline reuseの意味、重要な失敗/SQL/resource限界、license links | converter/runtime詳細、Wasmer migration、memory32 traps/mmap、歴史的benchmarksの大表 |
| Go/Python guides | 完全signature/default/errors/lifetime、client/pool所有、source consume、fixture scopes、examples | toolchain再生成、FD/CoW機構、migration-era保全指示。developer overridesはadvancedの明示節に |
| project-status | published release、現在の選択済みcontract/architectureの短い要約、known limits、approved次方向 | 各古いmilestone全文、then-open release gates、未採択spikeを現行扱いする説明 |
| current architecture | 一つの現在data path、構造/ownership/lifetime、OS page CoWとlive-state cloningの区別、現在の実装制約 | 古いintegration acceptance順序・Task番号・then-currentrequirements。repro recipesはdevelopment等canonical ownerへリンク |
| docs/decisions (small) | continued constraint、status/version、why、counterargument、evidenceリンク。今回contractは承認後selectedへ | 全experimentのADR化、未承認spikeの採択済み化、duplicate HOW |
| benchmark/history index | exact source/date/platform/workload/decision status、再現命令、測定値 | unqualified“current/required/pending”をcurrent navigationで読ませること |
| development/AGENTS/release/skills | verification boundary、CI exact-source手順、human gate、disposable policy、current build/license rules | user-facing基本用語のowner役、superseded cleanupへのcanonicalリンク |

**順序付きcleanup plan（未実施）:**

1. 承認後、user contractを一つのsourceに定義。published v0.4.3のfuture tenseとcurrent policyへのリンクを先に直す。
2. README/language guidesに同じprepared baseline/individual child/consuming setup/cleanup/failure境界を載せ、全公開signatureとpytest scope表を揃える。historical performance表はcurrent guidance/indexリンクに置換し、過去値は保存。
3. architectureをcurrentHOW先頭へ整理。cold filesのOS page CoWとlive heap cloningを明確に分ける。歴史的pre-sizingについての“no new CoW”はsource-bounded evidenceとして保持。
4. 継続するdecisionだけ短く記録: disposable DB isolation、cold baseline/fresh execution、single supported runtime、cooperative reclamation limits、承認された場合のowned backing integrity。未承認とapprovedを区別。
5. project-statusの過去説明をhistory linksへ縮約。version-qualified release notes/historyは保存。unversionedalpha draftをcurrentreleaseだと読ませないindexにする。
6. obsolete anchors/old current-tense bannersを修正。historicalreportsを全面的に今日の実装へ書き直さず、date/SHA/statusとcurrent入口を明示する。
7. reviewでは新規user/agentがREADME→languageguideだけで正しいlifecycleを説明できるか確認。docs-only checksはlink/wording/diff。実装後のruntime acceptanceはその変更境界とexactsourceで別に実施。

### Complete tracked Markdown inventory (90 files)

| Path | Audience | Existing layers | Currentness / proposed cleanup |
|---|---|---|---|
| [.agents/skills/experiment-workspace/SKILL.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/.agents/skills/experiment-workspace/SKILL.md) | maintainer, coding_agent | Dev/CI rules | current; retain canonical workflow/policy; correct stale wording/history-only links only where present |
| [.agents/skills/release/SKILL.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/.agents/skills/release/SKILL.md) | maintainer, coding_agent | Dev/CI rules | current; retain canonical workflow/policy; correct stale wording/history-only links only where present |
| [AGENTS.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/AGENTS.md) | maintainer, coding_agent | Dev/CI rules | current; retain canonical workflow/policy; correct stale wording/history-only links only where present |
| [CONTRIBUTING.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/CONTRIBUTING.md) | maintainer, coding_agent | Dev/CI rules | current; retain canonical workflow/policy; correct stale wording/history-only links only where present |
| [README.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/README.md) | user | User contract, HOW, History | current entry point with stale candidate/release status; retain primary user entry; after Human Review extract architecture/history, refresh release status and complete API coverage |
| [benchmarks/README.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/README.md) | maintainer, coding_agent | Dev/CI rules, History, HOW | current benchmark index plus dated Wasmer harness sections; keep current commands/boundaries; make dated historical run recipes clearly separate |
| [benchmarks/baseline-0.1.0a1.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/baseline-0.1.0a1.md) | maintainer, coding_agent | History | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/cow-feasibility.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/cow-feasibility.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/cross-platform-verification.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/cross-platform-verification.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/direct-link-architecture-investigation.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/direct-link-architecture-investigation.md) | maintainer, coding_agent | History | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/direct-link-consumer-experience.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/direct-link-consumer-experience.md) | maintainer, coding_agent | History, WHY | bounded evidence continues to inform current guidance/limitations; retain immutable evidence and explicit source/platform/date limits; link from current architecture or measured guidance |
| [benchmarks/direct-link-futex-race-origin.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/direct-link-futex-race-origin.md) | maintainer, coding_agent | History, WHY | bounded evidence continues to inform current guidance/limitations; retain immutable evidence and explicit source/platform/date limits; link from current architecture or measured guidance |
| [benchmarks/direct-link-race-scope.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/direct-link-race-scope.md) | maintainer, coding_agent | History, WHY | bounded evidence continues to inform current guidance/limitations; retain immutable evidence and explicit source/platform/date limits; link from current architecture or measured guidance |
| [benchmarks/fast-architecture-review.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/fast-architecture-review.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/fast-baseline-analysis.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/fast-baseline-analysis.md) | maintainer, coding_agent | History | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/fast-gap-after-aria.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/fast-gap-after-aria.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/fast-tranche-baseline.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/fast-tranche-baseline.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/final-v02-latency.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/final-v02-latency.md) | maintainer, coding_agent | History | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/final-v02-local-reference.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/final-v02-local-reference.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/fork-gap-probe.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/fork-gap-probe.md) | maintainer, coding_agent | History | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/mariadb-init-investigation.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/mariadb-init-investigation.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/memory-session-envelope.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/memory-session-envelope.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/memorylifetime/README.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/memorylifetime/README.md) | maintainer, coding_agent | History | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/plugin-init-investigation.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/plugin-init-investigation.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/practical-suite-comparison.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/practical-suite-comparison.md) | maintainer, coding_agent | History | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/prepared-clone-feasibility.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/prepared-clone-feasibility.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/reentry-feasibility.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/reentry-feasibility.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/spikes/cow/README.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/spikes/cow/README.md) | maintainer, coding_agent | History | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/spikes/direct-link/README.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/spikes/direct-link/README.md) | maintainer, coding_agent | History | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/spikes/distribution/README.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/spikes/distribution/README.md) | maintainer, coding_agent | History | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/spikes/generated-go-integration/README.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/spikes/generated-go-integration/README.md) | maintainer, coding_agent | History | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/spikes/generated-go-integration/snapshot-audit.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/spikes/generated-go-integration/snapshot-audit.md) | maintainer, coding_agent | History | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/spikes/prepared-clone/README.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/spikes/prepared-clone/README.md) | maintainer, coding_agent | History | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/spikes/reentry/README.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/spikes/reentry/README.md) | maintainer, coding_agent | History | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/spikes/wasm2go/README.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/spikes/wasm2go/README.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/testcontainers-comparison.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/testcontainers-comparison.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/two-worker-verification.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/two-worker-verification.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/v04-baseline.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/v04-baseline.md) | maintainer, coding_agent | History | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/v04-default-runtime-migration.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/v04-default-runtime-migration.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/v04-direct-link-baseline.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/v04-direct-link-baseline.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/v04-fd-close-lifetime.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/v04-fd-close-lifetime.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/v04-generated-go-candidate.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/v04-generated-go-candidate.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/v04-integrated-candidate.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/v04-integrated-candidate.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/v04-snapshot-memory-lifetime.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/v04-snapshot-memory-lifetime.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/v041-distribution-cleanup.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/v041-distribution-cleanup.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/v043-characterization.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/v043-characterization.md) | maintainer, coding_agent | History, WHY | bounded evidence continues to inform current guidance/limitations; retain immutable evidence and explicit source/platform/date limits; link from current architecture or measured guidance |
| [benchmarks/v043-release-baseline.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/v043-release-baseline.md) | maintainer, coding_agent | History, WHY | bounded evidence continues to inform current guidance/limitations; retain immutable evidence and explicit source/platform/date limits; link from current architecture or measured guidance |
| [benchmarks/v043-retirement-current.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/v043-retirement-current.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/v043-wasmer-retirement.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/v043-wasmer-retirement.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/verification-cost-probe.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/verification-cost-probe.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [benchmarks/wasm2go-feasibility.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/benchmarks/wasm2go-feasibility.md) | maintainer, coding_agent | History, WHY | source/date-bounded historical investigation or reproduction recipe; preserve compact evidence and recipes; explicit historical status/link to current architecture; extract only enduring selected decisions |
| [docs/development-cleanup.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/development-cleanup.md) | maintainer, coding_agent | History, WHY | historical audit/acceptance/migration evidence; preserve evidence; visibly scope by source/date and redirect current behavior/policy to canonical docs |
| [docs/development.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/development.md) | maintainer, coding_agent | Dev/CI rules | current; retain canonical workflow/policy; correct stale wording/history-only links only where present |
| [docs/experiment-workspace.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/experiment-workspace.md) | maintainer, coding_agent | Dev/CI rules | current; retain canonical workflow/policy; correct stale wording/history-only links only where present |
| [docs/go-zero-setup.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/go-zero-setup.md) | maintainer, coding_agent | History, WHY | historical audit/acceptance/migration evidence; preserve evidence; visibly scope by source/date and redirect current behavior/policy to canonical docs |
| [docs/go.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/go.md) | user | User contract, HOW, History | current entry point with stale candidate/release status; retain primary user entry; after Human Review extract architecture/history, refresh release status and complete API coverage |
| [docs/gorm-dogfood.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/gorm-dogfood.md) | maintainer, coding_agent | History, WHY | historical audit/acceptance/migration evidence; preserve evidence; visibly scope by source/date and redirect current behavior/policy to canonical docs |
| [docs/guest-source-provenance.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/guest-source-provenance.md) | maintainer, license_reviewer, coding_agent | HOW, History, WHY, Dev/CI rules | current source/license constraints with historical audit inputs; retain current canonical provenance/recipe; separate dated audit claims and final qualification state, preserve notice/source obligations |
| [docs/guest-start-diagnostic.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/guest-start-diagnostic.md) | maintainer, coding_agent | History, WHY | historical audit/acceptance/migration evidence; preserve evidence; visibly scope by source/date and redirect current behavior/policy to canonical docs |
| [docs/macos-compatibility.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/macos-compatibility.md) | maintainer, coding_agent | History, WHY | historical audit/acceptance/migration evidence; preserve evidence; visibly scope by source/date and redirect current behavior/policy to canonical docs |
| [docs/platform-acceptance.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/platform-acceptance.md) | maintainer, coding_agent | History, WHY | historical audit/acceptance/migration evidence; preserve evidence; visibly scope by source/date and redirect current behavior/policy to canonical docs |
| [docs/project-status.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/project-status.md) | maintainer, coding_agent | User contract, HOW, WHY, History, Roadmap | current status owner with stale v0.4.3 publication claims; keep concise current contract/state/limitations/roadmap; link released milestones and decision history rather than duplicate detail |
| [docs/python.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/python.md) | user | User contract, HOW, History | current entry point with stale candidate/release status; retain primary user entry; after Human Review extract architecture/history, refresh release status and complete API coverage |
| [docs/release-readiness-v0.2.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/release-readiness-v0.2.md) | maintainer, coding_agent | History, WHY | historical audit/acceptance/migration evidence; preserve evidence; visibly scope by source/date and redirect current behavior/policy to canonical docs |
| [docs/release-readiness-v0.3.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/release-readiness-v0.3.md) | maintainer, coding_agent | History, WHY | historical audit/acceptance/migration evidence; preserve evidence; visibly scope by source/date and redirect current behavior/policy to canonical docs |
| [docs/release-readiness-v0.4.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/release-readiness-v0.4.md) | maintainer, coding_agent | History, WHY | historical audit/acceptance/migration evidence; preserve evidence; visibly scope by source/date and redirect current behavior/policy to canonical docs |
| [docs/releasing.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/releasing.md) | maintainer, coding_agent | Dev/CI rules | current; retain canonical workflow/policy; correct stale wording/history-only links only where present |
| [docs/runtime-notices.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/runtime-notices.md) | maintainer, coding_agent | History, WHY | historical audit/acceptance/migration evidence; preserve evidence; visibly scope by source/date and redirect current behavior/policy to canonical docs |
| [docs/source-alpha-publication.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/source-alpha-publication.md) | maintainer, coding_agent | History, WHY | historical audit/acceptance/migration evidence; preserve evidence; visibly scope by source/date and redirect current behavior/policy to canonical docs |
| [docs/sqlalchemy-dogfood.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/sqlalchemy-dogfood.md) | maintainer, coding_agent | History, WHY | historical audit/acceptance/migration evidence; preserve evidence; visibly scope by source/date and redirect current behavior/policy to canonical docs |
| [docs/v03-acceptance.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/v03-acceptance.md) | maintainer, coding_agent | History, WHY | historical audit/acceptance/migration evidence; preserve evidence; visibly scope by source/date and redirect current behavior/policy to canonical docs |
| [docs/v04-generated-go-architecture.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/v04-generated-go-architecture.md) | maintainer, coding_agent, advanced_user | HOW, WHY, History, Dev/CI rules | current architecture mixed with historical migration acceptance; retain current HOW; relocate dated integration/release evidence and enduring WHY after review |
| [docs/v04-guest-reproducibility.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/v04-guest-reproducibility.md) | maintainer, license_reviewer, coding_agent | HOW, History, WHY, Dev/CI rules | current source/license constraints with historical audit inputs; retain current canonical provenance/recipe; separate dated audit claims and final qualification state, preserve notice/source obligations |
| [docs/v04-integration-audit.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/v04-integration-audit.md) | maintainer, coding_agent | History, WHY | historical audit/acceptance/migration evidence; preserve evidence; visibly scope by source/date and redirect current behavior/policy to canonical docs |
| [docs/v04-license-inventory.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/v04-license-inventory.md) | maintainer, license_reviewer, coding_agent | HOW, History, WHY, Dev/CI rules | current source/license constraints with historical audit inputs; retain current canonical provenance/recipe; separate dated audit claims and final qualification state, preserve notice/source obligations |
| [docs/v04-release-ci-migration.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/v04-release-ci-migration.md) | maintainer, coding_agent | History, WHY | historical audit/acceptance/migration evidence; preserve evidence; visibly scope by source/date and redirect current behavior/policy to canonical docs |
| [docs/verification.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/verification.md) | maintainer, coding_agent | History, WHY | historical audit/acceptance/migration evidence; preserve evidence; visibly scope by source/date and redirect current behavior/policy to canonical docs |
| [release/GO-v0.1.0-alpha.1.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/release/GO-v0.1.0-alpha.1.md) | user, maintainer | Release history | historical version/draft record; retain version-qualified historical notes, never treat as current feature support |
| [release/NOTES-alpha.1.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/release/NOTES-alpha.1.md) | user, maintainer | Release history | historical version/draft record; retain version-qualified historical notes, never treat as current feature support |
| [release/NOTES-alpha.3.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/release/NOTES-alpha.3.md) | user, maintainer | Release history | historical version/draft record; retain version-qualified historical notes, never treat as current feature support |
| [release/NOTES-alpha.4.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/release/NOTES-alpha.4.md) | user, maintainer | Release history | historical version/draft record; retain version-qualified historical notes, never treat as current feature support |
| [release/NOTES-v0.1.0.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/release/NOTES-v0.1.0.md) | user, maintainer | Release history | historical version/draft record; retain version-qualified historical notes, never treat as current feature support |
| [release/NOTES-v0.2.0.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/release/NOTES-v0.2.0.md) | user, maintainer | Release history | historical version/draft record; retain version-qualified historical notes, never treat as current feature support |
| [release/NOTES-v0.3.0.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/release/NOTES-v0.3.0.md) | user, maintainer | Release history | historical version/draft record; retain version-qualified historical notes, never treat as current feature support |
| [release/NOTES-v0.4.0.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/release/NOTES-v0.4.0.md) | user, maintainer | Release history | historical version/draft record; retain version-qualified historical notes, never treat as current feature support |
| [release/NOTES-v0.4.1.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/release/NOTES-v0.4.1.md) | user, maintainer | Release history | historical version/draft record; retain version-qualified historical notes, never treat as current feature support |
| [release/NOTES-v0.4.2.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/release/NOTES-v0.4.2.md) | user, maintainer | Release history | historical version/draft record; retain version-qualified historical notes, never treat as current feature support |
| [release/NOTES-v0.4.3.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/release/NOTES-v0.4.3.md) | user, maintainer | Release history, User contract | latest released version notes, bounded to v0.4.3; retain immutable version history; current guides own latest contract |
| [release/NOTES.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/release/NOTES.md) | user, maintainer | Release history | historical version/draft record; retain under explicit version history; rename/index unversioned alpha.2 NOTES.md as historical after review |
| [tests/historical/README.md](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/tests/historical/README.md) | maintainer, coding_agent | Dev/CI rules, History | current policy for retired fixtures; keep explicit historical non-gate boundary |

## Appendix 7 — Proposed v0.4.4 / possible v0.4.5 boundaries

v0.4.4候補の一貫したthemeは **owned reusable baseline + per-test disposable children**。大量APIを一度に掃除するthemeではない。全scopeはHuman approval待ち。

| Finding | Proposed scope | Why / dependency |
|---|---|---|
| exact owned backing / verify-once / same-resource Fork | fix in v0.4.4 | core repeatabilityと実測Fork-many。source-backedownershipとClose同期を一緒にproduction-quality化する必要 |
| public path writes Destination/destination | fix in v0.4.4 | ownedtemplate creationの一経路へ簡素化。explicit-save branchを普通snapshotから除く。別cache/exportは作らない |
| Python explicit open | fix in v0.4.4 | currentread境界をownedimportにALIGN。wrong guestもopen時に拒否、外部path独立。実需要未確認を隠さない |
| Python implicit constructor restore / direct Snapshot(path) | fix in v0.4.4 | canonicalopen/fork入口とlifetimeを迂回させない。internalFDhandoffまでなくすものではない |
| Path/path/manifest/validate ordinary surface | fix in v0.4.4 | implementation-ownedresourceとpubliceditablepathの分離。format introspection/debug APIは別需要 |
| two class mutable fixtures | fix in v0.4.4 | per-testmutable isolation契約とbuiltin helpersを一致。baselineclassscope reuseは既存overrideで表現 |
| mariamem_server setup semantics / per-worker ownership | docs only in v0.4.4 | helperを新名にせず準備sourceとして役割明示。function childとの違いを示す |
| release status、current HOW、CoW distinction、oldbench nav、policyリンク | docs only in v0.4.4 | current contract理解にarchitecture archaeologyを要求しない。原historyは保存 |
| native-bundle obsolete remediation | fix wording in v0.4.4 | retired能力を修復案内しない。diagnosticcode名の変更は不要 |
| Snapshot/Fork/Start names、realSQL commit/rollback、capacity behavior | keep as-is | 名前変更だけでは問題が解けない。capacityはcurrentguest16、常永久保証ではない |
| rollback escape / timeout defaults / language context idioms | keep as-is; docs only in v0.4.4 | observedboundaryを明示。strict wallclock/cancel体系の新設はownedbaselineに必要なし |
| Go public OpenSnapshot/Import、ForkOptions | defer to v0.5+ or concrete demand | mere symmetryは追加理由でない。Pythonadvancedinput例外を文書化 |
| metadata afterClose / repeatedClose exacterror / typedstatus parity | defer to possible v0.4.5 only if coherent user issue | logicalcleanupは共通で、signature全面統一を必要としない。今は差を記録 |
| rejectedlegacykwargs/exportboundary/error schema全面整理 | defer to possible v0.4.5 | ownedtemplateから独立。現guardのmigrationerror価値あり。incident namesを要件にしない |
| debug data artifacts / cross-job cache / export-import producer | defer to v0.5+ or real workload evidence | 現需要なし。通常Snapshotをcheckpointへ戻す理由にしない |
| MariaDB stable guest、full race redesign、hard containment | defer to v0.5+ / separate explicit task | current limitations。今回のaudit/ownershipでは解決しない |
| new benchmark promises / full userframework coverage | defer to actual workloads | existingSQLAlchemy/GORMとprimaryreferenceはHTTP/Django等の互換性保証ではない |

**possible v0.4.5 は未提案・未作成。** もし所有契約をalignした後もPythonのerror/status/closed-stateに具体的な使いづらさが残れば「public failure/lifecycle predictability」というfollow-up themeは成立し得る。現在はmetadata非対称・rawcontrol leak等を発見しただけで、別releaseを正当化するuserissueの実証はない。unusedkwargs掃除、rename、debug、Go importerを寄せ集めてv0.4.5にしない。

### Integration gate after Human Review (not executed)

選択された契約の最小productiondiffをcurrentmain上に実装し、publicbreakingchanges/errors/docs/fixtureacceptanceを同じcandidateに揃える。その境界に依存するdeterministicunit、handwrittenraces、SQL/isolation/realparallel/lifetime/importfailure/resourcechecksをmacOS/Ubuntuで行う。guest変更がなければguestregenerationを要求しない。exactnewcandidateのacceptance/release qualificationをoldspikeCIで代用しない。版releaseは別の明示指示まで実行しない。



## Evidence / verification / audit boundaries

- main baseline: `c8bd25a56e9d5221abaf40b2c98102bd60c217ae` (local/remote一致)。remote v0.4.3 tag object `dd84ca4e9e0f2802766dd2f46d1c6ab24a41dc20` をread-only確認。tag objectをpeeledreleasecommitだとは記述しない。publicationはmaintainer confirmationを前提。
- audit branch: `experiment/v044-product-contract-audit`。mainを変更していない。既存TrackedMD90filesをsourcehash付きで分類。新auditreportはcurrentusageguideの書換ではなくHumanReview入力。
- reused spike: code/CI candidate `730b64db7059d0374e2e00680416de77cdb346eb`、report/evidence commit `09443d4de999b833cddc2ca536d43f9120130c79`、comparison baseline `b83dd2c8bcda6d57def2cbbe9f9b9226d93cd2ca`。両OS[CI evidence](https://github.com/masahitojp/mariamem/actions/runs/37541652530)、[review/evidence](https://github.com/masahitojp/mariamem/blob/09443d4de999b833cddc2ca536d43f9120130c79/benchmarks/v044-owned-ci-review.md)。currentmainのarchitecture採択証拠ではなくfeasibility証拠。
- guest identity current/spike同一: `33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`。このauditではguest/runtime/SDK/fixturecodeを変更せず、benchmarksを再実行しない。
- 実測readyp50（ms）: macOS minimal Go122.2→55.5/Python195.3→52.7、10MiB139.1→62.0/222.4→61.5、100MiB196.7→63.0/337.8→63.0。Ubuntu minimal151.2→63.6/269.5→75.7、10MiB168.8→68.4/301.3→82.3、100MiB248.2→65.0/454.0→77.0。
- preparationを隠していない: Python100MiBimportはmacOS145.1→237.5ms、Ubuntu197.2→287.8ms。import+16childrenは11.267→6.853s /14.643→8.608s。Go100MiBsetup/SQL全込みは16.127→12.830s /20.695→19.014s。startup/point-use tailsはrawdataに残り、全体利得をready利得と同じにしない。memory削減を今回新たに主張しない。
- 公式referenceは指定ページを閲覧してsource確認。各frameworkの機能はmariamem互換性の保証ではない。[discovery/source notes](v044-product-contract-audit-evidence/usecases-discovery.md)。
- [API discovery](v044-product-contract-audit-evidence/api-discovery.md)、[docs discovery](v044-product-contract-audit-evidence/docs-discovery.md)、[API mapping JSON](v044-product-contract-audit-evidence/api-mapping.json)、[90-document JSON](v044-product-contract-audit-evidence/documentation-inventory.json)、[inputs/checksums](v044-product-contract-audit-evidence/inputs.json)。
- report-onlyverification: signatures/export/fixtureinventoryをコードと照合、source/file/line refs、JSON、SHA/checksums、relative links、diff/statusを確認。runtime acceptance/releaseCI/guest rebuildは必要な依存変更がなく未実施。
- このaudit用worktree/source copyはcommit/push後に削除し、compact report/JSON/receiptのみ保存する。task-owned >1GiB残留は不要。cleanupの実結果はdurable workspace receiptに保存。

V0.4.4 PRODUCT CONTRACT AUDIT READY FOR HUMAN REVIEW
