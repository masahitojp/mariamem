# #119: Close candidate plus A1a

**結論:** A1aを#203–205候補へ加えて再計測した。全体wallのpaired中央値は−0.87〜+0.28%で、多くが同時期A/A変動と同程度。同期P1などで短縮方向はあるが、非同期・空き枠P1では+0.01%、P2では−0.29%に留まり、追加の大きな高速化は確認できない。不要なディレクトリ作成の整理としてA1aを残す推薦は維持するが、速度保証はしない。

一方、A1a/sync/P1/cap1に68.90秒の単発tailがあり、通常の約9秒から大幅に伸びた。全件保持し中央値にも含めた。中央値の小さな差だけで性能退行なし・tail解消・製品採用可能とは結論しない。工程traceがないためA1a起因とも外部雑音とも判定できない。採用時には#119/#162の既存tail受入れと切り分けて扱う。本計測では追加診断を自動開始しない。

## What is measured

Measured source_commit `6f098cae508bf5fd7dda49402ccb2cadc0cb92f4`, branch `experiment/close-a1a`. Base `ead4101e2b40983c818ed843899e17a6a9196a7a`, product #203–205 (`f563128520fc49097ac83ef47cdea2dee21ff62a`). A1a is the allocation-only mariamem.go delta from `4aa460d6001dc981423cef91e5f63f25e0ab48bb`: remove `mariamem-go-*` MkdirTemp, db.temporary assignment and matching startup-failure RemoveAfter. Existing cleanup fields/helpers and timing marker remain to isolate the allocation change. Not a finished dead-field cleanup. `mariamem-transfer-*`, A2 shutdown RPC, mapping reset and guest remain unchanged. Not current main comparison.

Baseline uses a Go overlay restoring only mariamem.go from ead4101e; candidate builds the committed source. Same harness, compiler and generated code; separate binary hashes saved. git_identity.py checked source before builds. Within A/A same baseline binary/path/args/env, labels only in runner. A/B changes binary only within fixed Close mode. This campaign does not directly pair sync vs stop and old asynchronous gain must not be added to these percentages.

Go1.26.10, macOS27.2.1 arm64, CGO0/GOMAXPROCS8/GOGC100. Same1000row snapshot,480 total children (not480 per worker), SQL read/update/read, WaitDisconnected. P/cap1/1,1/2,2/2,2/4 ×sync/stop ×baseline-AA/baseline-A1a AB ×6pairs.16warmup+192main=208processes/99,840children. Pair members adjacent; alternating order, shuffled jobs seed119,150ms pause. No exclusion/repeats/adaptive sampling. UTC warmup start2026-11-15T09:44:35Z, final run start2026-11-15T10:11:53Z.

Primary batch wall includes final handle wait/disposal and Snapshot.Close; preparation/exit excluded. Process CPU/RSS/fault/switch counters include prep/exit and are separate. Shared host, thermal/power/background workloads not controlled. A/A is a contemporaneous control, not a confidence bound/noise subtraction or proof of equivalence. Only6pairs/cell and one host.

## Results

Each change is paired median (A1a−baseline); ratio100×(A1a/baseline−1). Negative means faster. AA is median absolute pair ratio. Independent arm medians are not substituted for paired deltas.

|P/cap|mode|A1a差 ms|A1a差 %|速いペア|AA絶対比中央値 %|AB範囲 %|
|---|---|---:|---:|---:|---:|---|
|1/1|sync|-30.31|-0.33|5/6|0.28|-0.92..+642.75|
|1/1|stop|-66.37|-0.73|5/6|0.43|-0.99..+0.11|
|1/2|sync|-80.87|-0.87|5/6|0.73|-3.87..+0.19|
|1/2|stop|+0.97|+0.01|3/6|0.24|-0.48..+0.83|
|2/2|sync|+15.38|+0.28|2/6|0.46|-0.84..+0.41|
|2/2|stop|-10.18|-0.18|3/6|0.48|-1.39..+0.96|
|2/4|sync|-16.16|-0.28|4/6|0.45|-1.32..+0.90|
|2/4|stop|-15.89|-0.29|5/6|0.42|-0.52..+1.05|

All8cell CPU paired medians range−1.01..+0.03%; RSS medians−1.36..+3.76%. No universal CPU/RSS reduction claimed; detailed pairs, ranges and arm medians in summary.json.

### Retained long observation

Main rep4, P1/cap1 sync, baseline→A1a, UTC2026-11-15T10:03:23Z/10:03:32Z: batch9276.251→68899.139ms (+642.75%). Candidate workers_ms68899.042, final drain0.097ms. Batch CPU16658.858→16027.401ms, process wall9361.082→68966.424ms. AllSQL/isolation/cleanup/counter checks passed. The extra wall is inside worker work rather than final drain, but Fork/SQL/Close attribution is absent. Similar CPU/load counters cannot prove the cause. Full-data arithmetic mean in this cell is 9218.865→19117.987ms (+107.38%); median must not hide this cost. No outlier exclusion or retrospective rerun.

## Verification and next decision

Focused candidate `go test -p 1 . ./mariamemtest ./internal/host` PASS. All208actual guest executions PASS SQL/isolation/Wait/Disposed/lease0 plus active mapping/reserved/RW recovery, creates/releases delta480. No new public API, broad release acceptance, Linux/race/Live/full application suite was run. User authorized adding A1a for this measurement, not a main merge or release. Root pre-existing user changes were untouched.

Recommendation: retain the minimal A1a change as unnecessary-work cleanup; do not justify it as a large speedup. Product finishing should remove genuinely dead directory state and update ownership tests without weakening cleanup guarantees, then use the normal targeted gate. The isolated long observation remains unexplained and does not establish either an A1a regression or harmless noise. No extra experiment is initiated here.

## Reproduce and evidence lifecycle

PLAN.md/run.py pinned before execution. `experiment_workspace.py prepare close-a1a --branch experiment/close-a1a --min-free-gib 12 --budget-gib 12`, then `run --timeout 5400 close-a1a -- python3 benchmarks/close-a1a/run.py <workspace>`. Source commit above includes the candidate; runner recreates baseline overlay. `python3 analyze.py` validates pair count and arm/hash matching, emits summary.json from all runs.jsonl. Inputs, hashes, focused tests and complete small raw results retained here. After preserving/pushing evidence, owned worktree/binaries/cache are disposable and cleaned; retained Git history reconstructs code. No large artifacts required.
