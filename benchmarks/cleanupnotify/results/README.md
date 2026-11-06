# Issue117: disconnect notification prototype — conditional, CPU guard failed

**Recommendation: hold unconditional adoption.** Notification removes the recurring
connection-confirmation delay and shortens cleanup in all five pairs, but batch
CPU/child increases by6.34% at the pair median, exceeding the predeclared5%
regression guard. This finite round ends without added repetitions. No main
integration, release or CPU-cause investigation is approved by these results.

The strongest objection to holding is the consistent local benefit: the wait
and cleanup thresholds pass5/5 pairs, and all selected correctness tests pass.
The guard still matters: CPU is whole-batch CPU, so the regression cannot yet be
assigned to notification itself, nor dismissed. A Human can separately choose
a bounded follow-up or explicitly accept a tradeoff; this result stays a guard
FAIL and is not relabelled PASS.

## Change and preserved boundaries

Experimental Go overlays only:

- Database.WaitDisconnected uses an optional internal backend state snapshot,
  then waits outside Database.mu on count-change, failure, completed-exit or
  context signals. The old polling path remains the same-binary control and
  fallback for backends without this internal method. No public API addition.
- Server reads client count and obtains the channel generation under Server.mu;
  final/partial session deletion and stopAccepting close that generation under
  the same lock. Waiters recheck state; close-before-select cannot lose a wakeup.
- Go guest.Process exposes a lazily created failure channel closed by its first
  recorded failure, independently of owner join; completed exit remains a
  separate signal. Original failure cause and cancellation semantics remain.
- No per-waiter goroutine or subscriber list. Database.Close, worker/mapping
  disposal and limiter lease settlement paths are preserved. Active()==0 means
  session-map removal after Serve cleanup, not full DB disposal. Close still
  supplies the later completed-disposal boundary.

Only the experiment flag ISSUE117_VARIANT=poll/notify switches the strategy.
The canonical product/guest/generated sources are untouched. The Go host manager
file internal/guest/guest.go is part of the overlay; MariaDB C/WASM is unchanged.
A production candidate would remove experiment selectors and be reviewed against
current main separately. This branch includes inherited exploratory tooling and
is not a merge-ready product history.

## Fixed source and protocol

- Product: `1862f4a89397bddfa1820d835106d3437a438cf7`.
- Measured harness: `c37d578e68b3068173a6734b38f00e11782cb123`.
- Prior observation harness: `1a2b5dc00f8f523a9f58c8fdd66065ff2d806eb0`.
- Reused UNDO observer: `2f679a14d45acf0dac98effc7172f38301f7a3b3`.
- Guest: `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`.
- Apple M1/16GiB/macOS27.2,Go1.27.3,CGO0,GOMAXPROCS8,GOGC100.
- Pipe,1,000 integer rows,48 children,P4/cap4,unchanged product settings.
  The inherited observer's argv selector is removed; no buffer-pool flag changes.
- Same binary for both arms; identity, clean tree, binary/guest/overlay hashes
  and buildinfo are retained. Before-build git_identity.py checks passed.
- Five ordinary alternating pairs (240 children/arm), separate ordinary warmups
  (48/arm), one diagnostic process per arm (48/arm), wrong-seed1-child controls
  per arm:16 processes, no extra measurement repetitions. Compiler/test activity
  stopped before timing. No previous cohort is used as this A/B's baseline.

Primary mode disables holder/phase-detail logging but retains cleanup stopwatches;
reused generated observer hooks are present as no-ops in both arms. This is a
same-binary strategy experiment, not pristine shipping-binary absolute timing.
Diagnostic mode separately enables cleanup details and the prior UNDO observer.
Root preparation/capture and final Snapshot.Close are outside batch timing but
executed and cleanup-checked. All SQL/pristine/update/affected-row/value/isolation,
active-child cap and owned-temp cleanup assertions pass; both wrong-seed controls
fail as intended and dispose. Lifetime peak RSS is raw process high-water mark,
not retained-child RSS or a resource acceptance campaign.

## Local timing result

Pooled per-child medians across240 primary children/arm, milliseconds. Independent
phase medians do not add exactly to the cleanup median.

| Phase | Poll | Notify |
|---|---:|---:|
|Connection/pool Close|0.0074|0.0096|
|WaitDisconnected|5.1206|0.0883|
|Database.Close|3.0691|4.9214|
|Complete cleanup|8.3176|5.0129|
|Fork|33.1240|32.9234|

The entire5ms wait is not a5ms net cleanup gain: DB Close itself becomes longer.
Earlier entry into Close can move previously overlapping work into that interval,
but this is a hypothesis, not a measured attribution. The CPU increase likewise
is not proven to be notification-instruction cost.

| Pair | Wait p50 reduction ms | Cleanup p50 reduction ms | Batch wall reduction % | Batch CPU/child reduction % |
|---|---:|---:|---:|---:|
|0|4.9609|3.6624|-48.33|-5.03|
|1|5.0135|4.1173|8.20|2.91|
|2|5.0099|2.8128|3.74|-6.34|
|3|5.0598|2.4991|-5.98|-6.89|
|4|5.0613|3.4128|30.12|-12.65|

Positive means improvement. Predeclared gates:

