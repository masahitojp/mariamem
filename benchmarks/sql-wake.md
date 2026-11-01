# Issue68: the long wait is queued MariaDB work, before a WASIX notification

**Four approximately800ms COUNT tails contain a763–792ms page wait while
MariaDB's thread pool leaves work queued. Maintenance creates a worker; I/O and
completion callbacks run; the notified Go atomic wait returns within0.05–0.10ms.**
This identifies the immediate delay boundary in the observed diagnostic runs.
It does not support replacing the host futex implementation as the next action.

Recommend a small guest-side candidate addressing this pool's blocked-worker
accounting/concurrency, after identifying why its effective concurrency is1.
Keep the400ms timer unchanged initially: reducing it would conceal the queue
stall. Native parity, configuration provenance and a correction A/B remain
unverified. No production fix, native campaign or guest rebuild was performed.

## A concrete sequence

Round0/P8, instance10 (instance IDs are process-local, not child numbers):

| Event | Offset from SQL page-wait entry |
| --- | ---: |
| SQL worker enters page read wait | 0ms |
| Background worker enters another page wait with null trx | 7.470ms |
| First maintenance: queue tail365/head241, active3, standby0, waiting1, long0, concurrency1 | 368.313ms |
| Second maintenance: same queue positions, active3, waiting1, **long2** | 770.402ms |
| New worker starts | 770.512ms |
| Background page wait ends | 771.212ms |
| SQL page wait ends | 772.383ms |

At the first maintenance, the generated policy evaluates
`active - long - waiting = 3 - 0 - 1 = 2 > concurrency(1)` and returns without
waking/creating a worker. At the second, two blocked tasks have become long:
`3 - 2 - 1 = 0`, allowing creation. The source's long-task threshold is500ms,
checked by400ms maintenance; these are separate constants. The queue does not
advance between these two samples. This is a pool-local concurrency target,
**not** the harness's P4/P8 or GOMAXPROCS8.

Three existing pool workers (trace threads135/143/154) are parked during the
stalled interval; only one is accounted as waiting. The query worker146 waits
outside that pool. Background read_wait with null trx does not call the
upstream `tpool_wait_begin/end` hooks. This supplies a specific accounting
candidate; it does not establish that changing just that branch is a sufficient
or safe correction. Another blocked worker waits on a different lock.

The new worker736 performs the queued preads and completion callbacks. For the
SQL worker's address637893748 there is no notify-enter during its long wait
until1030.354ms process time. That notification reports one waiter woken;
wait-return occurs at1030.401ms, result0. Notification-to-return is0.047ms,
including the notifier's own work, scheduling and diagnostic overhead. It is
not a claim of exact kernel wake latency. The query subsequently completes and
returns the correct aggregate.

## Other observed cases

All values below are ms. The queue delay is a representative longest matched
submit→task-start interval in the same instance overlapping the SQL page wait;
it is **not** asserted to be the exact page that the SQL worker requested.

| Measured run / instance | SQL page wait | Longest overlapping queued task | Longest pread inside page-wait span | Notify-enter → wait-return |
| --- | ---: | ---: | ---: | ---: |
| round0/P8 /10 | 772.383 | 790.249 | 0.018 | 0.047 |
| round0/P8 /21 | 783.555 | 778.509 | 0.015 | 0.074 |
| round1/P8 /11 | 763.898 | 763.059 | 0.008 | 0.058 |
| round2/P8 /31 | 791.748 | 793.502 | 0.044 | 0.099 |

All four show the same two maintenance observations: active3/standby0/
waiting1/concurrency1, long0 then long2; unchanged queue positions between them;
a new worker after the second tick; subsequent notification and quick resume.
The host wait returns0 (woken), not a timeout. The read-wait call stacks include
the SQL dispatcher. Query→instance association is established within guest
stacks; we do not infer an exact client-child identity from overlapping clocks.

The six measured processes also contain three COUNT spans around111–133ms.
Round2/P4 has127.866/136.698ms page waits and a75.010ms pread; these smaller tails
are **not explained by the800ms mechanism**. The collector adds allocations,
stack walking, locking and GC pressure; these runs cannot establish a baseline
latency distribution, resource regression or speedup. Whole-process pread maxima
are in the summary; the table's narrower maxima must not be generalized.

## Which layer, and what remains unknown

- **Observed:** work is delayed within MariaDB's generated thread-pool logic,
  before the late I/O/completion task and before the corresponding notification.
- **Observed:** WASIX Futex_wait/Go AtomicWait park the live worker and return
  promptly after the eventual notification in these four cases. The old missing
  Fd_dup panic/worker-loss shape is absent.
