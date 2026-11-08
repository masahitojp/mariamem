# #128 close/drain source diagnosis

Question: can the additional archive probe observe IDLE before QUIT/EOF retirement,
and what minimal observation distinguishes that race from a runtime defect?

Plan recorded before investigation: inspect the exact e6502de producer's host
assembly inputs, guest controller patch, original capture/retirement fixtures and
public WaitDisconnected contract; preserve the raw failure and propose, without
execution, one bounded drain observation and paired follow-up. Exit with grounded
source facts, explicit missing runtime evidence and an executable test proposal;
no claim of fixing the failure. Stop partial at 45 minutes active (tooling <=10),
256 MiB owned scratch or 12 GiB free floor. No builds, downloads, Docker, SQL, CI,
benchmarks or production changes. Environment: macOS arm64, Python3.14; starting
HEAD 1c5a6d59c70f6b5e39e1e92d0f659cb3f83b59b1, clean checkout, 22.48 GiB free.
Workspace helper dry-run: no cleanup candidates/debt. Process inventory requires
read permission; no heavy task will be started in this source-only slice.

## Finding and recommendation

**Source establishes a probe synchronization gap; it does not establish the
cause of the recorded run.** Recommend combining the bounded drain observation
below with #131's selected source changes, then obtaining one paired execution
budget. Do not fix production code or rebuild a disposable observer baseline.
#128's update-cost result remains **INCONCLUSIVE**. The strongest contrary
point is that the failure log already prints `SESSION_RETIRED result=0`; that
print is earlier than worker completion/reaper join and is not retirement proof.
A genuine join/controller/runtime defect remains possible until observed.

## Exact inputs and preserved failure

Evidence base is `1c5a6d59c70f6b5e39e1e92d0f659cb3f83b59b1`; that report,
original FAIL and all previous identities are unchanged. The failing additional
probe is [the saved input](../issue128-real/target_checkpoint_test.go.txt), lines
38–42; raw [target-checkpoint.txt](../issue128-real/evidence/native/runtime/target-checkpoint.txt)
contains exactly one failed execution, not a retry campaign.

- MariaDB trial: 13.0.2, source_commit
  `620a4b5624222048fece7fe1789978ae0675cae2`, tag_object_sha
  `308a50778fb4916ddde0d2923feea3d11dcc92c8`.
- Native producer/host inputs: `e6502de0781826488c984aa5637dfe593a74799d`;
  guest `b7672dcca277ec9a1294b82ec33ab68cab578ba6244c81dc31ffe37586e0486d`;
  host `2e6949fa322677f5a2b1ba02da90489214d78c25fa18d36c12d4c3cf4a9fb014`.
- Legacy producer `ecf81035009bd4e353ddee302f73c781c77a3f28`;
  guest `1854c8106abf275e67c84b6e43a6035109021d81d3612f54d0f17baa31906214`.
  Its extra archive scenario has **not** run.
- Public preflight `fd7aea9178a0f798de4a742ddb573a877f6c1f28` concerns
  12.3.3/#127 origin `8c8b5f1c09765c9fb51c2b640ed2fc32d759fbe3`, guest
  `873c9daf38f6e7f5005dbdbdf8e920b396fe5591ab74bfedcad37b436c50d3dc`.
  No public 13.0.2 acceptance follows. #132/#134 must fix the final tuple.

[source-identities.json](source-identities.json) authenticates read source to
producer Git blobs and actual compiled template pins in
[host-build.json](../issue128-real/evidence/native/runtime/host-build.json).
The assembled capture fixture differs from its historical input by the exact
previously reviewed idle insertion in `prepared_capture_fixture` at
`issue65-p1-timeout/probe_baseline.py:34–49`; its compiled hash is recorded,
not silently treated as identical. That insertion is in another test.
The native driver uses `probe.tools` plus the recorded single-build adaptation;
this is the isolated instance/adapter route, not the newer public backend.

