# OwnedPrepared — CI 完了後の Human Review

**GO for v0.4.4 の production-quality 候補化を推奨。確信度 HIGH（今回の bounded fixture / correctness 範囲）。**

[CI run 37541652530](https://github.com/masahitojp/mariamem/actions/runs/37541652530) は exact code/evidence candidate `730b64db7059d0374e2e00680416de77cdb346eb` の clean checkout で、macOS arm64 と Ubuntu 24.04 x86_64 とも成功した。前回の platform gate 待ち DEFER は解消。main に merge せず、release/version/tag も作成していない。この追記の commit は report/evidence のみであり、新しい source qualification SHA とは扱わない。

| Human Review 項目 | 判定 |
|---|---|
| 1. Correctness | **PASS**。両 OS で creation/import 完全検証、破損・inventory・guest/format/型不一致の拒否、元 input の変更/削除から独立する owned copy を確認。 |
| 2. Independence + Repeatability | **PASS**。各 SDK 35 mutating children、10 世代以上、3 通りの順序、4 worker 並列で INSERT/UPDATE/DELETE、schema、8 MiB growth、commit/rollback の影響が兄弟・後続 child に出ない。 |
| 3. Ownership/lifetime | **PASS**。unlinked read-only の同じ検証済み FD を map/inherit。Fork/Close 競合、admitted startup、child 継続、二重 Close、部分初期化/失敗回収。FD/VM mapping/goroutine/thread/process の累積は確認範囲でなし。 |
| 4. macOS + Ubuntu | **PASS**。ネイティブ両 platform で canonical check、focused handwritten races、Go SQL/lifecycle、Python 17 tests、実測比較が成功。 |
| 5. Measured benefit | ready p50: Go **54–74%**、Python **72–83%**短縮。Python import 込み16-child suite **39–62%**短縮。Go の重い100 MiB fixture作成/SQL込み suite **8–20%**短縮。 |
| 6. Complexity | production-facing 約800行、Go/Python acquisition、FD handoff、borrow/Close 同期。fixture 11 FD/Snapshot。manager process・OS別 architecture・custom CoW FS は不要。 |
| 7. Recommendation | **GO for v0.4.4**。速さだけでなく、外部 path の変更から切り離された repeatable template になった。正式統合は最小の production-quality 差分を人が承認した後。 |

**人への判断:** 固定契約と下記 downside を承認し、この owned-backing 方式を v0.4.4 の実装方針として採用するか、Yes / No？

最も強い反論は 1 FD/file の保持と二言語の取得/回収 logic の保守負担。後発 media corruption の毎 Fork 検出は承認済み契約から外れる。大量 table/同時 Snapshot の FD limit と Path() の staging/provenance 化を統合時に明示する必要がある。単一 Forkや長いSQL中心のsuiteでは利得が小さく、全面的な速度保証ではない。

## 実測 — exact baseline 比較

比較 baseline は `b83dd2c8bcda6d57def2cbbe9f9b9226d93cd2ca`（retirement + 既存 characterization instrumentation）であり、v0.4.3 release tag の再測定ではない。candidate は `730b64db7059d0374e2e00680416de77cdb346eb`。同じ測定 harness、GOMAXPROCS=2、Go1.26.8、Python3.14、3 trials ×16 Fork（各 cell 48 ready samples）。baseline/candidate 順序を交替。payload 0/10/100 MiB の backing は138/157/262 MiB、各11files。redolog/undo等の固定費を含む。

Go は Fresh開始、fixture INSERT、Snapshot、16回 ready/point/COUNT/Close、Snapshot Close を含む実操作合計。

| OS | payload MiB | ready p50 ms B→C | p95 ms B→C | Snapshot/import ms B→C | loop 秒 B→C | 準備込み16-child suite 秒 B→C |
|---|---:|---:|---:|---:|---:|---:|
| darwin-arm64 | 0 | 122.2→55.5 | 131.8→66.2 | 460.1→330.1 | 2.225→1.174 | 3.675→2.741 |
| darwin-arm64 | 10 | 139.1→62.0 | 155.7→68.2 | 410.9→377.0 | 3.027→1.774 | 5.083→3.797 |
| darwin-arm64 | 100 | 196.7→63.0 | 209.3→72.8 | 635.6→645.2 | 8.483→6.297 | 16.127→12.830 |
| ubuntu24.04-x86_64 | 0 | 151.2→63.6 | 156.6→67.8 | 382.1→381.6 | 3.510→2.085 | 3.983→2.599 |
| ubuntu24.04-x86_64 | 10 | 168.8→68.4 | 177.6→81.2 | 440.3→443.1 | 4.588→2.191 | 6.012→4.322 |
| ubuntu24.04-x86_64 | 100 | 248.2→65.0 | 257.8→75.6 | 781.7→780.0 | 10.926→7.894 | 20.695→19.014 |

Python は同じ baseline-produced external artifact を import、16 child のready/point/COUNT/Close、Snapshot Close を含む。artifact生成費用はこの表の外側で、input producer JSON/manifestを同梱。read/import のコピー費は実測で含めた。

| OS | payload MiB | ready p50 ms B→C | p95 ms B→C | Snapshot/import ms B→C | loop 秒 B→C | 準備込み16-child suite 秒 B→C |
|---|---:|---:|---:|---:|---:|---:|
| darwin-arm64 | 0 | 195.3→52.7 | 208.3→57.4 | 73.2→121.3 | 3.519→1.251 | 3.592→1.374 |
| darwin-arm64 | 10 | 222.4→61.5 | 235.3→71.9 | 82.9→138.3 | 4.686→2.159 | 4.769→2.299 |
| darwin-arm64 | 100 | 337.8→63.0 | 359.7→70.4 | 145.1→237.5 | 11.125→6.612 | 11.267→6.853 |
| ubuntu24.04-x86_64 | 0 | 269.5→75.7 | 279.1→84.2 | 106.9→156.9 | 4.810→1.761 | 4.920→1.925 |
| ubuntu24.04-x86_64 | 10 | 301.3→82.3 | 327.8→96.9 | 121.3→178.6 | 6.229→2.724 | 6.350→2.910 |
| ubuntu24.04-x86_64 | 100 | 454.0→77.0 | 492.8→87.8 | 197.2→287.8 | 14.445→8.309 | 14.643→8.608 |

Python import 増分は macOS 約48/55/92 ms、Ubuntu 約50/57/91 ms。準備・Closeへ同等の費用を移した結果ではなく、16-child suiteでも短縮。Go Snapshot費用はほぼ同等で、macOS100 MiBでは約10 ms増、Ubuntuでは約2 ms減だった。

### 解釈の限界

- Go100 MiB の loop 短縮はmacOS26%、Ubuntu28%。全表走査は残る。総suiteはmacOS20%、Ubuntu8%改善に留まる。後者のcandidate Freshは3回中2回約1秒遅く、baselineは約70ms。macOSは逆にbaseline3回とも約1秒遅く、candidate2回約50ms。これは既知のstartup tailで、変更していないFreshの差をowned方式の因果的benefitに算入しない。
- Go10 MiB candidate の point-use（接続を含む）は Ubuntu で単発782 ms、macOSの同trialで818/834 msのtailがあった。原因や本変更との因果関係は未確定。ready p50/p95の改善とは分け、suite実測には含めている。中央値の単純加算でsuiteを再構成しない。
- Go ready CPU p50 msはmacOS 124→45 /145→56 /202→56、Ubuntu178→73 /195→79 /276→73。Python ready CPUはparent wrapperのみであり、MariaDB host含む総CPUとは異なる。import+16-child総CPUはmacOS3.77→1.35 /5.00→2.30 /12.80→8.39秒、Ubuntu5.69→2.39 /7.84→4.12 /18.53→12.15秒。
- p95も改善したが48 samples/3 process trialsは長期tail分布を保証しない。>=25% ready改善という採用の目安を両OSで超えた。Fork-manyの実測を根拠とし、hash時間を算術で引いた値は使っていない。
- RSS/physical改善は主張しない。100 MiB Go ready RSS/primaryの中央値はmacOS1085/1036→1057/1015 MiB、Ubuntu1072/1070→1089/1088 MiB。OS回収/Goheapの差を含む。各OS18 cellsすべてfile-backed VMはSnapshot時・first/last child Close後・最終Close後に開始値へ戻った。

## 正しさ・資源の証拠

| 検証 | macOS arm64 | Ubuntu x86_64 |
|---|---|---|
| Canonical source/unit | 326 passed /23 skipped、public source687files | 同左 |
| Python実host | 17 passed; 35 children,4workers, FD9→9,thread1→1,全PIDreap | 17 passed; FD8→8,thread1→1,全PIDreap |
| Go35children + owner Close後child継続 | FD8→8,goroutine2→2 | FD9→9,goroutine2→2 |
| partial mapping失敗100回 | file-backed VM5,226,496→5,226,496 | 7,548,928→7,548,928 |
| 計測後FD | warmed4へ戻る、保持中+11 | warmed7へ戻る、保持中+11 |
| 18 Go cellsのmapping回収 | 18/18 | 18/18 |

full generated guest全体の-race cleanを主張しない。focused handwritten boundary racesのみ。pytest-xdistそのものではなく4個の独立host processを並列作成/use/Closeした。実測の性能campaignはserial16 Fork、並列性能promiseはしない。

## 契約・範囲

creation/import → implementation-owned private copy/adoption → readonly FD open/unlink →その保持FDをfull inventory/hash verify →Snapshot handle。Forkは同じFDを借り、Pythonはpass_fdsで同じopen-file referenceを継承、MAP_PRIVATEで新しいMariaDB runtimeを開始する。Closeはadmitted startupを待ち、owner FDを解放。開始済みchildのmappingは継続できる。

通常のchild write/growthはprivate mapping/child MemFSに留まり、backingを変更しない。取得後のsilent storage corruptionを毎Fork検出しない。same-UID adversaryやOSの別経路によるFD tamperingを防ぐsecurity boundaryとは主張しない。`Snapshot.open(path)`はfull-verify importとして維持し、db.snapshot(path)/Go Destinationのwrite API判断は今回混ぜていない。default pathはlive backingではなく取得時に消えるstaging/provenanceとなる。このAPI差分は正式統合時にdocs/APIレビューが必要。

## 証拠・再現・cleanup

- 初回requested main: `a23e450af19fd2086a008cc85ed35173f0103801`; この追記時のmain: `c8bd25a56e9d5221abaf40b2c98102bd60c217ae`（無変更）。
- spike branch: `experiment/v044-owned-snapshot`; CI-qualified candidate: `730b64db7059d0374e2e00680416de77cdb346eb`。
- guest SHA256: `33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`（無変更）。
- 元の実装/契約/再現コマンド: [spike report](v044-owned-snapshot-review.md)。今回のsource取得/二OS実測はCI workflowのmode=owned-spike,operation=verify。
- [CI receipt/checksums](v044-owned-evidence/ci/ci-result.json)、各platformのcheck/race/go-runtime/python-runtimeログ、raw JSON/input manifest、reduced summary.csv/jsonを同directoryに保存。reducerは既存`benchmarks/ownedspike/summarize.py`を再利用し、追加runtime test/benchmarkは実行していない。
- artifactは14日保存だがcompact evidenceをGitへ保存して期限依存を解消する。FD backing/binaries/Go caches/venv/sourceコピーは保存していない。元spike完了時に約5.3GBを削除済み。今回のreport用一時worktreeもcommit/push後に削除し、>1GiBのtask-owned残留はない。

**Did this become a better test primitive first, and a faster Fork second? → Yes（今回のbounded acceptance範囲）。**

OWNEDPREPARED SPIKE READY FOR HUMAN REVIEW
