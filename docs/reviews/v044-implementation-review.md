# v0.4.4 implementation — Human Review

**Product implementation ACCEPTED; RELEASE DISPATCH STOPPED pending evidence-reuse design.**
両 OS の production correctness/performance gates は PASS。承認済み実装はローカル main に統合済みで、remote push、version bump、tag、publication は未実行です。これは Product validation の結果で、Release CI の READY/publication 判定ではありません。

## 1. Implemented product contract

mariamem はテストごとに独立した mutable MariaDB を提供します。通常の application connections と commit/rollback を使い、DB の破棄を cleanup boundary にします。共有するのは準備済み baseline で、前のテストの mutations ではありません。Snapshot 成功時には source DB が終了します。子の変更から新しい Snapshot を作れても親は変わりません。起動成功した子は親 Close 後も使用でき、子ごとの Close が必要です。

Snapshot 作成/import 時に完全検証し、検証した exact backing を所有します。Fork は同じ resource を使い、毎回 content hash を再計算しません。supported operations は backing を変更しません。所有開始後の silent media corruption を毎 Fork で再検出する保証はありません。

## 2. Material API changes

| 操作 | Python | Go |
|---|---|---|
| Fresh | `mariamem.start()` | `mariamem.Start(ctx, opts)` |
| temporary baseline | `db.snapshot()` | `db.Snapshot(ctx, SnapshotOptions{})` |
| persisted baseline at creation | `db.snapshot_to(path)` | `SnapshotOptions.Destination` |
| persisted baseline acquisition | `mariamem.load_snapshot(path)` | 新しい公開 import API は追加しない |
| independent child | `baseline.fork()` / `start(snapshot=baseline)` | `baseline.Fork(ctx)` |

Python `snapshot(path)` は `snapshot_to(path)` へ置換し alias は残しません。後から save/persist はありません。Database/Snapshot 型と互換の lower-level acquisition は残します。class-shared mutable fixtures (`mariamem_class_fork` / `mariamem_class_connection_info`) と公開 metadata (`Snapshot.Path()` / `path` / `manifest` / `validate()`) を削除します。run-wide fixture/cache manager は追加しません。

## 3. Correctness / isolation / lifecycle

macOS arm64 / Ubuntu x86_64 とも CI PASS: source/unit, handwritten race checks, Go real SQL/lifecycle, Python import/isolation/lifecycle, installed wheel pytest/xdist。DML/DDL/growth、commit/rollback、35 workload generations、ordering、concurrent siblings、parent unchanged、source-path deletion、import corruption/inventory/guest/format rejection、Fork/Close、double Close、startup/partial mapping failure を既存 focused gates で確認。Snapshot acceptance は両 OS 49 checks PASS。

Installed-wheel の failure-cleanup scenario は意図的に assertion failure と setup error を発生させる negative test です。ログの failed/error 行は期待結果で、consumer harness の `alpha.json` は PASS、fixture hosts の回収を確認しています。全生成 guest の race-free や任意強制中断の安全性は主張しません。

## 4. Go / Python parity

baseline と mutable child の分離、exact backing ownership、source consumption、child independence、Close/failure semantics は一致。構文 parity は強制しません。Go には baseline-only public path import を追加せず、Python `load_snapshot` がその入口です。`fork()` は source options を引き継ぎ、汎用 Python `start` は指定/default options を使います。

## 5. Production measurement