[controller.cc.txt](controller.cc.txt) is the complete controller reconstructed
from the producer's four sequential patch sections using `patch -p1 --fuzz=0
--batch`, with no engine checkout/build. [Reconstruction output](controller-reconstruction.txt)
has no offsets/fuzz; SHA256 `e1f09c0f274af5448e94e6c81514fd7d863a4708ce9d5aba61e53c239802c17f`
equals `wasm/issue65_control.cc` in the actual target
[prepared-proof.json](../issue128-real/evidence/native/prepared-proof.json).
Reading only its first patch section would miss later deadline/identity changes.

## Proven source trace

All repository line references below refer to the pinned producer, whose relevant
read files were checked byte-for-byte against this checkout, unless fd7 is named.

1. `dbFor` (`issue65-native-capture/wire_test.go.txt:33–62`) constructs a real
   `database/sql` pool over TCP using go-sql-driver/mysql v1.9.3 (go.mod:5).
   The driver [`Close`, connection.go:158–194](https://github.com/go-sql-driver/mysql/blob/62984ada4402df6571557bc3fed2bcbde48ec908/connection.go#L158)
   writes COM_QUIT then closes its network connection. It has no server reply,
   guest join or host retirement acknowledgement in that method. The source
   excerpt/digest is retained here; no dependency archive/cache was acquired.
2. `main.go.txt:641–759` relays client bytes as DATA; read-loop termination sends
   PEER_EOF at725. Reader and writer independently report relay completion
   (650,698). Pool closure cannot synchronize those goroutines with native exit.
   Existing relays continue during capture checking; `BeginCaptureLocked`
   rejects reserved/opening/uncertain leases, not established active/retiring
   ones (`internal/nativewire/owner.go:173–183`).
3. Controller readCb (102–105) admits a command on consuming armed input;
   admit (81) changes IDLE→RECEIVING. EXECUTE_START (98) changes to EXECUTING,
   including QUIT. Finish (82–96) waits for output acknowledgement and sets
   either IDLE or RETIRING. UNREGISTER_THD sets RETIRING (94).
   PEER_EOF (131–135) marks inputEOF; clean EOF is not itself a join.
4. `guest/experimental.patch:291–312` runs do_command, reports
   CONNECTION_COMPLETE for connection close, unregisters/cleans/deletes THD,
   prints SESSION_RETIRED and only then returns. Controller worker lambda (121)
   still must execute mysql_thread_end, set workerDone and return. Reaper (169)
   joins the worker, clears the slot, increments joined, then queues RETIRED.
   Therefore neither the stderr message nor STATE=retiring proves completion.
5. Host RETIRED dispatch (`main.go.txt:571–574`) calls nativeRetired (345–359).
   Session closure wakes relays. Owner.release (`owner.go:139–164`) frees a
   lease only with native retirement AND Reader|Writer completion. Map deletion
   occurs only when that release succeeds (323–350). Guest empty slots alone
   do not imply host lease release.
6. The actual capture helper first polls **all present phases == idle**
   (`capture_test.go.txt:22–29,163–192`), not zero sessions. The guest's
   TRY_CAPTURE gate tests again under its gate mutex (controller136–142):
   any non-IDLE slot, including RETIRING, gives code1/busy. Host returns
   consumed=false (main928–933), ending its checking state. This is the exact
   error shape of the saved failure, not host reservation ErrBusy.
7. Successful capture then fences, requests CAPTURE_STOP, stops ingress, joins
   runtime/reader/host owners and takes the root (main938–975,824–850).
   Controller captureComplete (148–151) checks cleanup reports and native joins.
   These are **post-fence** requirements, preserved by captureNow's ordering
   and count assertions (capture_test44–51). Calling root `awaitJoined` before
   snapshot would wait for the entire live root to exit and cannot repair a
   client-disconnect observation; ordinary root close cannot approve capture.

STATE is also insufficient as a history oracle: controller172 coalesces
statePending to the current phase; the host's saved events at main508–510 retain
kind/slot/generation/value but discard body (phase text). The original FAIL has
neither retirement STATS nor exact gate-time phase. Do not infer a complete
phase sequence from its stderr ordering.

## Facts versus inference

**Observed:** archive ON/OFF, redo `36889→16947841`, checkpoint `16960243`,
256 rows/16777216 bytes passed before Close. Capture returned busy/unconsumed.
Ordinary failure cleanup later logged started=joined=1, cleanup_failed=0.
Capture/freeze/restore were not reached. No timed_wait/create_spare_archive
branch-hit instrumentation was present; checkpoint progress alone proves neither
branch coverage nor restore correctness.

**Source-supported possible interleaving:** driver writes QUIT/closes TCP;
controller STATS still sees last command IDLE (perhaps QUIT bytes are queued but
not admitted); helper returns; QUIT is admitted and reaches RECEIVING/EXECUTING/
FLUSHING/RETIRING; TRY_CAPTURE sees non-IDLE and correctly rejects. SESSION_RETIRED
can print before the host logs that rejection while the slot still awaits join.
This requires no engine defect and is not contradicted by the failure. It is an
inference, not a reconstructed timeline of that run. If capture wins the gate
before QUIT admission, fencing instead prevents subsequent admission, explaining
why arbitrary sleeps or lucky repeated captures would hide the issue.

**Unknown:** gate-time phase/slot/generation; QUIT/EOF ordering relative to STATS;
time from native return to join and host relay completion; whether archive work
caused any abnormal retirement delay; whether fully drained capture and restore
succeed in either path. Normal cleanup after failure does not answer these.

## Minimal observation and comparison with successful fixtures

Use a bounded **session drain**, not IDLE and not full root shutdown: no guest
slots, started==joined, no host sessions/leases, live healthy root, with all
fixture-owned pools closed and no concurrent admissions. Guest STATS under the
gate reports every non-null slot (155); once empty, it cannot become busy without
a new OPEN. This makes the subsequent gate check meaningful. Do not require
rollback_reports==started before capture: cleanup/capture owns that distinct
oracle and the original helper already verifies it after shutdown.

The actual assembled `issue65-compat-fixes/live.go.txt:29–69` already provides
WaitDisconnected using STATS sessions=[], started==joined and host map empty.
Reuse it in the additional fixture, with a five-second context, then assert root
health/aliveness and owner count. It returns nil if r.done is closed, so merely
calling it without the health check could mistake root death for successful
disconnection. Preserve timeout as failure with state, not a larger retry limit.
[proposed-test.diff.txt](proposed-test.diff.txt) is a proposal only; no original
input/helper or executable was changed. The new additional fixture should also
log one bounded post-rejection STATS observation before failing, without another
capture attempt. Existing frame/RPC and JSON decoding suffice; no SQL/parameter
or protocol decoder is added.

Original successful fixtures deliberately test **different** states:

- `capture_test.go.txt:75–160` captures with an open idle pool and transaction,
  rejects transaction-preserving capture, then checks rollback/restore/recapture
  and session isolation. Do not replace its idle helper with disconnect waiting:
  it intentionally accepts open idle sessions. This original success cannot
  prove Close→drain synchronization in the extra archive test.
- `issue65-native-live/live_test.go.txt:125–174` proves an idle pool still blocks
  drain, closes it, then holds `beforeRetirement` to prevent generation commit.
- `issue65-p1-timeout/owner_native_test.go.txt:97–137` holds final native worker
  completion and forbids RETIRED/reuse. Lines138–188 hold the reader relay after
  native retirement and writer completion and forbid releasing the lease.
  The completion hook is installed in handwritten ThreadLifetime.complete
  before a.done closes (`lifetime_overlay.py`, exact preimage guard); foreign
  reclamation waits a.done (`internal/generatedgo/code/base/thread_lifetime.go:90–135`).
  It does not edit generated worker bodies. Original bindings remain exact.
- Public `mariamem.go:271–297` documents close-pool-first, then waits Active=0;
  legacy `internal/host/server.go:185–210` deletes clients only after Serve
  returns/acknowledges guest close. Native Backend.Active uses Owner.CountLocked
  (`internal/nativewire/backend.go:248`) and thus both retirement/relay releases.
  At fd7 these public methods have the same relevant semantics. The isolated
  native Live adapter additionally reads guest join stats; public WaitDisconnected
  is not itself a guest STATE command or full root join. Public Live retirement
  waits disconnect **then** closes its child (`internal/live/endpoint.go:355–368`).
  Python smoke similarly calls wait_disconnected before snapshot (test:29).

| Distinguishing observation/control | Expected | Actual evidence now / interpretation |
| --- | --- | --- |
| Close returns, then idle succeeds | May still have a slot; future QUIT admission can change its phase | Implied by helper success before busy; exact JSON absent |
| Added drain after Close | sessions=[], started==joined, host=leases=0, root healthy, then one successful capture | Not executed; if satisfied with no opens yet busy occurs, source invariant/identity/runtime needs investigation |
| Drain timeout | Preserve last slot/generation/phase/command, started/joined, host/lease counts and cause | Not observed; nonempty guest means native/guest retirement pending; empty guest plus host leases means relay/host ownership pending; neither alone proves permanent defect |
| Deliberately retain an open idle pool | Disconnect wait times out, while original idle-capture remains allowed | Existing Live fixture source/original PASS, no new run |
| Hold native-completion barrier | Guest not fully joined; drain must not report success until released | Existing owner fixture; distinguishes SESSION_RETIRED from actual completion |
| Hold reader relay after RETIRED | Guest may be empty/joined, host count stays nonzero; drain must wait | Existing owner relay fence; excludes a guest-only observer |
| Existing running/partial/output capture controls | busy, consumed=false, no root; source remains usable where originally required | Preserve TestCapturePartialAndOutputRejection unchanged |
| Root dies while waiting | Fail, never interpret done shortcut as usable drain/capture | Required added health negative control; not executed |

Collect existing STATS immediately after Close, on drain completion/timeout, and
on capture rejection; log monotonic timestamps, epoch, slot/generation/command,
phase/input/outstanding, started/joined, host map/owner counts, root cause and
consumed/root/error. A small in-process observer at the existing frame-dispatch
boundary may retain STATE body/RETIRED identity for this finite extra fixture if
needed; do not add another frame decoder or generated-body edits. Bound retained
observations (e.g.128 recent events, no payloads). STATS before/after alone cannot
reconstruct a transient gate-time phase; label that limit. For the distinguishing
positive case, empty slots plus no new admissions removes the transient window.
No busy-retry loop, guessed sleep, phase allowlist, gate relaxation or silent
whole-suite PASS is acceptable.

## Combined #128/#131 follow-up — proposal, not execution authorization

First review #131's contact map with this finding. Select only changes that
remove an identified internal dependency or improve its detection; movement of
lines alone is not a benefit. This worker does not preempt #131's recommendation
or modify its report/project-status. Combine selected experiment-owned inputs,
the drain observation and finite controls **before** rebuilding either path.

| Work/cost boundary | Paired requirement and current knowledge |
| --- | --- |
| Shared preparation/UCA | Same target, WASIX, prepared base/three reviewed target adaptations, UCA, compiler/sysroot/Binaryen/converter/engine/platform. Aligning shipped legacy UCA remains shared setup, not native savings. #131 identifies which shared prepared contacts could be removed and their tests; unresolved selection blocks building. |
| Native-specific | Preserve NET/THD/Protocol/controller/EOF/retirement contacts and exact whole-body/TLS/layout binding review unless a reviewed #131 change replaces them. New identities require new review; no reused old127 binding PASS. This slice proposes only observer synchronization, no native engine repair. |
| Acquisition/clean builds | Run git_identity for producer and MariaDB source_commit/tag_object_sha first; complete dependency/pre/postimage records and strict/fuzz0 guards. Prior SDK/output caches were deleted; acquisition is needed and its cost is shared. Two sequential clean guest producers maximum; record producer freshness explicitly. |
| Binding/host | Two sequential translations/host builds maximum, compile the original suites, drain controls and paired archive scenario once per path. Keep legacy/native observers appropriate to their respective declared semantics; public staging is separate. Record new artifacts, exact generated worker bodies/TLS/layout, maps, toolchain and observer SHA. |
| Runtime | Same bounded256×65536-byte workload, archiveON/OFF/4MiB log, >2log redo, checkpoint advancement, count/bytes; close pools; respective real drain; one capture; restore and exact rows/bytes, then child isolation/recapture controls. Native retains22 lifecycle/88compat/38limits/G1234/G2241 and original79 accounting. Legacy retains its original smoke/P1/P2 expectations. Common archive checks are reported separately from path-specific coverage. |
| Failure policy | First unresolved shared/semantic failure ends the run with original logs, counts and cleanup debt; no automatic retry campaign or incremental build relabeling. Missing fixtures are unavailable, not PASS. CI0, benchmarks0, consumer expansion0. |

Suggested **new authorization** envelope: active<=2h including tooling<=20min;
wall<=4h30; guest2 sequential×60min, translation/host2×30min,
finite suites2×15min, setup/acquisition/cleanup<=40min (250min total,
20min contingency within wall ceiling). This is a ceiling proposal, not approved
by this source task. Costs are estimates: prior guest commands1116/886s,
translation100/119s and compile148/232s suggest feasibility, but downloads,
#131 changes, target generated identities and failures have unknown cost. Human
investigation/binding review and compiler/link repair must be timed separately
from command/wait. Do not turn these different old cache/probe timings into a
native speedup claim.

Owned disk<=12GiB, free>=12GiB at preparation and continuously while running;
include all host/container downloads, extracted tools/source, temporary Go paths,
caches, generated/output/staging bytes. Previous guest peaks5.19/5.43GiB are
measurements, not guarantees for combined work; future host/transient overlap
peak remains unknown. Acquire shared inputs once, run heavy tasks sequentially,
preserve evidence/digests before deleting recreatable per-path output. If guards
cannot establish capacity, report blocker; never delete another workspace or
expand the ceiling. No mandatory warmed shared cache.

Archive→capture→restore acceptance requires the real drained live root, original
capture lifecycle/rollback/join/free ownership oracles, identical data after
restore, bounded child cleanup, and paired same-target evidence. Separately prove
which EOF and pagecleaner timed_wait/create_spare_archive paths the selected
workload exercises; use finite guest-side branch observations if necessary in
reviewed experimental inputs, not checkpoint progress as a substitute. If no
convincing total maintenance-cost benefit remains after #131 and this paired
result, recommend reconsidering internal contacts/placement rather than automatic
productization. Final #128 close also requires the #132/#134 candidate-difference
check; public C3 settings/fault/bothOS remain #129/#130/#132.

## Verification, cost and cleanup

[reproduction.txt](reproduction.txt) records exact source-only reads/reconstruction.
Performed: producer/template hash comparisons, strict controller reconstruction
and actual prepared-postimage match, original report/probe/FAIL byte preservation,
JSON parse, relative-reference checks, diff/status inspection. No production fix,
probe application, SQL execution, runtime generation or test run occurred. No
build/CI/benchmark/dependency archive/SDK acquisition. One small external driver
source file was read through GitHub and reduced to its relevant excerpt/hash.
The locally installed Go source was found to be1.27.3 and was not used as proof
for the recorded Go1.26.10 host.

First durable plan timestamp09:10:30 UTC; source collection/report checks reached
09:16:31 UTC on2026-11-08. Including preliminary issue/skill reads and final
publication, active work is estimated10–15min, tooling2–4min; these are estimates,
not stopwatch measurements. Command calls were short source reads, not compiler
or runtime waits. This is additional shared lifecycle diagnosis/observer work;
it is not a measured native functional repair or total-update-cost improvement.
No compiler/link fixes, binding repairs or regression fixes were implemented.

Owned new durable evidence is about50KiB. Temporary controller reconstruction
was automatically removed. The only new ignored Python helper bytecode is
removed before completion; no downloads/build/cache/staging scratch retained.
Cleanup dry-run reports no candidates/debt; checkout totals~388MiB, hence no
retained path>1GiB. Initial audited processes showed Docker Desktop infrastructure
but no issue128/build/compiler job; no Docker operation or process termination
was performed. Free space starts22.48GiB and is rechecked at completion.
Worktree lifecycle remains with Orca/coordinator. Protected parent files,
#131 report and project-status were not edited.
Final pre-publication audit: free22.43GiB; staged diff has only these seven
source-evidence files, diff --check passes, ignored-file inventory is empty.
No retained path>1GiB and cleanup debt0 within this owned checkout; other
workspaces/desktop infrastructure were neither audited as owned nor deleted.
