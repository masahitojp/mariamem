# Accepted UCA change and residual PREPARE waits

The Human accepted UCA private-copy on 2026-11-12, including its measured P8
tradeoff. [The decision](../../decisions/uca-default-private-copy.md) separates
canonical adoption work from this investigation. **Continue under Issue140;
do not reopen Issue68 or treat this as the deferred UPDATE/UNDO case.**

The useful next question is narrower than “does another run take400ms?”:
**while a read request remains globally queued, why does no worker service it?**
The prior cap1 restriction is already removed. Existing evidence and source show
that an allowed concurrency gate does not imply a successful wake or creation.
Investigate those outcomes before changing another setting or timer period.
This source step has no new benchmark, runtime fix or natural-event causal proof.

## Existing issues and what can be reused

| Owner | Existing evidence | Treatment now |
| --- | --- | --- |
| [#154](https://github.com/masahitojp/mariamem/issues/154) | UCA initialization CPU/wall saving, bounded correctness on both hosts, adverse P8 comparison | Human accepted; canonical product assembly/integration still required |
| [#140](https://github.com/masahitojp/mariamem/issues/140) | PREPARE→page read completion; historical same-request global queue waits | Own current residual investigation |
| [PR141](https://github.com/masahitojp/mariamem/pull/141) | Adopted normal startup global concurrency | Already present in both current arms; do not propose applying it again |
| [#68](https://github.com/masahitojp/mariamem/issues/68) | Broad SQL-tail investigation, residuals transferred | Remains closed |
| [#143](https://github.com/masahitojp/mariamem/issues/143) | Historical UPDATE execution→UNDO writer-lock wait | Remains deferred; current PREPARE captures do not meet its UPDATE trigger |
| [#88](https://github.com/masahitojp/mariamem/issues/88) |8/16MiB comparison; default8MiB rejected | Historical residual trace is useful; keep current16MiB/read1 fixed |

The [old global/group partition](https://github.com/masahitojp/mariamem/blob/bcab9e6e07f9bf237c98a39eeba62cbcfd1e3997/benchmarks/issue140admission/results/README.md)
proved one completion task spent791.395ms in global dispatch, versus0.001ms in
the group, with actual queue membership and cap1 rejection snapshots.
That specific cause must not be assigned to current captures merely because the
stack class and400ms scale resemble it.

After the startup-cap intervention, the
[8MiB residual](https://github.com/masahitojp/mariamem/blob/260633b8c36078d5830983217ec2ed53a2c61920/benchmarks/issue88cappool/results/README.md)
already showed a different unresolved boundary: request3's submit returned in
5us, then initial global dequeue occurred389.421ms after submit. Its initial
stage retained **zero blocked-gate samples**. The last allowed sample, just
before dequeue, was active4−long0−waiting1=3 against cap16. A later cap16
rejection concerned the completion stage, not the initial389ms.
Sparse metadata cannot prove uninterrupted permission, but it does prevent
explaining that interval using the later rejection. Re-reading this existing
trace is more useful than repeating the old cap1 experiment.

## Additional information in the four saved current profiles

[Read-only replay](replay.py) and [compact reconciliation](reconciliation.json)
retain original hashes and independently enumerate matching-DB stacks:

| Saved capture | Pool-worker-shaped stacks | Executing tasks, parked in untimed host wait | In get_task/standby path |
| --- | ---: | ---: | ---: |
| diagnostic-0-baseline |3|3|0|
| diagnostic-1-candidate |3|3|0|
| diagnostic-2-candidate |3|3|0|
| diagnostic-3-baseline |3|3|0|

Every counted stack includes Fn16595 and task execution Fn16586; none includes
get_task Fn16594. Baseline500020e7's Fn16595 is structurally bound to the pinned
C worker_main (TLS initialization, pending-flag clear, get_task/execute loop).
Candidate stacks use the same function chain; the candidate generated worker
body was **not independently reacquired in this source-only step**, so its C
annotation is structural correspondence, not a new exact-body acceptance claim.
Both arms compile the same pinned tpool source; the experimental patch only
changes strings/ctype-uca.c and adds its prepared header.

These are three observed worker stacks at one instant, not a pool-memory census
or proof that exactly three workers existed throughout the delay. Go parked
state does not reveal the guest WAITING flag. The new result is that foreground
waiting coincides with background workers waiting, in both versions. It does
not reveal their queued request, owner, progress counters or wake history.

## Pinned source paths that distinguish the mechanisms

Upstream is the source_commit in guest/input.json:
`83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`.
Re-fetched tpool/tpool_generic.cc SHA256 is
`5aa908eba25625c652adf3df2d08723116491127bfef1d61148f2e91a8218280`,
identical to the prior authenticated source record. No declared guest patch
changes that file. Baseline generated function hashes are in reconciliation.json.

1. [maybe_wake_or_create_thread, lines790–805](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/tpool/tpool_generic.cc#L790)
   rejects when active−long−waiting > concurrency, otherwise wakes standby or
   calls add_thread. Prior instrumentation recorded this outer decision only.
2. [add_thread, lines670–738](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/tpool/tpool_generic.cc#L670)
   can still decline: max_threads, creation throttle, creation_pending, or
   thread construction failure. An outer allowed record does not distinguish
   these. Throttle is zero below4×concurrency; if current cap16 and small thread
   count are verified, throttling becomes a weak explanation, not the default.
3. [worker_main, lines517–535](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/tpool/tpool_generic.cc#L517)
   clears creation_pending after the worker-init callback, then takes a task.
   The clear itself does not re-evaluate queued work or wake another worker.
   Generated Fn16595 has the corresponding atomic clear at pool offset408
   followed by Fn16594, with no Fn16596 call. This is a source-level progress
   window worth measuring, not a claim that a flag is permanently stuck.
4. [maintenance, lines590–647](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/tpool/tpool_generic.cc#L590)
   retries progress, classifies long tasks, and may add a worker on no progress.
   Its default period is400ms; long-task threshold is500ms. Mutex try-lock can
   skip a tick. This gives a plausible source of coarse timing, **not proof that
   the observed400ms was released by a particular tick**. The foreground host
   AtomicWait is untimed. Timer initialization optimization is not shown faulty.

A possible interleaving, conditional on missing wait notification, is:
submission requests another worker while creation_pending is set; the new
worker clears that flag and takes a task that blocks without wait_begin; queued
work remains with no new submit/wait notification to retry creation until
maintenance or another event. This can occur below the concurrency cap. It is
an inference from the control flow, **not a reproduced interleaving**. Existing
workers might finish, a new submission might arrive, or wait_begin might create
a worker immediately. Those alternatives are precisely what the next trace
must distinguish. Do not turn this into a speculative product patch.

## Next finite observation and stopping point

Reuse the same shop70/Pipe/P8/cap9/16MiB/read1 fixture, initially one accepted
experimental arm. Bind its generated hook preimages afresh; never reuse old
numeric offsets without exact guards. Use existing request/park/notifier and
SQL-phase collector, adding event records at already synchronized boundaries:

- Exact request generation, submit/global dequeue/group run/completion/notify.
- The outer gate result **and actual add_thread outcome**, pending set/clear,
  worker-init begin/end, worker task start/end, worker wait_begin/end.
- Maintenance entry/lock skip/first progress action, plus actual cap and counts.
- Worker ID and current task identity; do not equate notifier with page owner.

Record bounded events without repeated full queue scanning; fail on truncation
or stale identity. Preserve mutex/atomic synchronization and record observer
cost. The missing evidence is event order, not another wall-time mean.
Suggested ceiling: one diagnostic Go build, one capture control and eight
natural suites, no retries or C build/heavy CI. Budget remains2h active including
30min tooling. If the existing collector cannot be rebound within that budget,
report that concrete gap rather than building an unbounded observer framework.

Finish when a >100ms queued foreground read is bound either to an outer gate
rejection, an inner creation/wake outcome, a runnable-but-unscheduled worker,
or a different downstream wait. If not captured, report NOT_REPRODUCED and
which event records are valid; do not silently extend the run count. A controlled
interleaving can then test the implicated branch, but its outcome must stay
separate from natural incidence. Changing a timer or admission policy requires
a subsequent small remedy decision.

## Checks and limits

The source/profile reconciliation is complete; the event observation above is
**not yet executed**. No new timing, thread-counter value, cause or fix is claimed.
The original adverse P8 evidence remains unchanged. Canonical UCA integration
is also unfinished and independent of the next tail capture.

```sh
python3 docs/reviews/issue140-uca-followup/replay.py --check
```

Replay reads pinned Git objects and works after disposable workspace cleanup.
It verifies four profile identities/counts, baseline function bodies, and the
historical same-request timing/counter arithmetic. Documentation links, Python
AST and diff checks are the relevant checks; unchanged runtime is not rebuilt.
