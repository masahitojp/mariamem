# Stable-endpoint live DB — Go host design proposal

Decision proposed: implement a bounded Go-owned stable endpoint and explicit
Go/Python Live lifecycle, using existing Snapshot/Fork. This document proposes
the next candidate; it does not approve implementation, main adoption or release.
The Human's latest instruction follows the request to prepare this design review.

Recommend this boundary because real Django/browser tests now establish a useful
same-process/same-address workload on both supported OSes. The strongest concern
is that ordinary application pools retain idle physical sessions: this contract
requires retiring those connections and quiescing application work before reset.
It is useful for the verified Django setting CONN_MAX_AGE=0; pool/session-preserving
live would require a different contract. Do not advertise general application or
worker reset from this evidence.

## Source identity and prior evidence

Design written from design branch source_commit
`778e6d6da05aed53455e0d18c909cee8cd7e7cf8`. Current product/runtime base is
`bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4`. Experimental consumer source is
`ab085d3c432b6b1483b7b937500b775d4a3faf53`, experiment/e2e-guest-live;
[CI40304818129](https://github.com/masahitojp/mariamem/actions/runs/40304818129)
and its [verified receipt](v06x-e2e-guest-live-evidence/ci-40304818129/assessment.json)
cover macOS arm64/Ubuntu x86_64 and Python3.11/3.14. The running relay is Python
at that source, not a Go implementation. The native app observation reference
remains original3446b5c/CI40286173347. The documented HTTP numeric-bind harness
adjustment remains explicit; application/migration/browser inputs stay fixed.

Cross-checks: [Snapshot contract](../decisions/snapshot-product-contract.md),
[routing contract](../decisions/connection-routing-contract.md),
[separate live decision](v06x-shadow-maria-entry-design.md#human-decision--live-is-a-separate-task),
[guide target](v06x-e2e-guide-target.md), [native review](v06x-e2e-native-control-review.md),
[guest result](v06x-e2e-guest-live-results.md), [whole dogfood plan](v06x-dogfood-replanned.md).

## User-facing proposal

A Live owns a stable localhost endpoint and one private mutable child. Each
successful Reset replaces the child's contents with a fresh Fork of the same
Snapshot. The Snapshot remains immutable and is not consumed by Live creation.
There is no public access to the private child, and Live has no Snapshot/Fork
method. Multiple independent Lives may borrow one open Snapshot.

Proposed Go surface (not implemented):

```go
func (s *Snapshot) Live(ctx context.Context) (*Live, error)
func (l *Live) ConnectionInfo() ConnectionInfo
func (l *Live) DSN() string
func (l *Live) Status() LiveStatus
func (l *Live) Reset(ctx context.Context, opts ResetOptions) error
func (l *Live) Close() error

type ResetOptions struct {
    DrainTimeout time.Duration // zero:5 seconds; negative rejected
}
// LiveStatus exposes State, Generation, ActiveConnections and cleanup failure.
```

Creation follows Fork's existing startup/query/shutdown options. Reset's context
covers waiting for operation admission, drain, candidate startup and commitment;
startup also respects the inherited StartupTimeout. Drain is bounded by the
smaller of context remaining time and DrainTimeout. Close/compensating cleanup
use the inherited shutdown bound even if the operation context is cancelled;
report cleanup errors rather than claiming the caller's deadline bounds cleanup.
Metadata remains readable after Close, consistent with Go Database metadata;
the endpoint is then unusable. DSN retains the current documented driver defaults.

Proposed Python surface (not implemented):

```python
with prepared_snapshot.live() as live:
    # Configure/start the application once using live.connection_info().
    for case in cases:
        wait_for_application_work_and_close_db_connections()
        live.reset(timeout=120, drain_timeout=5)
        run_browser_case(case)
    stop_application_and_close_its_connections()
```

`Snapshot.live()` creates a Live in the Snapshot's existing shared host; it does
not choose another host binary or perform an implicit cross-host handoff.
Live offers connection_info(), status(), reset() and close()/context management.
The example's application-wait function is caller orchestration, not a proposed
mariamem helper. Plain pytest fixtures can express it; no new shadow_maria marker
argument, Django runner adapter or preparation routing is part of this proposal.

Reset returns only after the new child is ready and old generation retired.
Python validates positive finite timeout/drain_timeout and sends both to the
host. It waits for the host's authoritative reset reply (no independent local
response-timeout exception while reset may still commit). Host EOF/protocol
failure invalidates the lineage as today. Any reset exception/interrupt stops
test admission until the caller explicitly retries successfully or closes it.
Generation/status are diagnostic evidence, not permission to continue after a
failed fixture setup. App exceptions remain primary if cleanup also fails.

## Ownership and baseline lifetime

Caller keeps the Snapshot open for the Live's reset lifetime. Typical nesting:
Snapshot context outside Live context, application context inside Live. Live
retains a reference to the Snapshot object/host Session, but it does not take
ownership of or silently duplicate its backing. Each admitted Fork pins backing
through startup using the existing Snapshot/baseline read-lock pattern.

Closing the Snapshot does not kill an already started child, matching existing
Fork semantics (snapshot.go:79). Subsequent reset cannot acquire that closed
baseline and returns code=closed, stage=live_precondition, closed=false for the
Live; old child/generation are preserved. No caller may admit a test after that
failed reset. Snapshot.Close never waits for an entire Live lifetime. Holding
Owned.Acquire's read lock until Live.Close would block Snapshot.Close and is
specifically rejected (internal/snapshot/owned.go:280,319).

The Go wrapper privately owns its child Database. The shared-host control
adapter privately owns a host.Server/log for each generation without publishing
ordinary database handles in manager.dbs. Both call the same Go endpoint/reset
engine. Failed or retired children stay owned until their cleanup is confirmed;
there is no deletion of the only resource reference on cleanup error. Close
returns a stable terminal error on repeated calls; unresolved resources remain
registered for host final cleanup. A Live's failure does not kill sibling DBs or
Lives. Python retains/releases its Session exactly once per Live, including
failed creation and cancellation/late reply paths.

## Go implementation boundaries

| Owner | Proposed change | Existing basis |
| --- | --- | --- |
| New internal/live package | TCP relay, generation state, admission/drain/reset/close, active workers and limits | Python prototype live.py onab085d3, ordinary Go net I/O |
| New public live.go, small Snapshot entry | Live API and private child factory over existing Fork | snapshot.go:63; mariamem.go:85,175,206 |
| internal/control/shared.go | live handle map, create/reset/status/close ops, EOF/shutdown ownership | manager/create/call/cleanup and request cancellation |
| python/mariamem/live.py + snapshot.py | Thin handle API, validation and context management | existing Snapshot/Database/Session lifecycle |
| python/mariamem/_session.py | Capability discovery, late live cleanup and closed-state mapping | request:95, _late:174; protocol2 greeting:51 |
| Tests/guide/workflow | Actual Go and Python Live acceptance, topology and resource/failure controls | existing native/guest browser inputs and strict mutation oracles |

This is a handwritten host/library addition. No MariaDB/guest patch, SQL parser,
protocol replay or generated engine change is planned. The proposed new files stay outside internal/generatedgo, so they do not belong
in its HANDWRITTEN_FILES list. If implementation later crosses that boundary,
update the canonical generation recipe before generated output. Verify existing
generation/inclusion boundaries; do not edit generated outputs or identity
ledgers to claim engine regeneration evidence that was not run.

Retain backend listeners and mysqlwire session/slot accounting unchanged. The
new stable listener forwards bytes to the current child's existing listener.
This adds a loopback relay hop, matching the observed prototype topology; there
is no new query-throughput or memory claim. Optimizing to dispatch directly into
mysqlwire is a separate change if measurements later justify it.

Reserve each accepted physical connection under the same lock that gates reset,
before outbound dial/handshake. The Go private backend adapter must expose
capacity (the current public Database backend interface lacks Capacity); update
its relevant fake backends and regression checks. Bound relay admission by the child's existing
max-connection capacity, including in-flight dials. Track only active workers;
do not retain a growing list of completed connection goroutines. Close must
unblock reads/writes/dials, join all admitted workers, retire child/listener and
report cleanup status. No new short idle timeout silently changes SQL sessions.
Both copy directions and half-close/error handling need explicit tests with
binary/prepared traffic and bounded cleanup.

## Reset state and cancellation contract

| Boundary | Action / result |
| --- | --- |
| Queued operation | Context-aware operation gate; serialized Reset/Close, responsive status. A cancelled waiter changes no state. |
| Preconditions | Validate options, baseline open and Live not closed. Reject without modifying child/generation. |
| ready → draining | Under admission lock stop new handshakes and wait for every physical client, including idle/pending handshake connections. Existing traffic can finish. |
| Drain timeout | Busy (Go ErrBusy/Python Busy), stage=live_drain; restore previous state, preserve old child/data/generation. Context cancellation before drain success likewise preserves the old generation. |
| draining → switching | With no admitted clients, start a fresh candidate Fork. New handshakes remain refused. |
| Retirement | Wait for old backend's session cleanup acknowledgment, then Close it. Keep explicit ownership until cleanup succeeds. |
| Commit | Under admission lock recheck context and closure, atomically publish ready candidate + increment generation exactly once. Release admission only after retirement. |
| Replacement/retirement/precommit cancellation failure | Close unpublished candidate with cleanup context, preserve errors, enter failed. New SQL refused; no fallback to old data. Retain any unresolved old resources for retry/final Close. |
| Failed → explicit Reset retry | Drain, require all previous cleanup resolved, fresh Fork/retirement, then ready. No hidden automatic retry/continue. |
| Any state → Close | Serialize, reject new operations, close endpoint/active transports, join workers and clean all owned children. Idempotent stable result. |

A reset context cancelled after the commit point does not undo a completed reset:
the operation returns committed success with authoritative generation. Cancel
before commit cannot publish a new ready generation. Existing control.runWith
post-call cancellation currently changes any result to an error; live_reset
needs an explicit narrowly scoped committed-outcome rule so it does not report
an already committed reset as an uncommitted cancellation. Other operations'
cancel/late-created-handle cleanup must retain current behavior. This difference
requires before/after-commit barrier tests, not elapsed-time sleeps.

Wire operations are additive live_create/live_status/live_reset/live_close.
Extend protocol2 greeting capabilities with live-v1; retain protocol2. A new
Python SDK refuses Live against a host lacking live-v1 before creating resources,
with actionable unsupported diagnostics; ordinary Database/Fork remain usable.
Creation replies contain a typed live handle, metadata, state and generation.
Both runWith's cancelled-result cleanup and Session._late must close late live
handles. shutdown idle checks and owner EOF cleanup include Live handles; final
cleanup closes Lives before baselines. No individual request kills the shared
process to meet its timeout.

Use existing Busy/ErrBusy, Closed/ErrClosed and Unusable/ErrUnusable identities.
`closed` describes the Live handle, not whether a private generation or baseline
closed. Replacement failures have code=unusable, stage=live_replace, closed=false,
state=failed and preserved underlying cause; explicit retry is allowed. Terminal
Close reports closed=true; cleanup failures remain visible. An idle connection
is busy for this reset contract even when no transaction is active. SQL errors
remain ordinary driver errors. During drain/switch/failed, new handshakes receive
a bounded unavailable refusal; they never queue for the next test's generation.

## Application boundary and limits

Reset can observe transport sessions, not the age of application work. Caller
must finish HTTP requests, stop new work and retire pools/connections before
calling it. Browser fixture waits for the action response and uses Django's
CONN_MAX_AGE=0. An old socket cannot reach a retired child, but a delayed job
opening a new socket after successful reset is indistinguishable from new-test
work at a fixed endpoint. Do not claim the relay prevents that late writer.
Background workers/queue retries and generic pooled applications remain W5/W8
work with their own quiescence or generation-token design. SQL-session continuity,
prepared-handle migration, post-startup app-state capture, app cache/auth resets
and parallel tests sharing one Live are not initial guarantees. Concurrent API
Reset/Close calls still require deterministic serialization and cancellation.

## Implementation verification and finite exit

1. Deterministic relay tests: reserve-before-dial; held idle/transaction/handshake;
   capacity refusal; two-direction binary forwarding; waiter cancellation;
   before/after-commit cancellation; concurrent reset/close; retry/cleanup
   failures; no stale admission, leaked workers, sockets or hidden child handles.
   Run the new concurrency boundary under Go race testing.
2. Control/SDK tests: missing capability; invalid options; late creation reply;
   baseline closed during startup/reset; Session retain/release; caller interrupt;
   owner EOF; shutdown with Live only; sibling operations remain independent.
   Existing control tests establish generic cancellation/EOF only, not these
   Live semantics. Test protocol resource cleanup and Python wrappers directly.
3. Real guest/browser acceptance on both OSes and Python3.11/3.14: replace the
   Python relay with public host-backed Live; retain app/migration/UI/hash pins,
   numeric HTTP startup adjustment, native row comparison, intended assertion
   failure, reset/app PID mutations and all process/directory cleanup oracles.
   Bind all new receipts to the new exact candidate.
4. Add actual Go public Live same-process app/browser acceptance; existing Go
   per-test Fork is retained as a control, not counted as proof of Go Live.
   Normal Go pool ownership must explicitly retire the app's SQL pool or use a
   purpose-authored reconnecting variant. Pin any app variant and obtain its
   native control before claiming that new workload; do not silently alter the
   original three-PID Go fixture or weaken its detector to manufacture reuse.
5. Gate both idle-held and transaction-held physical sessions; verify busy
   preserves original committed data, pending handshakes refuse during reset,
   retired old endpoint rejects access, failed reset admits no new SQL and
   explicit recovery succeeds. Raw successful cleanup must remain required.
6. Apply full changed-boundary development checks for runtime/SDK work, including
   affected public-source/generated-inclusion and unchanged ordinary Fork/SQL/
   routing ownership regression gates. Installed Go/Python consumer acceptance
   is needed for a product candidate; this source spike does not substitute for
   it. Qualification, benchmarks and release are separate decisions.

Completion is a finite matrix: all named boundaries PASS or a specifically
reviewed limitation; every FAIL/SKIP stays explicit. If Go-owned reset cannot
meet this contract without engine/session rewriting or broad Snapshot ownership
changes, return to design review with that evidence rather than extending scope.
No credible numeric implementation effort or runtime-overhead estimate has been
measured yet; the122-line prototype is not an estimate for this product work.
