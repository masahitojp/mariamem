# OwnedPrepared — Human Review packet

> 更新: 両 OS の CI が完了し、[CI 完了後の GO packet](v044-owned-ci-review.md) が現在の結論。以下は CI 提出前の記録。

結論は **DEFER — 実機 Ubuntu CI の gate 待ち**。macOS では「より良い test primitive」と「速い Fork」の両方を確認した。設計が大きすぎるという理由の DEFER ではない。両 OS の clean-checkout CI が通れば、bounded な v0.4.4 実装候補として GO を推奨する根拠がある。まだ main へ統合・release しない。

| 判断項目 | 結果と根拠 |
|---|---|
| 1. Correctness | **PASS（macOS の確認範囲）**。完全検証は取得時。破損・inventory 欠落/余分・truncation・symlink・guest/format/JSON 型不一致を import 時に拒否。 |
| 2. Independence + Repeatability | **PASS（macOS）**。Go/Python 各 35 個の更新 child、10 世代以上、A→B→C / C→A→B / B→C→A、4 worker 並列。INSERT/UPDATE/DELETE、schema、8 MiB growth、commit/rollback 後も新 child の初期 schema/data は一致。 |
| 3. Ownership/lifetime | **PASS（macOS、低レベル Ubuntu emulation）**。名前を削除した read-only FD を完全検証し、その FD を直接 map。元 input の置換/削除から独立。Close 競合、admitted handoff、child 継続、失敗回収、二重 Close を検証。 |
| 4. macOS + Ubuntu | **FAIL / 未達**。macOS arm64 は PASS。Ubuntu x86_64 の emulation では import/FD/private-map/error cleanup は PASS。実機の SQL/parallel/lifetime/performance は CI 待ち。既知の Linux 不具合を示す FAIL ではない。 |
| 5. 実測 benefit | Go ready p50 は **53–69%**、Python ready は **73–83%**改善。Python import 準備込み 16-child suite は **40–63%**改善。Go の setup/全表走査込み 100 MiB suite は **14%**改善。 |
| 6. 追加 complexity | 約 800 行の production-facing 差分。Go owner/import、Python owner/import、FD handoff、borrow/Close の同期。fixture では 11 FD/Snapshot。manager process、独自 CoW FS、OS ごとの別 architecture は不要。 |
| 7. Recommendation | **DEFER（platform gate 待ち）**。試作を破棄する根拠は今のところない。正式な GO は実機 CI と maintainer の契約承認後。 |

**採用判断:** 実機 CI でも correctness/isolation/lifetime が PASS し、改善が維持された場合、この固定 integrity 契約で最小の production-quality 変更を v0.4.4 候補として採用するか、Yes / No？

最も強い反論は、media corruption の検出契約を狭め、FD を保持し、Go/Python に acquisition logic を持つこと。persistent path の単なる「verified flag」より堅牢だが、無償の改善ではない。現在の利用者は maintainer 一人なので移行保守性を理由に保留していない。

## 実測の最小表

各 size/variant は別 process の 3 trials × 16 Fork。ready は全 48 samples の p50/p95（nearest rank）。GOMAXPROCS=2、Go 1.26.8、Python 3.14.8、macOS arm64。順序は baseline→candidate / candidate→baseline / baseline→candidate。canonical v0.4.3 release benchmark ではない。

| Go fixture payload | backing | ready p50 ms B→C | p95 ms B→C | Snapshot ms B→C | 16-child loop 秒 B→C | 準備込み suite 秒 B→C |
|---|---:|---:|---:|---:|---:|---:|
| minimal（1 row） | 138 MiB | 116.5→54.4 | 121.6→57.6 | 356.7→346.9 | 2.10→1.11 | 3.53→1.51 |
| 10 MiB | 157 MiB | 135.1→62.9 | 153.5→69.9 | 426.5→411.1 | 2.84→1.70 | 4.06→2.83 |
| 100 MiB | 262 MiB | 185.1→57.1 | 189.8→64.5 | 704.6→641.5 | 7.71→5.60 | 13.95→11.98 |

loop は ready + point lookup + COUNT + disconnect/Close の実測合計。suite は Fresh 起動、fixture INSERT、Snapshot、loop、Snapshot Close を含む。probe subprocess/FD inventory は操作合計から除外し、実 wall 値も raw JSON に残す。

minimal baseline の Fresh 起動が 2/3 trials で約 1 秒遅れた。Fresh の変更が原因だとは示せず、Owned の改善として計上しない。準備込み minimal suite の改善率はこの差を含むので、採用の主要根拠は ready と loop。10 MiB でも両 variant に Fresh の遅い trial がある。100 MiB の準備費用は約 6.2 秒で支配的。全表走査の query behavior を改善したとの主張はしない。

