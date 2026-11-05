# Issue #65 — 3D stopped-root Snapshot/Fork design

2026-11-06. Design continuation selected by the Human after 3C. No runtime
implementation, adoption, release or external issue update in this task.

**Recommendation:** keep the existing stopped-filesystem Snapshot and fresh-runtime
Fork. Add a guest-authoritative capture fence and a correlated capture shutdown;
do not copy THDs, NET buffers, Go goroutines or client connections. The decisive
reason is that the existing bound-root capture already runs after all generated
workers join. The strongest objection is that 3C proved only fresh execution:
rollback, restore validation and failure ownership still require real execution.
Proceed with one bounded capture/Fork proof before Live or consumer qualification.

## Basis and scope

Inspected source_commit `402cd68a9625a676f5ccaf83c47fdf7819bdd2da` on
experiment/issue65-native-packet. The executed 3C guest source is separately pinned
in [3C evidence](../../../benchmarks/spikes/issue65-go-wire/README.md); this design
is not relabelled runtime acceptance. The [original design](README.md) remains
historical. The [Snapshot product contract](../../decisions/snapshot-product-contract.md)
and the inspected branch's public Snapshot/Fork/Live ownership rules remain the
constraints, including the finite-Fork/capture-debt work recorded in project-status.
That work's main-integration state is not changed by this experiment.

Question: can the native endpoint preserve consuming Snapshot, reversible
precondition rejection and independent fresh children without a host MySQL parser?
This task's exit is a source-grounded state/ownership design and a costed next
proof, not a claim that capture works. Initial active-work budget2h, tooling30min,
heavy CI0; docs-only workspace1GiB/free floor4GiB. No SDK, build or benchmark.

## Reuse and actual gaps

| Source boundary | Reuse / required change |
| --- | --- |
| internal/host/heap_snapshot.go: SnapshotHeap | Retain RequestCapture, joined finish, TakeRoot and OwnRoot ordering; replace the old host session precondition with a guest control transaction for this endpoint |
| internal/generatedgo/runtime_instance.go: executeGuest/startInstance | Reuse WaitThreads before FreezeRoot and descriptor/memory release; do not mistake early worker failure or native DONE for joined runtime completion |
| internal/prepared/root.go: Capture/TakeRoot; internal/generatedgo/code/base/heap_snapshot.go: FreezeRoot | Reuse pre-bound source/build identity, seal/layout checks and single ownership transfer; no new public snapshot format or file-copy path proposed |
| benchmarks/spikes/issue65-wasix-link/control.cc | Existing gate, published status, ACK-held command leases and native worker reaper are useful; QUIESCE is not capture shutdown, has no capture-ID replay handling, and still accepts DATA after fencing |
| benchmarks/spikes/issue65-wasix-link/bootstrap.inc | Currently rejects restore and always runs fresh routine bootstrap; add explicit fresh/restore selection and validate restored routines before READY |
| benchmarks/spikes/issue65-go-wire/runtime_wire.go.txt | Explicitly rejects capture/restore/transfer; extend only for a separately identified experimental lifecycle profile |
| benchmarks/spikes/issue65-wasix-link/control.cc: main | Remove unconditional effects-table creation and post-STOP diagnostic SQL from the capture path; they are fixture behavior, not quiescent shutdown |
| benchmarks/spikes/issue65-go-wire/main.go.txt: close | Currently closes TCP peers before sending STOP; capture needs its own ordered owner-stop path |
| snapshot.go, internal/host/disposal.go, live.go, internal/live/endpoint.go | Preserve consumed/error reporting, retained disposal ownership, finite reservations, permanent capture debt and Live's physical-connection drain/commit rules |

Do not switch the production wire/Server wholesale or delete its implementation
for this proof. A legacy green Snapshot/Live test runs the old endpoint and cannot
qualify the new one. No claim that a single capability toggle closes these gaps.

## Two locks and one irreversible boundary

Host owns listener/Pipe admission, relay queues, transport cancellation, capture
intent and disposal ownership. Guest owns the authoritative SQL admission gate,
command phase, actual owner-published transaction status and worker retirement.
Host state notices are observations, not permission to capture. No host lock is
held across a control RPC, blocking relay write, THD kill or runtime join.

Proposed host states:

```text
RUNNING -> CHECKING -> RUNNING                  known precondition rejection
                   -> CONSUMED -> CAPTURED      fence + shutdown + owned root
                               -> FAILED       any failure after consumption
                   -> FAILED                   uncertain control outcome
```

