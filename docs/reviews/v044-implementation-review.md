# v0.4.4 implementation — CI handoff / Human Review packet

**現時点の判定: NOT READY。両 OS の CI acceptance と、公開済み v0.4.3 との
production performance 比較が未完了です。main への merge・release はしていません。**

## 実装した契約

テストは独立した可変 DB を使い、通常の接続と commit/rollback を行い、終了時に
DB を破棄します。高価な準備は固定 baseline として共有できます。子の変更は
親・兄弟に入りません。変更した子からは別の新しい baseline を作れます。
Snapshot 成功時に準備用 DB は終了します。子の Close は親を終了せず、親の
Close 後も起動済みの子は利用できます。

作成/import 時に完全検証し、検証した backing 自体を所有します。Fork はその
同じ resource を使い、content hash を再計算しません。所有開始後の silent
media corruption を毎 Fork で再検出する保証はありません。

## 1. Material API changes

| 操作 | Python の推奨入口 | Go |
| --- | --- | --- |
| 新しい DB | `mariamem.start()` | `mariamem.Start(ctx, opts)` |
| 一時 baseline 作成 | `db.snapshot()` | `db.Snapshot(ctx, SnapshotOptions{})` |
| 作成時に永続化 | `db.snapshot_to(path)` | `SnapshotOptions.Destination` |
| 永続 baseline import | `mariamem.load_snapshot(path)` | 起動用の既存 Snapshot path option |
| 独立 DB 作成 | `baseline.fork()` / `start(snapshot=baseline)` | `baseline.Fork(ctx)` |

最後の maintainer 指定に従い、Python `snapshot(path)` は alias を残さず
`snapshot_to(path)` に置き換えました。後から save/persist する操作はありません。
temporary/persisted は作成時に決まり、Fork の隔離契約は共通です。

`Database` / `Snapshot` 型と既存の lower-level import/start 入口は残します。
通常のガイドは acquisition functions と fixture を使います。
`mariamem_class_fork` / `mariamem_class_connection_info` を削除し、function-scoped
の子を使います。Go `Snapshot.Path()`、Python `path` / `manifest` / `validate()`
は公開面から削除しました。新しい共有 fixture や cache manager はありません。

## 2. Correctness / isolation / lifetime

ローカル macOS arm64、Go 1.26.8 で次が PASS です。

- canonical `verify.py check`: Go tests/compile、vet、生成物 identity、
  Python **338 PASS / 24 SKIP / 6 subtests**、public-source check。
- focused handwritten race tests: ownership、mapping、host、wire、guest wrapper。
  生成 guest 全体の race-free 宣言ではありません。
- Go real-runtime integration/default gates: PASS。
- Python OwnedPrepared real-host cases: **18 PASS**。35 workload generations、
  順序変更、4 concurrent siblings、DML/DDL/growth/commit/rollback、子から新 baseline、
  import corruption/inventory/guest/format、source deletion、Close/startup/failure。
  該当 lifecycle check の FD **5→5**、thread **1→1**、host 回収を確認。
- 追加の multi-client/normal-Close cases: **2 PASS**。
- Snapshot lifecycle acceptance: **49 checks PASS**。
- 部分 mapping failure を100回繰り返す回収確認、truncate/regrow、rename/unlink、
  name reuse/open-file identity の focused tests: PASS。

両 OS の installed-wheel、pytest serial/xdist、canonical integration は CI の
exact-candidate gate です。Ubuntu の今回の候補について PASS はまだ主張しません。

**既存制約:** Fresh DB の `SLEEP(0.2)` 実行中に Close すると cleanup timeout に
なるケースを、公開済み v0.4.3 host と今回の host の両方で再現しました。
どちらも process/pipes/reader は回収されました。OwnedPrepared による回帰では
ありません。古い Snapshot script の Wasmer-era `SIGSTOP`/active-SQL containment
期待は現行 host に適合しないため、決定的 import rejection と専用の内部 diagnostic
へ分離しました。production の Close/guest interruption は変更していません。
この境界の保証を拡張するには別途判断が必要です。

## 3. Go / Python parity

共有するのは fixed state、子は可変で独立、capture 成功で source 終了、exact owned
backing、Close と failure cleanup は同じ意味です。Python だけに baseline-only
external import 入口があり、Go に新しい OpenSnapshot は追加していません。
Go は既存 options、Python は `snapshot_to()` で作成時 persistence を選びます。
`baseline.fork()` は保存した起動 options を引き継ぎ、汎用 `start()` は指定した
options/defaults を使います。全 option の構文・default 同一性は主張しません。