| Python explicit import | import ms B→C | ready p50 ms B→C | p95 ms B→C | import + 16-child suite 秒 B→C | suite CPU 秒 B→C |
|---|---:|---:|---:|---:|---:|
| minimal | 71→128 | 185.5→50.7 | 190.4→56.2 | 3.306→1.208 | 3.62→1.30 |
| 10 MiB | 81→146 | 210.6→57.9 | 217.2→62.1 | 4.299→1.889 | 4.81→2.21 |
| 100 MiB | 133→234 | 315.5→54.6 | 322.8→61.4 | 9.921→5.983 | 11.87→7.71 |

import は同じ baseline-produced external artifact を両 variant が読む。input provisioning は import suite 外だが、その recipe と manifest/hash を保存。import の独立コピー費用は **57/65/101 ms** 増えた。少なくとも今回の prepare-once/Fork-many では便益を打ち消していない。

N=1 の prefix + Snapshot Close 相当の実測操作合計も CSV にある。Python は約 .272→.202 / .336→.252 / .740→.579 秒。独立の N=1 campaign ではなく、N=16 の先頭と実測 Close を組み合わせた補助値。単一 child の一般的な crossover を保証しない。

Go ready の process CPU p50 は 117→43 / 140→55 / 185→45 ms。Python の ready CPU 欄は parent wrapper のみで、host CPU は process probe、reaped child 全体は suite CPU に入る。parent の約 2 ms を MariaDB の総 startup CPU と解釈しない。

## データ経路・同一性

```text
creation: MariaDB stops/export → Publish manifest + files
          → open read-only owned FDs → unlink ordinary names
          → full hash/inventory comparison of retained FDs → Snapshot handle

import:   capture external manifest → independent private copy
          → open read-only owned FDs → unlink ordinary names
          → full comparison against external expected hashes → Snapshot handle

Fork:     alive/version/size/descriptor checks + borrow
          → MAP_PRIVATE of those same FDs → fresh MariaDB runtime
          → release startup borrow

Close:    reject new borrows → wait admitted borrowers → close owner FDs
child:    existing mappings survive owner Close → guest/worker join → munmap
```

検証対象は pathname ではなく、名前を削除した後の FD。import では source inode と owned inode が別であること、owned nlink=0、pwrite が EBADF になることもテストした。Python は `pass_fds` でその open-file reference を child host に渡す。handoff metadata は呼び出しごとの独立ファイル。offset/mtime/path の一致や verified flag に頼らない。

child の通常 write/growth は private mapping / child MemFS 内で処理される。Snapshot は guest heap/thread/TLS/lock の clone ではない。Snapshot→Fork→modify→新 Snapshot は別 template。元 template は更新されない。

内部 `--prepared-fd` は検証済み SDK producer からの trusted handoff。任意の外部 JSON を安全に認証する機構ではない。public `--snapshot` path import は完全検証を残す。same-UID adversary、OS が許す別経路での FD tampering、後発 media corruption を完全防御する security boundary とは主張しない。

## Lifetime / resource evidence

- Go: 35 mutating children + live-after-Close で FD **4→4**、goroutine **2→2**。
- Python: 35 mutating children、4 concurrent host workers で FD **5→5**、thread **1→1**、全 host PID を reap。pytest-xdist plugin 自体を実行したとの主張ではなく、独立 OS host process を 4 並列で作成/use/Close した。
- owner Close と Fork の競合では、admitted Fork は使えるか、閉鎖済みとして拒否する。Python は Popen handoff 内に barrier を置いて、Close が FD inheritance を待つことも確認。
- import copy/adopt の途中 FD failure、spawn failure、child startup failure、wrong guest handoff、partial guest initialization/worker failure、二重 Close を検証。
- 100 partial-map failures 後の OS file-backed VM bytes は **5,357,568→5,357,568**。既存の guest mapping/worker cleanup tests と focused races も PASS。
- Go comparison の全 18 cells で first/last child Close と Snapshot Close 後の file-backed VM は開始時と同じ。FD は warmed process の 4 に戻る。Snapshot 保持中は baseline 4 / candidate 15（11 backing FD）。
- RSS/physical-footprint の改善は主張しない。100 MiB ready の中央値は baseline RSS/footprint 約 1074/1031 MiB、candidate 約 1058/1015 MiB。10 MiB 最終 footprint は約 380→456 MiB と逆方向。Go heap/OS 回収のばらつきがあり、mapping の累積とは区別する。raw counter を保持し、実機 CI でも確認する。

1 FD/file は実装の具体的 downside。11-file fixture では問題にならないが、多数の table と同時 Snapshot で FD limit に近付く。limit-aware error cleanup はあるが、数千 table campaign や FD pooling は追加していない。

## 契約・API・統合判断

