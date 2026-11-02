# Issue #68: read1 wait-accounting prototype and queue distributions

2026-11-02. Human authorized the minimal experiment with acceptance based on
queue-delay distributions, **not disappearance of400ms events**.

**Partial distribution improvement; the conservative preregistered gate remains
inconclusive.** The source patch corrects null-trx waiting notification in the
prototype, passes controls and all288 child oracles, and improves per-task
p50/p95/p99. Uniformly weighted per-child worst-queue p50/p95 improve, but p99
does not. Keep the patch/evidence as an experimental candidate; do not regenerate
or integrate it as an accepted standalone resolution yet. The next focused
question is the remaining active pool tasks in captured long cases, not another
I/O setting change.

The strongest argument for advancing is the real source omission, verified
accounting effect and improvement in2/3 paired tail comparisons. The objection
is the unconfirmed top of the DB-level distribution and the prototype boundary.
Three pairs cannot establish a population regression or a stable speedup. The
hold is driven by the **distribution gate**, not by a rule requiring every
long event to disappear. A Human can separately accept a partial-improvement
tradeoff; this report does not silently change the gate after observing data.

## Minimal source change and prototype boundary

[guest/experimental.patch](../guest/experimental.patch) moves only
`tpool::tpool_wait_begin/end()` outside the two `if (trx)` blocks in pinned
`storage/innobase/buf/buf0rea.cc`. THD notification and statistics remain guarded.
The exact preimage accepts the patch and its postimage hash matches the retained
source correspondence. Canonical guest/source.patch is unchanged.