## 4. FD / resource implications

64 InnoDB tables の state は **137 prepared files / 148,977,486 bytes** でした。
ローカル macOS の独立した resource phase の結果です。

| retained Snapshots | Go total FD | Python total FD |
| ---: | ---: | ---: |
| 1 | 143 | 140 |
| 4 | 554 | 551 |
| 16 | 2,198 | 2,195 |
| 全 Close 後 | 6 | 3 |

一個あたり **137 FD**。Go の測定前は5、初回 runtime/poller 初期化後は6で、
16個分の2,192 FDは解放されました。Python は3→3です。
当該 Go soft limit は61,440、Python は1,048,575でした。これは容量保証ではありません。

Python soft limit を**256**に制限すると、1 baseline は保持でき、2個目は
`EMFILE` で拒否されました。partial import の FD は回収され、全 Close 後は3です。
単一 baseline からの子生成と、多数の別 baseline の同時保持を区別してください。
snapshot 数、prepared file 数、アプリ自身の FD 使用量を含めて予算が必要です。
低上限下の起動/回収確認も同梱 evidence に記録します。

mapping counters は virtual file-backed extent です。RSS/physical footprint と
同一視せず、FD の回収から physical memory の即時返却も推論しません。

## 5. Production performance

**結果待ち。以前の spike の改善率は今回の性能結果として掲載しません。**
CI は correctness PASS 後、FD scaling、minimal/10/100 MiB、3 trials × 16 Fork、
CRUD、独立 application connections、4-worker parallel cases を順に測定します。
Snapshot creation、persisted import、ready p50/p95、CPU、SQL、suite cost、cleanup、
resource counters を分けます。大きな COUNT を startup に含めません。

Go suite は Fresh + fixture + Snapshot + children + cleanup を含みます。
Python import suite は同じ外部 artifact に対する import + children + cleanup、
capture は別に測定します。準備費用を隠した ready 比較だけで採用しません。
API/HTTP 形の検証は独立 application connection での通常 commit の bounded proxy
であり、実 HTTP framework の新しい互換性保証ではありません。

## 6. README / docs acceptance

README/Go/Python guides は disposable DB、Fresh、prepare-once/Fork-many、隔離、
snapshot 成功時の終了、persistence の追加責任、load、Close を直接説明します。
使用のために Wasmer/mmap/CoW/direct-link の歴史を学ぶ必要はありません。
HOW は architecture、継続的制約の WHY は `docs/decisions/`、測定は history に分離。
project-status は公開済み v0.4.3、候補の状態、将来の方向を区別します。

変更ガイドの links/anchors、Python examples の parse、Go example の format、
release-doc tests、version checker は PASS。package version は公開済み0.4.3の
ままで、候補 API が未公開であることを明記しています。release prep は別判断です。

## 7. Implementation complexity / deferred work

追加の中心は owned descriptor lifecycle、exact-FD mapping、Python per-child FD
handoff とその cleanup です。長寿命 manager process、OS ごとの別 ownership model、
新 filesystem、guest/growth redesign は導入していません。

自動 cache/new shared fixture は行いません。fixture ergonomics は v0.6.0 dogfood。
guest migration と guest-wide races は v0.5+ の別境界。active-SQL interruption は
既存制約として記録し、この結果だけで v0.4.5 を作りません。

## 8. Inputs, evidence and reproduction

- Main baseline: `c8bd25a56e9d5221abaf40b2c98102bd60c217ae`。
- Exact released v0.4.3: `dd84ca4e9e0f2802766dd2f46d1c6ab24a41dc20`。
- Unchanged guest: `33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`。
- Branch: `experiment/v044-product-contract`。候補は本 report を含む commit。
- [implementation plan](v044-implementation-plan.md)。
- [local checks / hashes](v044-implementation-evidence/local-checks.json)、同 directory の
  reduced JSON、Snapshot acceptance、FD measurements、active-Close diagnostics。
- [CI reproduction / interpretation](../../benchmarks/ownedprepared/README.md)、
  `.github/workflows/v044-product-validation.yml`。

completed worktree、build/cache/venv、wheel/source copies、DB artifacts は削除し、
Git history と compact evidence のみ保持します。cleanup 結果と CI run URL は
handoff 時の回答・workspace receipt に記録します。CI が実行を所有し、完了結果で
Human Review を再開します。release/merge の自動実行はありません。

**V0.4.4 NOT READY — BOTH-PLATFORM CI ACCEPTANCE AND EXACT v0.4.3 PERFORMANCE PENDING**