- **Source correspondence:** simulated AIO uses pool tasks; the WASIX portability
  profile selects this route. Native Linux's asynchronous I/O route can differ.
  MariaDB maintenance and wait accounting are ordinary engine code, running here
  through the WASIX/generated-Go environment.
- **Unverified:** why the effective pool concurrency is1, which native execution
  profiles reproduce this state, and whether all required waits are correctly
  declared. `Thread_parallelism` is implemented and returns runtime.NumCPU;
  concurrency1 alone is not evidence of an unimplemented CPU-count syscall.
- **Not claimed:** all futex/syscalls correct, an upstream MariaDB-wide bug,
  a safe fix, or that every SQL tail has this cause.

The next bounded action should trace the source of concurrency1 and compare one
minimal accounting/configuration correction against the unchanged workload.
Do not add a blanket worker increase, rewrite synchronization, or merge the
instrumentation as product code. A product candidate still needs its own
correctness and uninstrumented before/after evidence.

## Fixed diagnostic scope and verification

Same v0.6.0 product source_commit
`b3b3b46a8807482ad3f96725af86e031fe369b01`, tag_object_sha
`b57183b08d48884840111e8b53daa500734337f0`, on M1/16GiB/macOS27.2/Go1.27.3,
CGO0/GOMAXPROCS8. Same TCP/1,000 integer rows/COUNT-SUM/UPDATE/independent SELECT.
P4/P8 each3 fresh measured processes,48 children each; separate48-child warmups
for each P. The fixed six runs were completed without extra reproduction attempts.
288 measured and96 warmup children pass row/isolation/cleanup oracles. The8-child
pilot, one corrupt-seed negative and one artificial150ms-delay collector control
also produce their expected outcomes and clean up.

Measured harness source_commit
`8a98449c604e0f88cf457315dbdf34a9ba5e7d93`.
A clean pinned product checkout is built with a diagnostic `go build -overlay`;
it is **not the unchanged release binary**. Seven overlay files add event logging
at pool submit/execute/maintenance/wait hooks, pread, AtomicWait/Notify and thread
entry. No timer, scheduling branch, SQL data or guest WASM is changed. All before/
after hashes are recorded. Query observers and100ms-triggered stacks remain.
Events are bounded to1,000,000/process; all processes report dropped0. Events are
written after database cleanup; none are streamed synchronously during SQL.
The collector retains module identities until exit, so RSS is diagnostic only.

Function names are structural correspondences to pinned MariaDB source
`83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`, not a newly acquired WASM debug-symbol map.
The mapping file records offsets, fragment hashes and its basis. Pool fields are
sampled inside maybe_wake_or_create_thread while its existing mutex is held.
Preads are observed at the WASI Fd_pread boundary, not physical disk requests.

[Compact evidence](forkcompare/results/compact.json),
[summary](forkcompare/results/summary.json),
[source correspondence](forkcompare/results/source-correspondence.json),
[raw archive reference](forkcompare/results/raw-reference.json).
Raw events, stacks, controls and pinned source excerpts belong to separate ref
`evidence/sql-wake-20261102`, commit
`1d1b347da2a401cc38e2ae7e63e15731902de714`,
[raw.tar.gz](https://github.com/masahitojp/mariamem/blob/1d1b347da2a401cc38e2ae7e63e15731902de714/raw.tar.gz)
(27,706,487bytes, SHA256
`efca0c9fcd29f59c6108fe70b8ac687de7bbf6eeb6bb7ffdd35c3c00d4d323cc`).
All archive member hashes and raw-event→compact→summary recomputation pass. A
wrong-summary control is rejected and check mode leaves canonical files unchanged.
No CI was submitted.

Reproduction: prepare a disposable experiment with8GiB budget/16GiB free reserve,
checkout the measured harness, clone the pinned product into `temp/product`, copy
`run.py` to `evidence/run.py`; run phases build, pilot, measure. The build checks
typed source/tag identity and clean checkouts before applying the hash-recorded
Go overlay. Analysis:

```sh
python3 benchmarks/forkcompare/analyze.py --evidence <raw-evidence-directory> --results <results>
python3 benchmarks/forkcompare/analyze.py --evidence <raw-evidence-directory> --results <results> --check
# After scratch removal, compact-only consistency/checksum validation:
python3 benchmarks/forkcompare/analyze.py --results benchmarks/forkcompare/results --check
```

The last command validates compact-summary consistency and checksums, not a
re-execution of raw event reduction. Keep that distinction explicit. Budget:
initial2h active /30min measurement tooling /0 heavy CI, within the recorded
allowance (time accounting is an estimate, not an instrumented activity ledger).
Investigation checkpoint complete; Issue68 remains open and no product correction
is accepted or implemented here.