[wait_notification.cc](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/tpool/wait_notification.cc)
checks TLS pool membership before dispatch. The
[generic pool methods](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/tpool/tpool_generic.cc#L841)
guard non-worker/long-task begin and clear waiting only when marked. These are
source guards, not an assumption that every guest thread is a pool worker.

For this small comparison, the source patch's **normal-path equivalent** is
implemented as a generated-Go overlay of Fn16786. One binary selects baseline or
fixed at process startup. Fixed adds the two actual generated wrapper calls
Fn16582/16583 around the null-trx lock function Fn16623. Original generated body,
including non-null behavior, is byte-identical; baseline falls through to it.
Normal exceptional-state termination handling is mirrored, but this is not a
general exception/abort proof. A canonical patched WASM and regenerated candidate
have **not** been built; the prototype cannot qualify a release artifact.

## Preregistered acceptance and metric definition

[account-plan.json](forkcompare/account-plan.json) was committed before build.
Product-default read1 stays fixed (write2/purge1/nativeAIO0); no cache/pool-timer
change. Fresh-process order is baseline→fixed, fixed→baseline, baseline→fixed.
Each process runs48 children at parallel8 using the same1000-row Snapshot,
closed root, TCP SQL, independent mutation and cleanup.

One task delay is timestamp at submit_task **entry** to worker task_start. It
includes acquisition/enqueue contention and is not a pure post-push timestamp or
physical I/O latency. This is the same operational metric in both variants.
In the selected long case, submit returns after10.980ms and task start remains
delayed another782.883ms; enqueue contention alone does not explain that case. Root tasks are
excluded from the primary child distribution. Each child's largest executed-task
delay yields one sample:144 per variant. Per-task results are also retained,
but task volumes differ and many tasks share one stalled DB; they are not
independent trials. Censored/unexecuted child submits are0 in both variants.

The conservative gate requires functional/controls/accounting/censor success;
pooled per-child maximum p50/p95/p99 non-worse, with strict p95 or p99 improvement;
and non-worse p95/p99 with at least one strict in2/3 pairs. Quantiles are median
for p50 and sorted floor(p×(n−1)) for p95/p99. Maxima and threshold counts remain
visible; no400ms disappearance condition is used. This is descriptive finite
prototype acceptance, not a statistical confidence claim.

## Distribution results (ms)

| Distribution | Quantile | Baseline | Fixed |
| --- | --- | ---: | ---: |
| Per-child maximum queue delay, n144 each |p50 |9.501 |8.123 |
| |p95 |21.909 |20.129 |
| |p99 |776.228 |785.566 |
| |maximum |785.919 |804.402 |
| All child tasks, n81,584 /70,814 |p50 |2.419 |1.485 |
| |p95 |13.302 |11.233 |
| |p99 |769.374 |390.065 |
| |maximum |785.919 |804.402 |

| Queue threshold exceedances | Baseline | Fixed |
| --- | ---: | ---: |
| Children with max >10ms |70/144 |55/144 |
| Children with max >100ms |5/144 |4/144 |
| Children with max >500ms |4/144 |3/144 |
| Tasks >100ms |1168/81,584 |864/70,814 |
| Tasks >500ms |876/81,584 |580/70,814 |

| Pair | Baseline child-max p95/p99 | Fixed child-max p95/p99 | Tail support |
| --- | ---: | ---: | --- |
|0 |19.480 /24.892 |20.129 /26.590 |no |
|1 |20.203 /403.399 |14.014 /401.240 |yes |
|2 |20.258 /776.228 |19.625 /25.873 |yes |

The mechanism/controls/censor gate passes and2/3 pairs support the tail. Pooled
DB-max p99 is about1.2% higher, so the preregistered non-worse distribution gate
is not met: `INCONCLUSIVE_OR_REGRESSION`. The values do not prove a population
regression; neither may the p99 be discarded to declare acceptance.

Secondary observations: batch CPU median4013→3987ms; lifetime process peak RSS
median766.3→739.8MiB. These are3-process observations, not resource equivalence
or a v0.7 resource campaign. Batch values are637.7/972.6/1258.3ms baseline and
1084.4/885.5/880.6ms fixed. Wall time is not the acceptance condition.

## Functional and accounting verification

All288 children pass rows, independent UPDATE/SELECT, unchanged effective
settings, Snapshot/root lifecycle and cleanup. All6 traces have dropped0,
bijective root/child binding and no censored child task. Routine stacks and
AtomicWait/Notify hooks remain absent. Triggered stack capture is disabled in
both variants to keep this paired observation symmetric.

Controlled generated-function fixtures cover actual Fn16786 and wrapper calls:
null-trx begin/end0/0 baseline→1/1 fixed; non-null stays1/1; no-pool and actual
long-task guards pass. They use controlled memory/callbacks, not a full guest
error-path or arbitrary-application test. Both control binaries are bound to the
same clean source and overlay as the SQL binary.

Across root+children, fixed records123 null-trx read scopes and123 matched new
accounting spans; no already-WAITING entry was seen. In47 scopes a real pool
waiting-state observation appears on the same worker during the new accounting
span. Non-null code is unchanged and receives no new null-accounting span.
This demonstrates the added notification's reachability and normal-path balance;
it does not establish a universal nesting or interruption property.

Gate controls reject an unbalanced control receipt. A synthetic distribution
improvement with400ms-plus COUNT still present is accepted by the gate, confirming
that it does not secretly test disappearance. Synthetic controls are not runtime
performance evidence.

## Captured residual cases: a different limit of this patch

The supplemental decoder is **post-hoc attribution**, not a replacement gate.
Fixed process0 child20 has COUNT796.335ms, read_wait788.382ms and a queued task
waiting793.862ms. The first maintenance about381ms after COUNT begins sees
active3/standby0/waiting1/long0/concurrency1 and rejects2>1. Around785ms the
next sees long2 and permits progress. Other fixed cases show the same shape.

The new accounting marker on that slow query read has worker-data pointer0;
no generic-pool task_start occurs on that query thread in the process trace.
The query thread belongs to the DB's guest thread manager but is **not** one of
those generic-pool workers; the guarded wait API is a no-op there. The patch
works on other pool callbacks, but this single call cannot compensate the two
remaining active workers. Their precise CPU/lock/wait state is not identified
by this scalar trace, so do not declare another unreported-wait site proven.

This is a useful boundary: the real omission is corrected in the prototype,
yet it is not established as the sole driver of the captured worst queue stalls.
The read1 clamp/accounting model is consistent with the data; attributing the
entire earlier read4 27% batch observation to this one call site remains unproven.

## Identities, artifacts and reproduction

Product v0.6.0 source commit `b3b3b46a8807482ad3f96725af86e031fe369b01`;
tag object `b57183b08d48884840111e8b53daa500734337f0`. Measured harness
`bbd60290f1511f2cb54f90599678cb76af9877bd`, verified clean with source/tag checks
before build. Go1.27.3, macOS27.2 arm64, Apple M1/16GiB, GOMAXPROCS8, CGO0.
Same SQL binary for both modes, SHA256
`9f76936fc5c6e9659281586e909189334793534b29fea84842bab6b150186f97`;
control binary
`d0bf140302c18bc0563b0b60913b92fb30608b64fdc734c7f849f6cce16c7898`.
Generated-function naming is structural source correspondence, not new WASM
symbols. Canonical WASM identity is not relabeled as a patched guest.

[Compact](forkcompare/results-wait-accounting/compact.json),
[summary/gate](forkcompare/results-wait-accounting/summary.json),
[source correspondence](forkcompare/results-wait-accounting/source-correspondence.json),
[original-body equivalence](forkcompare/results-wait-accounting/equivalence-check.json),
[controls identity](forkcompare/results-wait-accounting/controls-identity.json),
[gate controls](forkcompare/results-wait-accounting/analysis-verification.json),
[secondary observations](forkcompare/results-wait-accounting/secondary.json),
[supplemental cases](forkcompare/results-wait-accounting/supplemental-waits.json),
[selected case check](forkcompare/results-wait-accounting/selected-long-case-check.json),
[raw reference](forkcompare/results-wait-accounting/raw-reference.json),
[checksums](forkcompare/results-wait-accounting/SHA256SUMS.json).
Compact retains all144 child maxima per variant and exact per-task summaries;
individual per-task samples stay in raw. Compact-only checks recompute the primary
gate; full per-task percentile reproduction requires raw reduction.

Raw: commit `68e000f870b1e5651a6ae9bd9778bd3255a96a48`, ref
`evidence/wait-accounting-20261102`, raw.tar.gz11,337,472bytes, SHA256
`6630ee6c62bd074f67bfd42e73ba79b90817d36c5441d20ec36213124c68ed81`.
The953members preserve full events/reports, source/control receipts and pinned
upstream files, with original/published hashes for workspace-prefix normalization.
No raw event forest is added to the report branch.

```sh
python3 benchmarks/forkcompare/analyze-accounting.py --results benchmarks/forkcompare/results-wait-accounting --check
```

Extract verified raw and use --evidence <directory> with a new --results
directory to reproduce the entire reduction. Compare summary.json byte-for-byte;
compact provenance paths and original/published file hashes differ by the
recorded prefix normalization, while all numerical reductions match. inspect-accounting.py reproduces supplemental attribution from that
raw directory. A fresh runtime experiment at the measured harness copies
account-run.py to evidence/run.py with pinned product at temp/product, then runs
--phase build, --phase controls, --phase measure. New observations need new
receipts. The original source-bound receipts are never relabeled.

The fixed six-process comparison is complete; no extra repetitions to obtain a
pass. Source and generated normal-path prototype are implemented on the
experiment branch only. No canonical guest regeneration, Ubuntu/native run,
main adoption, qualification, version change or release is performed.


## Final bounded worker attribution — investigation segment stopped

The Human limited the last follow-up to at most one hour, existing traces first,
at most one additional runtime observation if needed; no repeated capture,
new parameter search, guest build or both-host acceptance. Existing traces were
sufficient to identify the remaining observation boundary, so **no additional
DB process or build was used**. This closes this investigation segment, not
Issue68 as resolved and not acceptance of the experimental patch.

The [read-only decoder](forkcompare/attribute-workers.py) matches task start/end
by instance and worker, then inspects the first rejecting maintenance policy
within each slow COUNT. It retains original trace hashes, open observed scopes,
generic wait-method call balance and the surrounding scalar-event gap. A wait
call balance is not direct worker-flag proof: these methods have guarded no-op
paths. No scalar events cannot distinguish CPU execution from a blocked wait.

| Fixed case | COUNT ms | Running task intervals ms | Observed state at rejecting maintenance |
| --- | ---: | --- | --- |
|rep0 child20 |796.334 |801.505 /789.434 /783.531 |one background-load scope with open wait call; two unclassified |
|rep1 child5 |795.949 |795.810 /793.253 /784.792 |same shape |
|rep2 child7 |810.725 |807.089 /804.184 /795.730 |same shape |

All three policies show active3, waiting1, long0, concurrency1. The two
unclassified task intervals contain scalar-event gaps around783–797ms and no
open recorded read_wait scope at that maintenance point. This means the existing
read_wait patch is not sufficient to explain these intervals; it does **not**
prove another missing notification, a syscall bug, or CPU saturation.

The two approximately800ms baseline cases each have a pool-worker read_wait
scope without a matching open generic wait call, alongside another unclassified
task and the background-load waiter. This is consistent with the concrete
omission motivating the patch. The approximately403ms baseline case has no
rejecting maintenance policy during COUNT; its decoder row explicitly falls
back to the first rejecting policy, before wait accounting settles. Its snapshot
has fewer executing callbacks than the active count, so it is not pooled with
the five maintenance snapshots or treated as identical worker attribution.

Every observed pool dispatch slot is12303, which the pinned generated table maps
to Fn16585, the generic task execute dispatcher. It dispatches again through task
memory. The recorder does not retain that inner callback identity or worker
CPU/block state. Thus structural source inspection cannot recover those details
from these receipts, and a broader function search would not prove what these
particular workers did.

**Conclusion to the original question:** read1 pool admission contributes real
queue stalls in this workload. The null-trx omission has a concrete experimental
correction and partial distribution benefit. The remaining long tail is not yet
localized to an actionable second site; the complete explanation of the earlier
parallel4 plateau remains unproven. Keep Issue68 open with this bounded segment
stopped. Do not extend the current run until a partial patch passes its gate.

A future, separately selected task should capture **the inner callback plus a
bounded stack for the same instance/worker during a rejected queue window**,
with explicit worker binding. That would distinguish the observed code path from
CPU versus lock/event waits. It requires a new diagnostic overlay and host build,
not another repetition of this recorder. Scope it as one instrumented process
with a no-reproduction exit; engineering effort is estimated at1–2 hours plus
build time (not measured), with no guest/WASM regeneration. There is no current
commitment to run it or to adopt a correction.

[Worker attribution](forkcompare/results-wait-accounting/worker-attribution.json)
and [source correspondence](forkcompare/results-wait-accounting/worker-attribution-provenance.json)
retain all six slow cases. Reproduce without executing a DB:

```sh
python3 benchmarks/forkcompare/attribute-workers.py --raw <extracted-raw> --output benchmarks/forkcompare/results-wait-accounting/worker-attribution.json --check
```

This follow-up changes no prior queue-distribution gate, performance result,
source-bound receipt, product setting or acceptance scope.
