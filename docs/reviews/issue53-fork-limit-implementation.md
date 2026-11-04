# Issue #53 — implementation checkpoints

The Human authorized implementing the reviewed design on 2026-11-03 after
`a4929d1234068eead0faf6034b5d2e4b27e58b31`. The first checkpoint implements shared
primitives; the next adds reachable cleanup ownership through the existing host
lifecycle. Subsequent checkpoints connect public Go entries and the control/core
Python SDK and supplied Python entries. **Full fixed/both-host acceptance remains
unfinished.**
[Issue #53](https://github.com/masahitojp/mariamem/issues/53) owns completion;
[the fixed acceptance table](issue53-fork-limit-design.md#fixed-acceptance-and-stopping-point)
is unchanged. No acceptance row covering a real entry is marked complete here.

## Current checkpoint — hosted matrix and stale credential oracle repair

Verify run [41746730774](https://github.com/masahitojp/mariamem/actions/runs/41746730774)
uses source_commit `b75af56f6960316a2d47e7865a21808a20105330`. During the Human's
explicit five-minute monitoring request, both core jobs failed the old
`TestPureMemory32Auth`: they expected1045 for placeholder credentials even though
the approved #78 endpoint accepts them. Both jobs had already passed the existing
`tests/godefault` suite, which checks accepted credentials and malformed-handshake
rejection. This is an outdated integration oracle, not evidence of a Fork-limit
runtime regression.

The test is corrected to `TestPureMemory32PlaceholderCredentials`: default
root/empty metadata stays checked; root/wrong-pass, unknown-user/empty, test/test
and root/root must execute SQL, and the original root connection remains usable.
Product/API/guest/generated behavior is unchanged. No error is ignored and the
malformed/capability handshake rejection oracle remains in
`tests/godefault/credentials_test.go`. Local macOS arm64 / Go1.26.10 checks of
both complete integration packages (`tests/generatedmemory`, `tests/godefault`)
pass. New verification uses a new SHA, not a rerun of the old source with a
substituted test or a relabelled receipt.

The completed D1 artifacts from the original run were downloaded and checked:
both OSes × Python3.11/3.14 have installed=true, exact source/host commit above,
dirty=false,20 serial and15 xdist PASS with cap1/finite-wait checks. This bounded
success is retained under the original SHA; the entire verify run is not READY
because its core jobs failed. Other families and final aggregate remain separate.

## Previous checkpoint — final race cases and matrix detector wiring

Continues from source_commit `aac7bc6fcd9e2c26983ca35dd6df6798bad9114b`.
The remaining planned Python barriers now cover both Fork spellings after the
source Session retain but before reservation. Parent Close completes without
releasing that barrier or closing the existing child; no target/export starts,
and the pending retain is returned exactly once.

The Live recovery race test passes when new debt arrives during its Reset reply,
but first reproduced a failure during an earlier owner's cleanup retry: the
old code sampled the debt version after retry and could clear the newer local
admission failure. Live now samples before the owner census/retries. The same
test preserves new debt through the first successful Reset and allows a later
explicit Reset after confirmed cleanup to clear it. This is controlled failure
timing over a framed host, not a guest-fault reproduction or changed policy.

The existing Live full-acceptance owner now includes Fork-limit option/entry/
transport/handoff tests and bounded actual-guest ownership cases for both
Python3.11/3.14 on both OSes. The installed consumer captures cap2 and confirms
third-child timeout plus capacity-busy Live Reset preserve existing SQL/data;
the workflow runs that consumer separately under both interpreters. No new job,
trigger, performance campaign or source/publication policy is added. Existing
workflow contract tests reject removal of those detector paths or per-minor
installed output binding.

Focused working-tree verification passed50 Python ownership/transport cases,
then185 workflow/selection/runtime-reuse/Live/Fork tests plus14 subtests on
macOS arm64 / Python3.14. The updated source/installed consumer's source smoke
passed using the previous clean `737f4414` host. Source-bound daily/smoke and
the fixed-row evidence map follow the code commit. Hosted installed matrix
execution remains a planned acceptance task, not an unknown design decision;
unforeseen failures during that execution are a separate category.

Clean inspected code source_commit
`8566c8ad6b5dbb62d5540120bec0e9abe3d97519` passed canonical daily check
(67 source tests, Go tests/vet,1870 Python tests plus106 subtests,91 skips),
Go/Python source DB/Live smoke and all9 selected actual-guest ownership cases
with a matching clean-source host on macOS arm64 / Go1.26.10 / Python3.14.
The [fixed-row evidence map](issue53-fork-limit-acceptance-map.md) now names all18
rows' detectors, their source/controlled/actual-guest limits and existing matrix
owners. This closes the planned local detector reconciliation; it does not mark
the hosted installed matrix PASS. The following commit adds evidence/docs only.
After that record, a detector-only follow-up adds an independent outer bound to
the pipe-stall caller and verifies default30 fixture propagation alongside the
explicit override. Its27 focused tests pass; an actual temporary-plugin negative
control that removes the SDK request deadline fails the named outer-deadline
oracle and completes cleanup. Product runtime code is unchanged from `8566c8ad`;
the earlier daily receipt does not include this follow-up test delta. Head CI
will check that delta under its own source rather than relabelling the old run.

## Previous checkpoint — bounded failure verification

Verification continues from candidate source_commit
`03d06c0a696731c2e50bfcefed2095e4589c291c` under the existing fixed acceptance.
No new resource/performance campaign or product direction is introduced.

Controlled remote-owner tests first failed on two retry defects: a failed source
export's cleanup token was not retained for retry on the source (retry instead
waited for a nonexistent target startup), and a late unreturned Snapshot was
forgotten after its Close failed. The owner now retains the export cleanup token
separately and holds the pending target Snapshot through its successful cleanup.
That cleanup also remains necessary when the old DB's source slot was already
settled before the late capture reply arrived; the extra baseline is closed
without acknowledging the original slot a second time.
Neither error nor elapsed watchdog serves as disposal proof. These same tests
pass after the local corrections; a successful retry does not clear the parent's
admission latch or rewrite the original operation failure.

Real framed-control subprocess tests stop replies after reservation, export or
target startup, then exercise timeout and KeyboardInterrupt at each boundary.
The source slot remains occupied until the delayed result is disposed; target
startup is not attempted after a late reservation/export. Late startup closes
its unpublished child exactly once while an independent target owner remains
usable. Submission/pipe-stall coverage from the previous checkpoint is retained.
Controlled owner tests also cover failed source acknowledgement, unknown target
cleanup, unsent-versus-ambiguous startup and actual-exit-before-settlement order.

Control Go tests use actual prepared backing and the common limiter for export
failure, preexisting destination preservation, wrong-parent acknowledgement,
parent Close and duplicate settlement without freeing another lease. Shared-host
Live adapter tests combine the real limiter and control/reset/cleanup paths with
controlled already-disposed execution owners and real file-removal failures:
cap2 retains old/candidate debt, failed retry starts no new child, confirmed
explicit Reset commits one generation, and unrelated debt/parent closure prevent
reopening. Retried adapter cleanup now also runs for an already-disposed owner
without a server pointer. This is not a real-engine cleanup-fault reproduction.

Focused local working-tree tests passed on macOS arm64 / Go1.26.10 / Python3.14:
control/live/forklimit race suites;87 Python ownership/transport tests; four
real-host handoff/parent/recapture cases including injected whole-source or
whole-target process loss; and a real-host raw-control range test retaining
source and sibling SQL. The latter real-host runs reused the previous clean
`6df2f5c6` host while exercising current Python source, so they are not presented
as an exact-candidate host receipt. Source-bound daily/smoke and focused actual
guest cases follow the code commit. Both-platform/Python-version installed-entry
acceptance and the final fixed-row reconciliation still determine completion.

Clean inspected code source_commit
`737f4414f6b8ac24abc53a2e90ed1d11bf90d328` then passed canonical daily check
(67 source tests, Go tests/vet,1863 Python tests plus106 subtests,91 skips) and
Go/Python real DB/Live source smoke. An independent regular checkout produced a
same-commit host with exact `vcs.revision` and `vcs.modified=false`; that host
passed all nine selected bounded handoff/range/E2E, different-binary,
mapped-resnapshot and racing-Close actual-guest cases. Whole-host loss is an
explicit process-kill injection, not a claim to reproduce a guest failure or
to kill shared hosts as a recovery policy. The prior source's receipts remain
unchanged. The next commit records these results only; head CI, installed-entry
matrix and final reconciliation are separate remaining work.

## Previous checkpoint — supplied Python entries

Implementation continues from inspected source_commit
`e401c2af3e3aa6fa8f5c7485228c0a5a7a98bd85`.

- Pytest adds session settings `mariamem_max_forks=None` and
  `mariamem_fork_timeout=30`, validates before preparation callback/command and
  forwards them to capture/every child acquisition. None/callable/PrepareCommand
  behavior stays unchanged. Invalid settings and failed acquisition retain the
  original cause and use the existing worker admission latch.
- Python E2E Config adds `max_forks`, validates before starting/preparing and
  forwards to capture. Explicit1 rejects; auto1 is left to Live's actionable
  error, with no expansion. The owned example explicitly requests2. Its hooks,
  case ordering and cleanup contracts stay unchanged.
- D1 `prepared_database(max_forks=None, fork_timeout=30)` validates at declaration
  without acquiring. These settings remain separate from root start options.
  Every run/class capture passes the declaration (auto resolves independently),
  and ordinary/finalization children use the finite timeout. Finalization closes
  remaining mutable/class owners while retaining R, then acquires the DROP child
  under the same SDK cap. Failed cleanup aborts DROP, preserves errors and still
  attempts remaining cleanup; there is no emergency slot or test-latch reset.
- Existing installed D1 serial/xdist campaigns now use explicit cap1 and observe
  every capture's requested/resolved cap and every Fork's finite timeout,
  including teardown/replacement-worker paths. Source changes add assertions;
  they are not a new receipt or a claim that the full matrix has passed.

Focused controlled tests pass on macOS arm64 / Python3.14: supplied pytest
actually runs with a held cap1 child and reports finite acquisition failure;
the next body is refused while the held child remains usable. Additional tests
cover independent D1 auto resolution, explicit propagation, retained class
sources after setup/preserved/consumed capture failure, cap1 finalization ordering
and cleanup-failed DROP refusal. The BrowserEntry cap2 first/second case test
uses real MariaDB/Live with controlled app/browser hooks; it is not browser or
framework end-to-end acceptance. Source-bound daily/smoke and the existing D1
campaign follow the code commit. Both-platform/Python-version and remaining
handoff fault acceptance still determine #53 completion.

Clean inspected code source_commit
`6df2f5c6ec07d27965266acb57c9678a04dd8cca` passed canonical daily check
(67 source tests, Go tests/vet,1846 Python tests plus106 subtests,88 skips)
and Go/Python real DB/Live source smoke on macOS arm64 / Go1.26.10 / Python3.14.
The focused entry/ownership suites passed156 tests plus12 subtests, and a
separate pinned Django6.1.2/mysqlclient2.2.7/pytest9.0.2/pytest-django4.12.0
environment passed all72 framework/ownership/policy tests without optional
Django skips.

The same clean code and host passed the existing D1 source-entry serial
campaign's20 cases and xdist campaign's15 cases, now with cap1 and finite-wait
assertions, using Python3.14 and the repository's fixed framework requirements.
This includes standard runner and pytest, class failure/skip, preparation/busy
source/migration failure, repeated runs, load/loadscope, idle/controller checks,
crash/replacement workers and controlled cleanup failure. The existing no-restore
mutation is still detected as an expected negative control. A same-source
BrowserEntry cap2 test passed with real MariaDB/Live and controlled app/browser
hooks. These are local source-entry checks, not installed-wheel, macOS15,
Ubuntu or Python3.11 acceptance.

The D1 runner's host identity guard initially refused the linked-worktree build
because pinned Go1.26.10 detects only a directory `.git` and omitted VCS metadata.
An independent regular checkout of the exact commit produced the accepted host;
build-info confirms `vcs.revision=6df2f5c6ec07d27965266acb57c9678a04dd8cca`
and `vcs.modified=false`. The runner's guard was not weakened, and refused
preflights did not execute the application campaign. The next commit only
records these verification results; head CI remains separate.

## Previous checkpoint — control and core Python SDK

Implementation continues from inspected source_commit
`24c6128b468bab7b651762b2538fe8a50d17d1da`. Shared control advertises
`fork-limit-v1`, validates legal JSON capacity/wait fields inside the request
handler and uses issued reservation tokens. An out-of-range value does not
terminate the shared host. Active leases cannot be canceled as unused tokens;
parent Close revokes unused reservations and preserves active children.

Python exposes `snapshot(max_forks=...)`, read-only `max_forks`,
`fork(timeout=...)` and the equivalent constructor's `fork_timeout`. It retains
the source Session under the parent lock, then waits/exports outside that lock.
A single nonblocking transport writer has one active and at most one queued
frame. Submission and reservation/startup replies have finite watchdogs;
responsive full-capacity polling can wait until caller timeout or parent Close.
Partially written frames retain their owner and are not interleaved or silently
dropped. Individual timeouts never kill a host with other owners.

Different-host handoff owns its source lease until actual target disposal,
dependent scratch/log cleanup and source acknowledgement. Late results retain
their cleanup owner. Consumed recapture settles the origin only after disposal;
preserved capture does not. Unknown cleanup latches admission; explicit Live
Reset retries remote debt and clears the local latch only if no new debt arrived.
Export followed by local setup failure reclaims the export without target startup.

Focused local tests pass for control (race), the core Python SDK (112 cases) and
five selected real-host ownership paths on macOS arm64 / Go1.26.10 / Python3.14.
The real-host cases include cap1 source-slot retention by a remote child,
timeout/SQL survival, recapture, parent Close with a live remote child and existing
handoff/mapped/racing-Close regressions. Controlled-host tests cover parent Close
during a full-capacity transfer wait, invalid values preserving siblings,
capability rejection and a host that stops reading its control pipe.
The focused results preceded the code commit and are not a CI receipt or full
fixed acceptance. Clean inspected code source_commit
`f6f07f8ffafc58f0da57bf3ab0dfa3c4cf8bac16` then passed canonical daily check:
67 source tests, Go daily tests/vet,1822 Python tests plus100 subtests and87 skips.
The same source passed Go/Python real DB/Live source smoke. Its rebuilt host
also passed all five selected real-host ownership tests above. The following
commit only records these results; head CI and both-host acceptance are separate.
An initial broad sandboxed run hit socket permission restrictions and the macOS
clean-source allocation-probe guard; those are not reported as successful checks.

Next: supplied pytest, E2E and D1 settings/lifecycles, the remaining controlled
handoff/cleanup failure acceptance, then the fixed both-host matrix. No new
resource/performance campaign, adoption, merge or release is included.

## Previous checkpoint — public Go limits

The Human requested continuing with a user-visible cap1 Fork wait/release path.
Implementation starts from inspected commit
`68d768550e7c8fb743e8eb3790082c4a23efc3d1`.

- Go exposes `SnapshotOptions.MaxForks` and immutable `Snapshot.MaxForks()`.
  Zero resolves auto at capture; explicit1..MaxInt32 overrides it. Invalid values
  reject before consuming the source. Capacity waiting precedes the backing lock,
  and parent Close revokes unused reservations and wakes waiters before joining
  admitted startup. Successful child lifetime stays independent of parent Close.
- A child owns its lease before the runtime watcher starts. Close, unexpected
  exit and consumed capture settle only after disposal. Preserved capture retains
  occupancy. Unknown or partial cleanup stops parent admission; no `consumed`
  flag or error string serves as a disposal proof.
- Live requires cap>=2, reserves nonblockingly before healthy drain, and preserves
  data/generation on capacity busy. Explicit Reset retries pending/current-child
  cleanup before recovery when failed, then atomically checks all debt and takes
  a slot. Another owner's unresolved cleanup and parent Close prevent recovery.
  A failed startup with delayed disposal supplies a retained cleanup-only child.
- Go fixture default2 stays intact; its configured cap now reaches the private
  Snapshot, maintaining the outer SQL-owner/inner DB lease relationship. Go HTTP
  config adds a cap override and rejects explicit1 before preparation.

Focused Go race tests passed for public Go, `internal/live`, `internal/forklimit`
and `mariamemtest`. Added tests cover public wait cancellation, parent Close,
consumed/preserved behavior, outer/inner cap propagation, cap2 Live busy/drain
reservation return, two failed disposals followed by retry, and another owner's
debt. Controlled cleanup failure evidence is distinguished from actual guest faults.
The existing Go source/installed consumer now includes actual cap1 wait/release,
timeout survival, parent Close with a live child and recapture, plus Live's spare
slot busy path, including SQL row survival after busy refusal and wait timeout.

On 2026-11-04, clean inspected source_commit
`8c4a65a34133fb6d12417119c5d61aee272c9928` passed canonical daily check
(67 source tests, Go daily tests/vet, 1808 Python tests plus100 subtests,85 skips)
and Go/Python real DB/Live source smoke on macOS arm64 / Go1.26.10 / Python3.14.
The Go consumer's assertions cover the new cap1/2 behavior; unchanged Python
smoke remains a lifecycle regression check, not Python capacity acceptance.
Focused race tests passed on the modified Go boundaries before the code commit.

The first daily attempt detected the moved G1 skip-backing-release mutation
anchor. The control now skips the extracted `backing.Close()` assignment, keeps
its same physical descriptor-retention oracle, and was actually executed with a
Go overlay: the named consumed-capture test failed semantically as required.
Its28 source/receipt validation tests also passed. This updates the detector
without weakening it or relabeling an older receipt. Extra regressions reject
duplicate reservation activation without releasing an existing child, preserve
cleanup-vs-parent-closed error priority, and return a startup slot when cleanup
was already confirmed before the failure was observed.

The following commit adds only this record to the tested source. New head CI is
separate; earlier checkpoint results remain pinned to their original sources.
Ubuntu execution and full #53 both-host/cross-language acceptance are pending.

Remaining work is the shared-control protocol and Python together, then supplied
Python fixtures/E2E/D1 and both-host fixed acceptance. The old Python handoff has
no source-lease acknowledgement; enabling that host-side limit alone would strand
capacity when a remote child closes. Keep these changes in the same subsequent
integration slice instead of adding an unlimited bypass or shipping a half-bound
handoff. No entry/acceptance case is removed and no new approval gate is added.

## Previous checkpoint — late cleanup ownership

After the first checkpoint, the Human requested continuing with the identified
startup/consumed-capture cleanup boundary. Implementation starts from inspected
commit `c810e194aa855a7e521a73a163e10d83e8bda945`. That earlier checkpoint passed
[Development CI41648322854](https://github.com/masahitojp/mariamem/actions/runs/41648322854)
(`check`, `integration`, `Live required gate`); this run is not evidence for the
new lifecycle changes below.

- `internal/disposal` separates an operation's error from its cleanup owner.
  Wrappers/joins preserve the owner and original cause. Successful cleanup does
  not rewrite the failed operation or an already stored public Close result.
- A failed framed greeting can still return nil Process, but its error now owns
  the unresolved join. One continuation per cleanup owner follows late completion;
  it does not poll, repeatedly retry filesystem failures or kill a shared host.
  Failed removal retains an owner for explicit retry.
- Host startup holds borrowed restore backing until cleanup completes. Transfer
  removal waits for execution/session completion, and Close/consumed capture use
  the same retry owner. Worker join has one waiter per Server rather than one
  per disposal retry. Imported temporary backing closes after pending startup
  cleanup, avoiding a blocking deferred Close while the borrow is still held.
- Public Go and shared-host lifecycle wrappers retain temporary/log cleanup in
  the correct order. A private Live log is removed on startup failure only after
  that call successfully created it. Post-start failure no longer discards the
  child's cleanup error. A failed control operation with an unpublished created
  handle disposes that handle before returning its error reply.
- `Lease.TrackCleanup` holds capacity until all typed owners confirm completion.
  One watcher belongs to a lease, even across duplicate reports. Unknown untyped
  cleanup remains blocked; strings never prove disposal. Confirmed late cleanup
  settles the lease but still requires explicit admission recovery.
- Internal nonblocking cleanup probes use a distinct pending condition so they
  do not add a spurious caller cancellation/timeout to the original diagnostic.

Focused Go1.26.10 macOS arm64 race tests passed for `internal/disposal`,
`internal/forklimit`, `internal/guest`, `internal/host`, `internal/control` and
the public Go package. New controlled cases cover a real framed greeting with
late completion, guest/session joins held separately, failed/retried removal,
parallel retry serialization, retained cap1 capacity, unchanged capture/Close
failure results and unpublished-handle cleanup. These are controlled lifecycle
faults, **not reproduction of an actual-engine hang or filesystem fault**.
On 2026-11-04, clean inspected commit
`c62fc38f2e8b784e104172d59d42aab2013004db` passed the canonical daily check:
67 source tests, Go daily tests/vet, 1808 Python tests plus 100 subtests; 85
opt-in/optional tests skipped. The same commit passed Go/Python real DB/Live
source smoke (capture, reset, busy/closed-parent rejection, host reap and
directory removal). Go1.26.10, macOS arm64 and Python3.14 with the repository's
unit requirements were used. These are local source checks, not Ubuntu/macOS15
qualification or full #53 acceptance. The subsequent commit only records these
results; it does not relabel the earlier `c810e194` CI receipt.

The previous inaccessible-cleanup-owner boundary is addressed. The next work is
to wire public Go Snapshot/Live and the shared-control reservation protocol,
then Python's finite send/reply watchdog, handoff and supplied entries. No
`fork-limit-v1` capability or public `max_forks` entry is advertised yet. The
full fixed acceptance table, including both hosts, is still required; no new
performance requirement or Human approval gate is added here.

## First checkpoint — implemented boundary

- `internal/forklimit`: finite immutable capacity, cancellable acquisition,
  nonblocking reservation, activation before allocation/export, Close wakeup
  and revocation of unused reservations. Active children retain their lease.
- Cleanup uncertainty retains occupancy, preserves its cause and stops admission.
  Confirmed settlement clears only its own debt. Explicit recovery checks all
  remaining debt and reserves atomically; normal disposal never resumes admission.
  Duplicate settlement does not release another lease. Storage grows with actual
  outstanding leases, not the configured maximum or lifetime Fork count.
- One-time sizing uses the minimum observed physical/cgroup/runtime memory limit,
  quarter-memory / 256 MiB, finite GOMAXPROCS fallback and MaxInt32 clamp. Linux
  membership and mount-root resolution includes visible cgroup ancestors. Hidden
  namespace ancestors cannot be observed. No free-memory or CPU-optimal claim.
- Go request-field parsers and Python's private `_forklimit` validators share
  MaxInt32 capacity and the new wait-time bound. Python rejects huge integers
  before conversion; positive subnanosecond waits serialize as `1ns`. Raw JSON
  parsers are intended for request-local use, not the fatal framing decoder.

The code is deliberately not connected to Snapshot, shared control, Python public
methods, Live, fixtures or D1 yet. In particular, the control host does not yet
advertise `fork-limit-v1`. Validator tests are not proof that bad new fields
preserve sibling SQL in a real host. Those integration cases remain required.

## First checkpoint ownership audit (historical; addressed above)

The design requires reporting an unowned late outcome before wiring the limiter.
Source inspection at the design base found this concrete path:

1. `internal/guest/linked.go`, `ConnectWithFailure`: failed ready/timeout calls
   `AbortAndWait`, then returns **nil Process + error**.
2. `internal/guest/guest.go`, `AbortAndWait`: after ten seconds without `p.done`,
   it returns an error string saying cleanup timed out. It does not provide the
   caller with a typed unresolved owner/completion outcome.
3. `internal/host/server.go`, `start`: on that error, it removes transfer scratch
   (ignoring removal failure) and returns nil Server. The public/shared-control
   callers therefore cannot distinguish joined disposal from a still-running
   linked execution when deciding whether to release a newly reserved slot.

The guest completion goroutine still retains its Process internally. This is
not evidence that its execution was abandoned by every goroutine or that an
actual engine hung. The missing owner is the **admission layer's accessible
completion/cleanup owner**. No error-message parsing or assumed slot return is
acceptable. `SnapshotHeap` also returns consumed=true on failed finish; consumed
alone cannot serve as a disposal oracle.

Recommendation for the next bounded implementation slice: preserve a private
typed cleanup owner/outcome through startup and consumed capture, including
transfer-directory disposal. Keep a failed startup's lease until that owner
confirms joined disposal. Keep the original operation failure even when later
cleanup succeeds. Test late completion and failed/retried removal with controlled
owners, then connect public Go and shared-control adapters to the same primitive.
This is already within the approved ownership work, not a new performance study
or permission to change the guest/WASM engine. No handoff removal, speculative
release, host kill or acceptance reduction is proposed.

## First checkpoint verification (historical)

Source starting point was inspected with `scripts/git_identity.py inspect HEAD`:
object_type=commit, source_commit=`a4929d1234068eead0faf6034b5d2e4b27e58b31`.
Tests below apply to the subsequent implementation diff, not to that unchanged
source commit. No benchmark or release receipt is issued.

- macOS arm64, Go1.26.10: `go test -race ./internal/forklimit` passed, including
  the final correction at `3c1dee3e232dbd986eac04ed9cde7999d46d9c87`. Tests cover
  cap1/2 contention, actual blocked-wait wakeup, cancel, Close/recovery races,
  retained cleanup debt, duplicate settlement, input bounds and sizing fixtures.
- The initial foundation's Linux amd64 test binary cross-compiled with Go1.26.10,
  before the final cleanup-cause discrimination correction. This is **not** Ubuntu
  runtime acceptance; Linux cgroup fixtures also run on the macOS test host.
- Python3.14: the 40 focused validator cases passed. No public API, host-control
  survival, stuck-pipe or installed-entry claim follows from these pure tests.
- Publication allowlist check passed. Existing Go/Python DB/Live source smoke
  passed; since the new primitives are unconnected, this is regression smoke,
  not #53 runtime acceptance.
- Daily check completed after installing the repository's unit requirements:
  67 source checks, Go daily package tests/vet, 1808 Python tests plus 100 subtests
  passed; 85 opt-in/optional tests skipped. Python3.14 / pytest9.2.0,
  xdist3.8.0 / PyMySQL1.2.3 / SQLAlchemy2.0.54. The earlier incomplete-venv/dirty-tree
  attempts failed and are not acceptance evidence.
- That daily invocation started at `5330cf4c4fb14334e51ec544b408788034357f5d`.
  During its Python phase, `3c1dee3e` changed only the new Go pool and its tests;
  the final pool race test was rerun separately. This is layered local checking,
  **not an exact-head CI receipt**. Both-platform #53 acceptance is outstanding.

The final correction uses the pool's direct full sentinel to decide whether to
wait. A cleanup cause that wraps the same sentinel must still return cleanup
failure immediately. A regression test checks that it does not wait to deadline.

No guest/WASM patch, generated source, version or release ledger changed. The
original checkout's unrelated user modifications are preserved in place.