Host closes new-attach admission while CHECKING but keeps existing transport and
ACK pumps running. Both TCP and Go Pipe use this admission lock; waitgroup Add
must be fenced before any Wait. A busy/transaction rejection returns consumed=false
and reopens attach. Successful fencing consumes the source. A timeout, partial
control write or lost reply after the request might have reached the guest is
ambiguous: return consumed=true, stop admission and retain cleanup ownership.
Only provably unsent cancellation or a correlated definitive rejection is reversible.

Guest states are RUNNING -> FENCED -> STOPPING -> STOPPED, or FAILED. Under the
same gate used for command admission, TRY_CAPTURE rejects every non-IDLE session
(handshake, RECEIVING, EXECUTING, FLUSHING or retirement), then rejects active
transactions unless rollback was requested, then atomically sets FENCED. Queued
but not yet admitted bytes cannot turn into SQL after this point. Final native
dispatch also checks the fence before executing; it does not synthesize responses.

The first-byte lease needs an explicit audit of NET's already-buffered input:
3C's admission callback is in readCb, so a future packet satisfied entirely from
NET storage must not bypass busy/deadline accounting. This design does not claim
that such a bypass was reproduced. Test fragmented and concatenated commands;
if needed put a small admission hook at native NET's actual buffered-input
consumption boundary, plus the dispatch check. Do not parse headers in Go or mark
an idle worker busy merely because it is waiting inside do_command.

## Capture transaction and ordering

Message names below are proposals, not assigned public opcodes. Version the
private lifecycle profile in READY and bind it to the expected guest build;
reject unsupported profiles. Keep normal DATA opaque. Each capture operation has
(instance epoch, capture ID, request ID); session frames also retain generation
and monotonic offsets. One accepted capture latch/result per instance suffices:
duplicates report the same outcome, never perform another capture. A definitive
rejection needs a new operation ID to retry. Stale/mismatched replies cannot
reopen admission or deliver a root; no unbounded request-history cache is needed.

1. Host enters CHECKING, sends TRY_CAPTURE(rollback), and continues draining output.
   Guest performs the atomic checks above and returns REJECTED(reason) or
   FENCED(capture ID). A normal output ACK means bytes were written to the client
   transport, not that the application consumed them. Unacknowledged output is
   busy and cannot be silently discarded to make the precondition pass.
2. On a matching FENCED, host marks consumed and requests the already-bound
   prepared.Capture **before** sending CAPTURE_STOP(capture ID). Existing normal
   Close/STOP and private-channel EOF cannot substitute for CAPTURE_STOP.
3. Guest accepts CAPTURE_STOP only for the latched fence. It marks expected owner
   shutdown and emits CAPTURE_STOP_ACCEPTED before waking/cancelling Vio waits.
   Host stops session ingress and
   closes client sockets only after that acceptance; keep the private pipes and
   output/control reader alive until final replies and runtime completion drain.
   After FENCED, late DATA is discarded/rejected as expected stopped input without
   queue growth or a new poison cause. Late peer EOF/output errors cannot undo the
   fence or overwrite an earlier failure. No new SQL/diagnostic work is admitted.
4. Each owner cleans up its statements and transaction, unpublishes THD safely,
   destroys NET/Vio/THD and exits. The reaper joins all session workers before
   releasing slots. Stop/join coordinator timer/killer/reaper helpers in their
   dependency order, then call engine shutdown. Idle prepared sessions are allowed
   at capture admission, but statement IDs and session variables do not survive.
5. Emit a matching CAPTURE_STOPPED receipt only for that capture and successful
   lifecycle shutdown; flush/join the mux writer, then return from the guest root.
   Unexpected private EOF, ordinary STOP, poison or engine/cleanup failure cannot
   masquerade as this receipt. Native started==joined alone is insufficient.
6. Generated execution joins **all** translated workers; only a successful capture
   shutdown may FreezeRoot. Add a per-instance, one-shot capture-disposition channel
   to the experimental adapter: the continuing host reader validates the matching
   CAPTURE_STOPPED receipt and supplies approval or failure. After executeGuest
   successfully joins, the adapter requires that approval before FreezeRoot.
   Cancellation/transport failure resolves the disposition as failure; it never
   approves on EOF. Do not wait for reader exit here: that reader normally exits
   after runtime completion, which would create a cycle. A receipt can arrive
   before runtime join, but cannot authorize early freeze. Merely removing the
   fresh-only guard and relying on a nil root error is insufficient.
   The host waits for completion and reader/relay joins, then TakeRoot
   and OwnRoot exactly once. Publish the baseline only if every boundary succeeds.

