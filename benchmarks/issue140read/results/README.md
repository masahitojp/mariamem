# Issue140: before-notification versus after-notification wait

## Conclusion to the question

**The two profile-bound long PREPARE calls spent almost all their page wait
before the actual host notification.** Notification-to-resume was sub-millisecond.
This identifies which side of the wait to investigate; it does not yet identify
why the read/completion work arrived late. Keep #140 open, with no product fix
or pool-size decision from this diagnostic.

| Natural capture | PREPARE caller | Same page read_wait | Park registration → notification-before | Notification-after → waiter resume | trx / pool begin call |
|---|---:|---:|---:|---:|---|
| 16MiB, natural-2, db-2/scope1 | 757.585ms | 747.384ms | 747.298ms | 0.076ms | non-null / called |
| 8MiB, natural-3, db-13/scope1 | 393.714ms | 391.180ms | 390.878ms | 0.294ms | null / not called |

Both are the first PREPARE (orders INSERT), from `TestCreateOrder/two_lines`
and `TestShipOrder/pending_rejected` respectively. Each waited on its own instance's
page ID `(space=10, page=0)`. Matching numeric IDs across instances do not mean
shared physical pages. `db-2`/`db-13` abbreviate the retained `issue68-db-*` IDs.

The complete natural corpus has ten read_wait scopes ≥100ms, including
background work: registration-to-notification 373.872–763.906ms;
notification-after-to-resume 0.011–1.837ms. Those ten are **not ten independently
profile-bound PREPAREs**. Control-suite tails are excluded from this range.
There is no frequency, speedup or 8MiB/16MiB ranking claim.

The null-trx branch cannot explain both profile-bound events: the 16MiB
foreground scope really passed a non-null trx and called the conditional
pool-wait begin/end functions. A call is not proof that pool worker accounting
changed; current worker kind, active/waiting counts and queue occupancy were
not recorded. The 8MiB foreground scope skipped these calls. Background scopes
at the same snapshots are retained separately, not substituted for foreground.

## What is bound, and how

Measured diagnostic source: `040f16368965e65955b88d7459ddae3ecab6c7a8`.
Pinned product source: `a3b2b6457147e2b8edbd31fec77ab6ec04f11b22`.
Origin guest SHA256:
`14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`.
This continues the prior diagnostic at `7e6547f95b84b12c608a88c39221da62da4ce256`;
no old receipt is relabeled as this source. See [inputs.json](inputs.json) for
host/toolchain, binary digest and every generated overlay before/after hash.

Overlay-only wrappers surround current `Fn16787` (read_wait) and `Fn16624`
(shared nonspin latch). Each live read scope records block address, page ID,
actual trx argument and conditional pool begin/end calls. A scoped pprof label
joins the PREPARE foreground stack to the same read scope. Snapshots immediately
before and after profiling bind its page, block and **still-active wait ID**.
Fresh guest threads clear inherited read-scope labels.

The host hooks record the **actual parked channel**, keyed by its ThreadPool,
EA and channel identity. Notification timestamps bracket the actual `close(ch)`;
resume is recorded immediately after that channel is selected, with return
after the original unpark cleanup. We do not derive a futex EA from the page
block address. Pthread condition internals may use separate storage.
All observer clocks use the workload recorder's microsecond clock.

The natural long-event notifier stacks all include:

```text
Fn18280 → Fn18174 → Fn16619 → Fn217 → Fn89
        → host.Futex_wake → AtomicNotify → ThreadPool.wake
```

Current generated `Fn18174` performs the page-state subtraction and unlock,
then calls `Fn16619(block+24)`; the latter signals through `Fn217`.
The selected structural correspondence is read-completion/unlock, consistent
with `buf_page_t::read_complete()` in the pinned MariaDB source. Current static
literals include its page-read diagnostics and Fn18280's read-error diagnostic.
These strings are **code provenance**, not observed read/corruption errors.
[Source binding](source-binding.json) pins all selected current function bodies
and literals; it is not a complete C symbol map or an I/O execution timeline.
Raw fields at offsets24/156 are retained without treating them as a thread ID.

## Scope, controls and limits

Three focused synthetic controls pass with `-race`: actual same-channel wake;
wrong instance/address/zero-count rejection; timeout/retired-scope handling and
unrelated-latch exclusion. One live SQL SLEEP control proves the caller window
and DB labeling and has no falsely bound read scope. Eight fixed natural suites
then run two reversed blocks of 16/8MiB × polling watcher on/off. All nine
processes use the same binary and read hooks; watcher-off is **not an entirely
uninstrumented baseline**. The schedule and exit were fixed in
[plan.json](../plan.json) before builds.

All 630 cases passed; all nine runs reported zero active mappings after cleanup.
All 198 instance observers closed, with no scope/event truncation. Scope cap256
and wait cap1024 are per instance. Fast no-park scopes may be omitted, with an
explicit census. Retained per-process calls/scopes/events are replayed.

The observer itself takes locks, labels scopes and captures notifier stacks;
the goroutine snapshot also perturbs scheduling. Timings locate these observed
waits, not production overhead or event incidence. Signal-after and resume can
race on different CPUs; a negative difference would be reported as such, not
silently clamped. No new Ubuntu evidence, generic owner identification, actual
read submission/start time or effective pool-accounting proof is claimed.

The initial helper attempt stopped before compilation due to a doubled runner
path. The same finite plan then completed under the manual disk guard. This is
recorded separately in [attempts.json](attempts.json), not changed into a PASS.
Build cost is in inputs; default budget2h active/30min tooling, CI0, disk10GiB,
minimum free8GiB. No extra natural samples followed the fixed exit.

## Recommendation / remaining observation

Investigate the **pre-notification read/completion path**, rather than adding
host waiter-resume optimizations. The next bounded observation should bind the
same request's submission, worker execution/callback entry and page unlock,
with pool counters at those boundaries. This would distinguish queued work
from time inside read/completion processing. Current notification-only stacks
cannot distinguish these causes, and do not prove that the host shim or missing
pool wait notification is the root cause. No further campaign starts here.

No setting/default, product API, canonical guest, main integration,
Qualification or release is changed. Committed internal/, guest/, release/
and root Go module inputs remain equal to the pinned product source; diagnostic
runtime changes exist only in the recorded build overlays.

## Replay and future reproduction

```sh
python3 benchmarks/issue140read/results/analyze.py --check
python3 benchmarks/issue140read/source_binding.py WORKTREE OUTPUT.json
```

Replay is read-only, needs no temp tree/network and compares summary bytes,
profile digests, source-independent binding invariants, four negative mutations,
case/cleanup census and all retained checksums. Compare OUTPUT.json with the
retained source-binding.json. The compact JSON observations contain all nine
traces, SQL phase records and scoped read-event records; all three bounded
profiles are retained exactly once. Raw timings remain available without
keeping build/cache outputs. No evidence file is overwritten by `--check`.

A separately approved fresh collection can use a clean disposable checkout
with worktree/, temp/, evidence/ and the recorded Go/host conditions:

```sh
python3 scripts/experiment_disk.py --work-dir WORKSPACE --min-free-gib 8 --budget-gib 10 --timeout 900 -- python3 WORKTREE/benchmarks/issue140read/run.py WORKSPACE
```

The runner checks exact source identity and unchanged committed runtime inputs
before builds, runs synthetic controls before the guest binary, and requires the
live control before the eight natural suites. Save new receipts separately;
a future rare-event capture is not guaranteed. Preserve compact evidence and
clean owned overlays/module/build caches afterward.