取得後の silent content corruption を毎 Fork 検出しないことは、承認済みの契約変更。hash を path cache や mtime cache に置換したのではない。元 path の再変更は owned template に影響しない。一方、後発した backing の content corruption を検出する old per-Fork guarantee は戻らない。構造・version・FD/size/lifetime の確認は残る。

`Snapshot.open(path)` は full-verify read/import として残した。`db.snapshot(path)` / Go Destination も今回の PoC では維持。明示出力は external artifact を残し、返す handle は別 owned copy を使う。write API 廃止判断を混ぜていない。

必要な semantic 差分として、通常作成の staging path は取得時点で削除される。Go Path()/Python path は provenance/staging 値で、live backing ではない。default Snapshot の path を再 open するコードは移行が必要。この点は production integration の docs/API review に含める。

小さな安全な方案は見つかった。二つの OS に共通する unlinked read-only FD と MAP_PRIVATE で実現し、Python manager や storage service は不要。約 800 行の acquisition/handoff/lifetime code と二言語の validation maintenance は残る。改善閾値は macOS ready で十分超え、ownership は test repeatability を具体的に強化した。実機 CI が失敗したら GO を撤回する。guest race redesign、hard-failure containment、MariaDB upgrade、別の Snapshot optimization は行っていない。

## Exact references / reproduction

- requested main baseline: `a23e450af19fd2086a008cc85ed35173f0103801`
- retirement base: `26d9050be9004940315e2add8253e31b26538316`
- exact v0.4.3-style comparison baseline: `b83dd2c8bcda6d57def2cbbe9f9b9226d93cd2ca`（retirement + reused characterization instrumentation）
- final code: `935f18c9fcf8134db615ed45e0f86d6fa3144071`, branch `experiment/v044-owned-snapshot`
- Go measured source: `064c658a4bcb52505a771c895e16dca1c856d447`。final code まで production Go/harness は同一。
- final Python import measured source: `1f4b4b904bd183364f928d23711f8f95b528c878`。後続は tests/CI/reduction のみ。
- compiled guest SHA256: `33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`
- main は別 task により `c8bd25a56e9d5221abaf40b2c98102bd60c217ae` へ進んだ。本 spike は pin した baseline を維持し、main を変更していない。

ローカル binary は source commit 前に build したため VCS dirty stamp を含む。source/body の同一性と binary hash を [inputs.json](v044-owned-evidence/inputs.json) に保存。native CI は exact final candidate の clean checkout を新規 build する。ローカル測定を exact-SHA release qualification として再利用しない。

コード: [Go ownership/import](../internal/snapshot/owned.go)、[private FD mapping](../internal/generatedgo/code/base/owned_prepared.go)、[Python owner](../python/mariamem/owned_snapshot.py)、[host handoff](../cmd/mariamem-host/main.go)。tests: [Go generations/parallel/Close](../tests/gointegration/owned_spike_test.go)、[Python import/isolation/failure](../tests/test_owned_snapshot_spike.py)、[partial-map OS check](../internal/generatedgo/code/base/owned_prepared_test.go)。

```sh
GOTOOLCHAIN=go1.26.8 python scripts/verify.py check
GOTOOLCHAIN=go1.26.8 MARIAMEM_PROCESS_COST="$SPIKE/process_cost" go test -race -p 1 ./internal/generatedgo/code/base ./internal/generatedgo ./internal/guest ./internal/host ./internal/snapshot -count=1 -v
GOTOOLCHAIN=go1.26.8 MARIAMEM_TEST_DEFAULT=1 go test -p 1 -tags=integration ./tests/gointegration ./tests/godefault -count=1 -timeout=4m -v
PYTHONPATH=python MARIAMEM_TEST_HOST="$SPIKE/candidate-host" python -m pytest tests/test_owned_snapshot_spike.py -q -s
```

比較の build/run/reduction は [run_compare.py](ownedspike/run_compare.py)、[summarize.py](ownedspike/summarize.py) と branch 限定 `mode=owned-spike`, `operation=verify` の CI job にある。CI は guest rebuild/release/tag/publication を実行しない。両 platform の correctness 完了後に同じ bounded comparison を行う。提出後は監視せず停止する。

canonical check（326 passed / 20 skipped）、focused races、実 Go tests、最終 Python 17 tests、OS mapping check のログ、[summary.csv](v044-owned-evidence/summary.csv)、raw cells、input manifests/hashes、lifecycle counters を compact evidence として保存した。後続の tests/CI/report 変更は対象 tooling/public-source/diff checks で検証する。

cleanup の実結果は disposable workspace の durable `cleanup-result.json` に記録する。source/code/evidence を commit/push し、FD-backed fixtures は Close 済み、worktree・専用 Go/Python caches・toolchain・build binaries・source copy・task 専用 Ubuntu image は削除する。以後の CI scratch は ephemeral runner 内に置く。