Baseline source: `c8bd25a56e9d5221abaf40b2c98102bd60c217ae` (published v0.4.3).
Candidate source: `c5f43106a8054bb59a2da9184a1c2103fe1a1d9f`.
Unchanged guest: `33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`.
[Completed CI](https://github.com/masahitojp/mariamem/actions/runs/37898847164): both jobs success.

Three trials × 16 Forks per serial shape (48 ready samples). 数字は production candidate の実測で、spike の値を流用しません。p95 は48 samplesの範囲での指標であり性能保証ではありません。

| OS | payload | Go ready p50 ms | Python ready p50 ms | Go ready p95 ms | Python ready p95 ms |
|---|---|---:|---:|---:|---:|
| macos | minimal | 189.1 → 93.2 | 274.6 → 133.1 | 238.0 → 125.7 | 325.3 → 215.6 |
| macos | 10 MiB | 208.7 → 125.5 | 269.9 → 116.1 | 244.1 → 152.4 | 334.0 → 163.6 |
| macos | 100 MiB | 264.4 → 138.2 | 421.2 → 120.6 | 339.1 → 163.9 | 483.4 → 145.9 |
| ubuntu | minimal | 174.0 → 75.6 | 305.1 → 82.9 | 181.1 → 80.8 | 311.8 → 92.9 |
| ubuntu | 10 MiB | 195.0 → 78.7 | 345.1 → 88.8 | 203.1 → 84.0 | 357.8 → 98.8 |
| ubuntu | 100 MiB | 279.3 → 76.6 | 515.8 → 84.6 | 286.5 → 79.8 | 527.8 → 95.5 |

Suite wall p50 seconds (baseline → candidate): Go includes Fresh + fixture + Snapshot + children + cleanup; Python includes persisted import + children + cleanup, with artifact creation measured separately. SQL/read workloads are included in suite cost but excluded from Fork→ready.

| OS | payload | Go 16-Fork suite s | Python import 16-Fork suite s |
|---|---|---:|---:|
| macos | minimal | 5.486 → 3.977 | 5.091 → 2.977 |
| macos | 10 MiB | 7.263 → 5.696 | 5.894 → 3.577 |
| macos | 100 MiB | 20.525 → 18.569 | 13.919 → 9.171 |
| ubuntu | minimal | 3.681 → 2.075 | 5.541 → 2.041 |
| ubuntu | 10 MiB | 5.865 → 3.993 | 7.036 → 3.000 |
| ubuntu | 100 MiB | 22.153 → 19.041 | 16.018 → 9.019 |

Serial Fork p50 improvements: macOS Go 40–51%, Python 51–71%; Ubuntu Go 57–73%, Python 73–84%. Initial ≥25% repeated-Fork decision aid is met. Suite benefit is smaller for expensive fixture/scan work: macOS Go 10–28% / Python 34–42%, Ubuntu Go 14–44% / Python 44–63%. This is a concrete prepare-once/Fork-many improvement, not a claim that expensive COUNT becomes faster.

Bounded realistic suites (wall p50, baseline → candidate):

| OS | boundary | light CRUD s | application connection s | 4-worker / 10 MiB s |
|---|---|---:|---:|---:|
| macos | Go | 4.757 → 2.934 | 4.427 → 3.828 | 5.194 → 4.056 |
| macos | Python | 5.146 → 3.738 | 4.898 → 3.099 | 2.478 → 1.677 |
| ubuntu | Go | 3.733 → 2.125 | 3.764 → 2.142 | 5.837 → 4.019 |
| ubuntu | Python | 5.927 → 2.431 | 5.964 → 2.467 | 4.340 → 2.833 |

Application case uses independent application connections with normal commits, a bounded API/HTTP-style proxy; it does not qualify a new HTTP framework. CPU falls in the compared serial/realistic suites. CPU scopes differ: Go RUSAGE_SELF excludes the counter helper child; Python includes reaped children and diagnostic helper. Compare within each boundary, not Go CPU against Python CPU.

### Acquisition cost and resource downside

Python import makes an independent owned copy; this cost is paid once per handle. Serial import medians ms (minimal/10/100 MiB):
- macos: 86.5 → 266.4, 91.2 → 270.4, 149.8 → 560.5.
- ubuntu: 122.2 → 177.3, 139.1 → 202.6, 227.3 → 327.6.

This added preparation cost is already included in the reported Python import suite. Capture of 100 MiB temporary Snapshot: macOS 1,182→1,342 ms (three-trial median); Ubuntu 967→970 ms. Persisted capture: macOS 1,514→1,553 ms; Ubuntu 970→1,065 ms. Capture/import are not universally faster; the gain is repeated use. macOS ready/capture variation is visible; this small hosted-CI sample should not become a fixed performance promise.

## 6. FD / memory implications

64 tables yielded 137 prepared files (~149 MB). Each held Snapshot retains approximately one read-only FD per file. No long-lived Python manager or different per-OS ownership design is introduced.

| OS | boundary | 1 Snapshot total FD | 16 Snapshots total FD | after Close | tested soft limit |
|---|---|---:|---:|---:|---:|
| macos | go | 143 | 2198 | 6 | 10240 |
| macos | import | 140 | 2195 | 3 | 10240 |
| ubuntu | go | 144 | 2199 | 7 | 65536 |
| ubuntu | import | 141 | 2196 | 4 | 65536 |

Both FD resource gates PASS. Go macOS baseline 5 becomes 6 after one-time runtime/poller initialization; all 2,192 backing FDs for 16 templates are released. Python returns to its starting count. Existing local limit=256 tests accepted one 137-file template, rejected another with EMFILE and cleaned partial acquisition; multiple distinct baselines require explicit FD budgeting. Baseline sharing does not multiply retained parent FDs per test.

FD and virtual mapping counters do not imply immediate physical/RSS return. Raw JSON contains RSS/private/physical or platform-equivalent counters, with bounded before/after sampling; parallel child peak sampling is not available and no peak-memory capacity guarantee is made.

## 7. README / documentation

README and language guides directly explain what/why, Fresh vs reusable baseline, real commits, Snapshot success consumes source, fork independence, Close, snapshot_to persistence and load_snapshot. mmap/CoW/Wasmer/direct-link history is not prerequisite knowledge. Current HOW lives in architecture; constraining WHY in decisions; historical measurements remain evidence. Candidate guides explicitly separate unreleased APIs from published v0.4.3 installation. Wording/reference/example/version/public-source checks passed; this result does not publish those APIs.

## 8. Decision, cleanup and next boundary

READY FOR v0.4.4 RELEASE PREP: correctness and repeatability are preserved on both platforms, and prepare-once/Fork-many has material measured benefit. Downside: owned-copy acquisition cost and retained FDs. Existing active-SQL forced Close timeout behavior occurred on both v0.4.3 and candidate; guest-wide races/non-cooperative reclamation remain separate scope. No new issue found here warrants creating v0.4.5. Cache management/shared fixture ergonomics are deferred to dogfood; guest migration/races to v0.5+ scope.

Runtime baseline was `c8bd25a…`; implementation branch is `experiment/v044-product-contract` at `c5f4310…`. Separate identity-prevention branch is `experiment/v044-git-identity-guard` at `69f852d…`. Its 10 identity + 6 harness tests passed; it changes tooling/docs, not runtime. As agreed, integrating it does not require repeating macOS/Ubuntu runtime acceptance. Final-main identity/fail-fast checks suffice for that boundary. Preserve actual CI source SHA rather than relabeling CI evidence onto a later commit.

The maintainer accepted the product/API/FD trade-off and authorized release. Runtime candidate `c5f4310…`, identity change `55f46a1…`, and its scope clarification `69f852d…` were subsequently fast-forwarded into local main. No runtime edits were made during integration. Remote main remains at v0.4.3. Release dispatch is explicitly stopped pending review of [runtime-evidence reuse](v044-release-runtime-reuse-design.md). Version remains 0.4.3; no tag/publication occurred. Completed local worktrees/cache/build/venv/temp were removed. Both CI cleanup records confirm scratch and recreated build removal, with no retained >1 GiB paths. Only compact reports/JSON/CSV/logs/hashes remain.

Compact CI evidence is committed under `v044-implementation-evidence/ci-*`; `CI-SHA256SUMS.json` records its hashes. Original uploaded artifacts were retained locally and all 146 recorded hashes per platform verified. The earlier pending report remains in [tested candidate history](https://github.com/masahitojp/mariamem/blob/c5f43106a8054bb59a2da9184a1c2103fe1a1d9f/docs/reviews/v044-implementation-review.md). This report is acceptance evidence for that tested SHA, not a READY receipt for a later integration/release SHA.

**V0.4.4 IMPLEMENTATION READY FOR HUMAN REVIEW**