Capture failure discards any pending root and returns no baseline. Preserve the
first cause while attaching cleanup errors. Context expiry does not authorize
releasing memory/maps still used by non-cooperative workers. Retain one disposal
owner; keep capacity reserved while cleanup is incomplete. If failed capture
ownership cannot be released, preserve the existing permanent capture-debt latch;
ordinary Close/retry/Live Reset must not clear it. No default snapshot timeout or
new cancellation promise for the existing non-interruptible seal is introduced.

Rollback=true permits a fenced active transaction; it does not permit busy SQL
or silently commit. Use owner-thread native transaction cleanup. Inspect its error
reporting before implementation: a void cleanup/shutdown call is not by itself
proof of successful rollback. Confirm on restored InnoDB rows that committed
writes survive and uncommitted writes do not; inject cleanup/shutdown failure
and require no baseline. The MEMORY effects table from 3B/3C is unsuitable as a
persistent-data oracle; this is stopped-file capture, not engine-RAM cloning.

## Fork and Live boundaries

Fork acquires the existing finite lease and pins the baseline through startup.
Map its bound prepared entries at mariadb in a new filesystem/runtime; allocate
new epoch, gates, workers, session generations and transport. Set explicit restore
boot mode, validate routine schema/keys through the normal bootstrap, close that
private bootstrap connection, then publish READY. No fresh-only CREATE/repair
or effects-table fixture runs against restored files. Invalid restore fails
before any client admission. No THD, SQL statement ID, socket, NET buffer, timer,
mutex or pending request is restored. No dependency on the source runtime remains.

Reuse existing child COW ownership and baseline Close behavior: admitted children
remain usable, new Fork fails after Close. Child Snapshot uses the same lifecycle
again. Preserve lease settlement through successful startup, rejected capture,
consumed capture and failed disposal; capacity counts resources, not just listeners.

Live stays a later adapter over these children. Keep the stable opaque relay,
reserve replacement capacity before draining, require **all physical connections**
(including idle pools) to close, wait for backend retirement and preserve the
existing generation commit point. Busy drain rejection preserves the old child;
replacement failure blocks SQL until explicit recovery. Do not migrate sessions
or turn Live Reset into Snapshot of the current child. Shared-host crash domain
and cleanup/capture-debt rules remain unchanged.

## Next proof, detection and limits

Recommend **3D.1 only** next: one stopped-root capture and fresh Fork route in the
isolated generated-Go endpoint, with the necessary fence/failure controls below.
Initial2h active/tooling30min/heavy CI0, owned12GiB/free floor12GiB; estimate one
LLVM23 guest build plus Go translation/compile and seconds-scale cases. That is
a cost envelope, not a promise of completion. Stop within budget with the exact
missing evidence if lifecycle error reporting or binding changes cost more.
Do not couple it to Live integration, host-controller relocation or benchmarking.

| Required observation on the actual native endpoint | Existing anchor / what it does not establish |
| --- | --- |
| Busy, partial-input and held-output rejection leaves DB usable; transaction rejection preserves connection/state | host/server.go:snapshotPrecondition is old host authority; 3B is native-only; 3C did not capture |
| Queued/NET-buffered INSERT racing the fence has no post-fence effects; deterministic gates, no sleep-only race oracle | 3B HOLD/count oracle is useful, not generated-Go capture proof |
| Idle prepared session retires; rollback=true excludes uncommitted InnoDB row; committed row survives | 3C prepared/deadline join is useful, not transaction persistence proof |
| Native joins/engine shutdown/translated WaitThreads precede freeze; host transport drain and relay joins precede acquisition | runtime_instance_test.go:TestControlledGuestJoinBeforeCleanup covers existing runtime ordering, not the new capture receipt |
| Two restored children have independent writes; baseline Close preserves children; modified child can capture again | tests/godefault/memory_snapshot_test.go is the old route; rebind equivalent workload to the spike |
| Lost/duplicate fence/stop reply, cancellation on each side of fence, ordinary STOP/EOF and early worker failure return no invalid baseline | Existing Capture source/substitution tests protect root ownership, not this new control protocol |
| Failed/non-cooperative cleanup retains ownership and capacity; no early release or forgiven capture debt | internal/host/disposal.go and public snapshot.go are behavior to retain, not coverage of a new adapter |

A successful macOS3D.1 would justify a separately costed Linux x86_64 repeat and
3D.2 Live/reservation/debt proof, then declared consumer/profile acceptance.
Those stages remain unexecuted. Auth/capability compatibility, fatal wire
cause disposition, prepared edge cases and 17th-connection behavior from the
original design remain adoption conditions. No performance, race-freedom,
full-client compatibility or production readiness follows from this design.