- Wait >=3ms and cleanup >=2ms in >=4/5 pairs: **PASS,5/5 each**.
- Pair-median batch wall regression <=5%: **PASS**, median reduction3.74%, but
  directions are mixed (three shorter/two longer); no stable suite speedup claim.
- Pair-median batch CPU/child regression <=5%: **FAIL**, increase6.34%; four of
  five pairs consume more CPU. Whole batch CPU includes Fork, SQL and cleanup.

All primary observations:

| Arm / rep | Batch ms | CPU/child ms | SQL block >100ms | UPDATE >100ms |
|---|---:|---:|---:|---:|
|poll /0|613.721|57.418|0|0|
|notify /0|910.344|60.309|1|0|
|notify /1|572.746|61.692|0|0|
|poll /1|623.876|63.538|0|0|
|poll /2|619.216|62.595|0|0|
|notify /2|596.046|66.564|0|0|
|notify /3|1300.828|67.209|1|0|
|poll /3|1227.380|62.876|1|1|
|poll /4|834.493|59.784|1|0|
|notify /4|583.169|67.347|0|0|

Two long SQL blocks per primary arm remain in the dataset. Poll r3 child31
contains UPDATE806.750ms (SQL block809.465ms); poll r4 child1 has SQL795.417ms
but UPDATE0.452ms. Notify r0 child7 and r3 child37 have SQL805.787/815.082ms
with UPDATE0.392/1.106ms. Primary holder logging is disabled, so no holder is
assigned retrospectively to those events. Neither a tail-frequency improvement
nor Issue68 resolution is claimed; no outlier or process was removed.

## Requested holder/waiter logs

[holders.csv](holders.csv) provides a readable subset of all96 diagnostic traces:
wait registration/100ms owner samples and the purge hold/release scopes relevant
to background page waits. [summary.json](summary.json) retains parsed waits;
undo-traces.tar.gz retains every original event, including unmatched fast scopes.
undo-SHA256SUMS.json binds all96 archive members. No trace was truncated:
maximum3,090 events/child against8,192.

- 25,344 completed purge rseg hold scopes, zero aborts, five query rseg waits,
  one background header-page atomic wait; no matched UPDATE/purge/page chain.
- Poll diagnostic child36: purge guest-TLS609516256 holds rseg17881408 and waits
  for header space1/page3. Entry sample owner is FOR_IO /WRITE_FIX; registered
  to resumed wait0.470208ms. This is a point-in-time owner sample, not proof of
  continuous I/O ownership or physical-disk delay.
- No diagnostic UPDATE exceeds100ms (max4.163ms poll /6.140ms notify). Poll
  diagnostic child30 has SQL392.783ms but UPDATE0.290ms; the UPDATE-specific
  observer does not establish the cause of that other SQL interval.
- Two IO owner snapshots occur in selected logs; they are not two independent
  background waits. Owner thread IDs and guest TLS values are distinct domains;
  threads are not OS process IDs. Join identities only within the same trace.
- Session confirmation gap in diagnostics: poll p50 5.169375ms, notify
  p50 0.002625ms. Notify uses no periodic timer. This corroborates removal of
  the confirmation delay; diagnostic performance is not mixed into primary A/B.

No additional run or collector was added to seek a long event. The stopped UNDO
investigation remains stopped; these are diagnostics accompanying this comparison.

## Correctness and verification scope

Normal tests pass for root/host/Go guest manager: active connection cannot return
success, context cancel/deadline preserves healthy DB state, eight waiters,
partial disconnect, disconnect-before-select, concurrent Close, failure before
owner join, joined exit, stable channel generations, first-failure/idempotence
and original cause. Existing worker-trap-before-completion control passes.

Host-focused race tests pass for those packages. Generated code under
internal/generatedgo/code/... is explicitly compiled with -race=false, while
root/host/Go guest manager and their other dependencies remain instrumented.
The initial broad generated-code race build was stopped during compilation;
its stop helper reported a group-kill PermissionError, and subsequent process
inventory confirmed zero members of the old group before continuing. This is
not a runtime test failure or full generated-engine race PASS. race-scope.json
and race.py retain the selected command and exact limitation.

Reused UNDO/owner/release-order collector units and actual-Exec observer controls
pass. Analysis mutations reject incomplete/invalid primary evidence and wrong
child/rseg/address/scope/thread/page/overlap joins. Runtime failure/Close controls
are deterministic controlled-owner tests, not a full both-platform failure
campaign. No Ubuntu performance or product acceptance is claimed.

## Reproduction and stop

`PYTHONDONTWRITEBYTECODE=1 python3 analyze.py --check` recomputes summary/children/
holders from this directory and the archive read-only. Run test_analysis.py and
test_undo.py for reducer controls. SHA256SUMS.json covers all retained files
except itself; all raw trace member hashes are separately verifiable.

For fresh execution, create a disposable workspace at exact measured harness,
copy ../plan.json, ../build.py, ../run.py and this race.py into evidence/, run
build.py, race.py, then run.py under the recorded budgets/toolchain. run.py refuses
to repeat a started protocol. No deleted binary/cache/temp inputs are needed for
analysis replay. Any rerun creates new observations.

The finite prototype is complete with a CPU guard FAIL. If continuing, choose a
bounded CPU/overlap investigation or accept a documented tradeoff separately;
do not add repetitions until a PASS appears. A reviewed production candidate,
both-platform correctness, main integration and release retain separate gates.
