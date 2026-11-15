# Public CloseAsync after consumed-capture debt fix

Conclusion: spare capacity P1/P2 improves in4/4pairs, paired wall−1.13%/−1.37%.
Retain small, capacity-dependent benefit; no universal speed guarantee. Full
saturation gives P1+0.52%,P2 effectively0%. Sync-AA typical variation0.31–0.94%
across cells; AA ranges overlap some AB observations. Four pairs/shared Mac,
no inferential significance or subtraction of noise. Async-AA was not measured.

Source_commit63d0e7b6 (full identity in inputs.json), Go1.26.10/macOS arm64,
CGO0/GOMAXPROCS8/GOGC100. Same1000row snapshot,480totalchildren/run, public
CloseAsync/CloseHandle instead of the internal stopForCleanup. A1a retained.
Fix only preserves capture cleanup debt for root/Fork and shared Close result.
No A2/mapping-reuse changes. One binary/hash across all runs.

8warmup+64measure=72processes/34,560children. Four pairs/cell/comparison,
P/cap1/1,1/2,2/2,2/4, sync-AA and sync/async-AB, shuffledseed119,alternating
order,pairadjacent,150ms pause. Primary batch wall includes final handles Wait,
Disposed checks and Snapshot.Close. AllSQL/isolation/lease0/mappingcount,
reserved/RW recovery and creates/releases==480 PASS. No dropped observations.

|P/cap|paired ms|paired %|async faster|sync AA abs median %|AB range %|
|---|---:|---:|---:|---:|---|
|1/1|+49.84|+0.52|1/4|0.36|-0.43..+4.33|
|1/2|-107.36|-1.13|4/4|0.66|-1.69..-0.42|
|2/2|+0.00|+0.00|2/4|0.94|-0.47..+0.48|
|2/4|-81.11|-1.37|4/4|0.31|-1.90..-0.31|

For spareP1/P2, batch CPU paired medians+1.28%/+0.08%; process peakRSS
+0.02%/+0.86%. SaturatedP2 RSS+5.16% alongside syncAA RSS+1.34%; no general
CPU/RAM saving claimed. See per-pair raw values and separate-arm medians in
summary.json; separate-arm medians are not the paired effects above.

Maximum batch wall across72runs:10,139.270ms. No observation comparable to the
prior68.9second tail; this finite absence does not resolve that cause. No new
recurrence Issue opened. UTC interval (run starts):
2026-11-15T15:49:13Z to 2026-11-15T15:58:38Z.

Prior full/race/CI gates belong to afe7d914, not this fix. Focused root/guest/
host/fixture and selected actual guest public async/CRUD/Fork checks pass on
this source. New root/Fork regression fails semantically with old snapshot.go:
root loses capture debt, Fork returns a nil stop result. Existing backing-close
oracle now requires EBADF from Close as well as Snapshot. The first focused
attempt correctly identified its old nil expectation, retained separately.

No runtime changes during measured cohort. No Linux/new wheel qualification,
new integration approval or release claimed. This is an isolated evidence
branch; production PR should carry only fix/tests and this result reference.
PLAN fixed before run. run.py recreates the negative control and positive gates;
all small raw observations and pinned source/binary identities retained. Build
caches/worktree are disposable after preservation; no large profile required.
