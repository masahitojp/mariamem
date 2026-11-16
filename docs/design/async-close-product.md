# Owned asynchronous Close product candidate

The Human authorized productization after #203+A1a adoption. Base main
`d70e9fc1db69cbf23810a0aff02fa90bb704504b`. Port the minimal #204/#205
implementation from `f563128520fc49097ac83ef47cdea2dee21ff62a` onto that base,
preserving A1a removal and the late startup cleanup regression repair.

## Public contract

Go Database.CloseAsync(ctx) rejects new operations under the same mutex that
publishes one shared close operation. It waits for guest root/workers, peer pipe
closure, response-reader join and host sessions. Runtime memory cleanup may
already run concurrently with transport join; the promise is quiescence before
successful return, not a total ordering of all cleanup events.

Return a non-nil CloseHandle once shutdown starts, including on wait timeout or
stop failure. A context already canceled before initiation returns nil without
starting shutdown. Wait(ctx) waits for the initial cleanup attempt and returns its
stable result; cancellation affects that waiter only. Disposed() confirms actual
reclamation independently of the saved result. Ordinary Close joins the same
operation and preserves its synchronous result. Concurrent/repeated calls share
one actor. The actor uses configured ShutdownTimeout, not the first waiter's ctx.

Normal pending cleanup keeps the Fork slot occupied without blocking the entire
pool as uncertain debt. Actual release failure uses the adopted #203 owner and
admission contract. Snapshot.Close does not drain children. Live's private
retirement retry first joins the initial operation, then uses existing recovery.
No new recovery API or safe retry contract for arbitrary descriptors is claimed.
Python's process-host lifecycle is a separate interface; this candidate exposes
Go only. Noncooperative worker limitations remain, with no forced memory release.

## Detection and verification

Runtime source_commit `7145637813ce08d5b852b6c2dc21a6f87680380a`, Go1.26.10/macOS arm64:
- Nine affected Go packages PASS (root, mariamemtest, disposal, guest, host,
  forklimit, live, generatedgo and generatedgo/code/base).
- Six race packages PASS (root, disposal, forklimit, guest, host, live).
- Actual guest public CloseAsync/Fork lifecycle (12children), CRUD/Fork,
  repeated Close and independent-root snapshot checks PASS. All handles Wait,
  disposal and mapping/reserved/RW restoration are asserted.
- Shutdown-mode Snapshot/resnapshot, Go Live source-smoke and selected runtime
  worker trap/stopped-boundary integration checks PASS.
- Python3.14/pytest8.4.2:255 boundary/timing/retention/scope checks PASS;
  generated inventory, evidence ledger, canonical prepared mapping template
  reproduction, public source and diff checks PASS.

The first Python attempt stopped before tests because pytest was absent;
passing Python results use an isolated venv. No runtime source changes follow
the tested commit; only documentation records are added. No new performance
campaign or Linux qualification was run locally. The prior48/480child benchmark
is historical, not relabelled as measuring this public API candidate. CI runs
root controls in check and all tests/generatedmemory tests in integration;
platform CI remains necessary before main adoption. Original source ownership
and generated input manifests are unchanged; runtime adapters are handwritten.

Prior tests cover concurrent/watch-first/user-first Close, canceled waiters,
stop/release gates, failed cleanup retention, capacity saturated/spare cases,
parent Snapshot.Close and final export output delivery. The public wrapper has
a cancel-before-start/stop/Wait/concurrent-Close-sharing regression. The earlier
late startup debt regression remains intact and passes. These are controlled
failure tests, not actual OS munmap failure reproduction.

## Decision and limits

Prepare for Human review of the public contract and exact candidate. This is
not integration or release approval. Previous spare-capacity gains were small
and workload-dependent; no speedup is promised. The prior68.9second observation
remains unresolved in #119; per Human instruction, recurrence requires an Issue
with source/workload/timing evidence. This finite validation recorded no such
long observation and does not prove the historical cause resolved.

Evidence commands/exit codes/source identities and small logs are retained in
the owned workspace evidence directory; code and this report are committed.
Owned caches/build/venv/worktree are disposable after preservation. Existing
user changes and unrelated worktrees are untouched.

## Review correction and public-API comparison (2026-11-16)

Preserve failed partial Snapshot backing cleanup for both root and Fork databases,
including after Snapshot consumes the source. The shared Close result now carries
that cleanup failure; CloseAsync and Wait cannot report success while ignoring
capture debt. Existing synchronous backing-close-error expectations now require
the same EBADF failure. The new controlled root/Fork regression checks stable
Close/Wait results, Disposed=false, no repeated backend stop and occupied Fork
capacity. Old snapshot.go fails this test semantically in both cases.

[Fixed measurement and all raw observations](https://github.com/masahitojp/mariamem/blob/f42e9274724030521ca6d4c7f40a37a3d4bf803e/benchmarks/async-close-product/README.md).
Measured source_commit `63d0e7b64e6c5c09631dab2efdfbd1a6a89fb849`. The three source/test files above are
byte-identical to that measured candidate; the product PR excludes its tagged
benchmark harness/raw evidence and retains the pre-existing CI mutation repair.

Same Go1.26.10/macOS arm64 binary,480totalchildren, final drain included.
4pairs/cell, sync-AA interleaved with sync/async-AB;8warmup+64main=72processes,
34,560children. AllSQL/isolation/disposal/lease/mapping restoration checks pass.
P/cap1/2 and2/4: paired wall−1.13%/−1.37% (−107.36/−81.11ms),4/4faster each;
syncAA abs medians0.66%/0.31%, with overlapping extreme observations. Saturated
1/1:+0.52%(1/4faster),2/2:approximately0%(2/4). Small,capacity-dependent value;
no significance/universal guarantee or new CPU/RSS-saving claim. Four pairs are
less than historical6paircohorts; do not combine percentages across cohorts.
No comparable68.9second observation occurred; its cause remains unresolved.

Focused root/guest/host/fixture plus actual public async/CRUD/Fork pass before
measurement. Prior full/race/CI results remain pinned to their original source,
not relabelled as testing this correction. No new race/otherOS campaign run.
The first focused attempt caught the old nil-Close expectation; it is preserved
separately from the passing measured cohort.
