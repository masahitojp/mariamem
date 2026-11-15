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
