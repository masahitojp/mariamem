# Issue156: controlled pending-clear mechanism

**The proposed queue-stall mechanism reproduces in the pinned MariaDB native
thread pool, without WASIX or the Go shim. Attribution of the earlier PREPARE
outliers remains UNPROVEN.** Six controlled conditions, two requested concurrency
values and three repetitions all satisfy their fixed oracles (36/36). This is a
scheduler mechanism test, not a performance result or natural SQL reproduction.

Recommend one similarly controlled translated-guest test before selecting a
product fix. Keep #140/#156 open. Do not increase read threads or shorten the
maintenance interval based on this result. UCA adoption through PR157 is complete
and does not depend on this investigation.

## What this establishes

The actual upstream `worker_main`, `add_thread`, `submit_task`, `wait_begin`,
`get_task` and `maintenance` implementations are compiled, not a reimplementation
of their policy. Main baseline is `8df45792a927e440972266ee799d6f7223713e14`;
MariaDB source is `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`.
The canonical patch does not change tpool_generic.cc. Source hashes and explicit
instrumentation preimages are checked before compilation. Host is a single
macOS arm64 machine, Apple clang21; this is not a supported-platform matrix.

1. Task A submission creates worker1, which is held in its existing init callback.
2. Task B submission reaches add_thread while creation_pending is set. The actual
   refusal branch is observed; two tasks are queued, one worker is active.
3. Release init. The actual worker clears pending, dequeues A, and A blocks in a
   controlled condition wait without calling tpool_wait_begin.
4. B remains queued through the deliberately imposed 50ms observation window.
   Pending is cleared; active=1, waiting=0, long=0, dequeued=1. No capacity/max
   refusal or long-task heuristic is needed to produce this state.
5. An explicit maintenance invocation creates worker2 and B runs. Task A is then
   released, task references reach zero, and the pool destructor returns.

The actual source clears pending without a queue recheck at
[tpool_generic.cc:520–535](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/tpool/tpool_generic.cc#L520).
[wait_begin](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/tpool/tpool_generic.cc#L841)
and [maintenance](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/tpool/tpool_generic.cc#L590)
do call the progress check. The pool documents maintenance as its no-progress
safety mechanism. A caller that blocks without reporting its wait is an important
precondition; this result alone does not classify the upstream policy as a bug.

## Counterfactuals

Each row has 6 passing cases: requested concurrency1/16 ×3 repeats.
The dynamic pool uses min1/max32; fixed-pool control uses min=max2, which clamps
both requested concurrency values to2. Read-I/O task-group limits are not modeled.

| Condition | Observation | Workers created |
| --- | --- | ---: |
| Pending overlap + unreported wait, then maintenance | B held until explicit maintenance |2|
| Same overlap, A calls wait_begin/end | B progresses without later maintenance |2|
| B submitted after A starts blocking | No pending refusal; B progresses |2|
| Fixed-size pool | No pending refusal; both tasks progress after init release |2|
| Same overlap, release A without maintenance | Existing worker dequeues B |1|
| Same overlap, submit additional task C | Submission supplies the missing progress trigger |2|

The identical stalled state at concurrency1 and16 means that merely allowing more
active workers does not itself supply a new progress check. It does not measure
production throughput at either setting.

The six fixed repetition1/concurrency16 event traces are retained, without
selecting favorable timings. One example: pending refusal0.121ms, clear0.127ms,
A start0.128ms; explicit maintenance52.386ms, second worker spawn52.392ms and next
task start52.497ms. The approximately52ms gap is intentionally forced, not a
reproduction or explanation of the original approximately400ms SQL latency.

## Boundaries and next decision

The native standard library owns threads, mutexes, condition variables and
atomics. The standalone mysys timer adapter does not schedule callbacks;
maintenance is explicitly driven. We first invoke maintenance on an empty pool
to initialize its real coarse timestamp and avoid falsely classifying the first
task as >500ms long. A >250ms scheduling disturbance invalidates a controlled case.
Support headers supply only minimal configuration/debug/alignment declarations.
No SQL, InnoDB read requests, WASIX syscalls, generated-Go threads or periodic
mysys timer execution are tested. Therefore the shim is not necessary for this
mechanism, but it could still affect actual occurrence or recovery timing.

All pool destructors return, waitable task reference counts and queues are zero,
and worker destroy-callback counts match creation. Upstream uses detached native
threads; these are pool-lifetime retirement observations, not OS thread join or
whole-process resource-exhaustion proof. The original harness's `workers_joined`
label is normalized to `workers_retired` in the compact case table.

Why the earlier eight natural suites did not reproduce the tail remains unknown.
This test shows that relative ordering matters: moving B after pending clear or
reporting A's wait eliminates the stall. The earlier observer's approximately
100,000 events per process might alter that ordering, but this is a hypothesis,
not an observed observer-on/off causal result.

Next: one generated-guest control with the same two task roles and creation/init
barrier, plus reported-wait/late-submit controls. Bind its actual task and worker
identity; verify the queue state, clear and rescue event. If that control also
reproduces, then locate a real PREPARE/read blocking site that omits the wait
notification. Until that association is observed, neither a pending-clear queue
recheck nor a wait-notification change is selected for product implementation.
No further natural sampling, full matrix or guest rebuild is implied here.

## Reproduction and evidence

Execution source: `91b18b5b415cfee936df16c4aece050f69180ca6` (plan fixed before
execution). `plan.json` pins all six upstream files; fetch them from the exact
MariaDB commit into disposable `temp/upstream/tpool/`, then:

```sh
python3 scripts/git_identity.py inspect HEAD
python3 benchmarks/pool-pending-control/run.py \
  --upstream /absolute/owned/temp/upstream/tpool \
  --temp /absolute/owned/temp/native --output /absolute/owned/temp/results
python3 benchmarks/pool-pending-control/analyze.py \
  --reduce /absolute/owned/temp/results/results.json --output /absolute/owned/temp/reduced
python3 benchmarks/pool-pending-control/analyze.py --check --output /absolute/owned/temp/reduced
```

Use an owned workspace/free6GiB/budget4GiB and the existing disk guard. The runner
checks upstream hashes and exact hook preimages, compiles one small native
binary, and runs exactly36 cases with20s watchdogs. The read-only `--check` replays
the committed compact matrix/checksums and rejects five mutations (missing case,
wrong refusal count, absent stalled queue, unbalanced workers and missing trigger).
It does not depend on deleted temp or recompile unchanged code.

`results/` retains all36 compact case rows, six preselected traces, source/build
identities, input hashes, the compile failure receipt and reduction/checksums
(about16KiB). The first compile failed before any cases because the local Apple
clang default C++ include path omitted SDK headers; the second explicitly uses
the installed SDK headers. One successful native build (1.85s), one invalid
compile, no guest build, no CI and no natural SQL runs. A workspace-runner retry
was rejected before execution because its state was failed; the existing disk
guard then supervised the corrected run. No test-outcome-selected retries.
Raw build logs/upstream copies/binary/full traces are reproducible scratch and
are removed after preserving their hashes and compact conclusions.
