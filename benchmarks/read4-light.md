# Issue #68: light read4 wait observation

2026-11-02; bounded diagnosis, no product correction or adoption.

**The400ms residual COUNT is still not captured; its wait target remains
unconfirmed.** The lighter three-process run nevertheless records the relevant
source path during ordinary progress: a pool callback enters a null-transaction
page-read wait, does not call pool waiting accounting, and concurrent queued
work encounters the concurrency gate. This is narrower evidence than a slow
COUNT causal timeline, and must not be presented as the captured400ms failure.

Recommend ending repeated read4 capture attempts at this checkpoint and reviewing
a minimal guest waiting-accounting proposal against the already captured
product-default read1 case. Read4 is an unadopted experimental setting; making
its remaining rare symptom reproduce is not the only way to advance the
original product-default issue. The source target is concrete, but no correction
is implemented or claimed sufficient here. The material objection is that these
new scopes complete in1–22ms, and another unaccounted wait may be necessary for
the long stall. That remains an acceptance condition for any correction.

## Fixed observations

All3 fresh processes have48 children at parallel8, read4 fixed.

| Process | COUNT maximum | Queued task maximum | Page-read scope maximum | Events |
| --- | ---: | ---: | ---: | ---: |
|0 |25.234ms |31.567ms |21.548ms |207,898 |
|1 |36.790ms |36.333ms |37.646ms |228,198 |
|2 |40.086ms |39.627ms |27.752ms |223,770 |

No COUNT or instrumented page-read scope exceeds100ms; the conditional stack
trigger therefore never fires. All144 child row/isolation/settings/cleanup
oracles pass; instance bindings and all span pairs validate; dropped0.
The total659,866events is36.4% below the preceding full recorder's1,037,785 for
its own144 children. Routine stacks and atomic hooks are statically absent and
raw stack IDs are all0. This event-volume difference is not a measured overhead
percentage: scheduling/task counts differ between runs.

COUNT begins at pool concurrency4 in81/144 children, and overlaps buffer-pool
loading in87/144. Thus some relevant overlap remains, although it is smaller
than the prior full recorder's112/144. The absence is not a fix result or an
estimate of natural tail frequency.

## A source-path observation during ordinary progress

The reducer selects null-trx `read_wait` scopes lasting at least1ms, nested in an
actual pool task on the same instance/thread, with balanced earlier wait-begin/
end call counts and no wait-begin inside the read scope. It then requires a
nonempty queue, zero long-task compensation and a rejecting concurrency decision
in the same instance during that scope. The conservative selection finds:

| Process | Selected scopes | Distinct child instances | Overlap COUNT / before / after |
| --- | ---: | ---: | ---: |
|0 |10 |7 |7 /1 /2 |
|1 |11 |7 |7 /3 /1 |
|2 |8 |6 |7 /0 /1 |

These are29 **function scopes**, not29 long SQL stalls or an exhaustive census of
all missing accounting. They belong to20 distinct process/child identities;21
scopes overlap their own child's COUNT. Scope wall time includes scheduling and
is not a measurement of time physically asleep in a syscall.

One explicit example is process0, child35, instance38, pool worker638:

| Relative to read-wait entry | Event |
| --- | --- |
|0ms |Pool callback slot12303 enters read_wait with trx argument0 |
|0.004ms |Queue nonempty; active5, standby1, waiting0, long0, concurrency4 |
|2.174ms |The same child's COUNT begins |
|4.669ms |The read_wait scope returns |
|9.214ms |COUNT returns; its own duration is7.041ms |

No tpool wait-begin/end call occurs on that worker before/during this scope.
The source gate sees5−0−0>4 and returns before waking even the available standby
worker. If that read scope were accounted as one waiting worker, the same
snapshot would instead satisfy5−0−1≤4. That is a source-level counterfactual,
not an executed fix. This child still makes progress without a timer-scale stall.

All selected pool callbacks use table slot12303, mapped by pinned generated
p6.go to Fn16585. This is an executor/wrapper identity, not proof of the semantic
job's name. Do not identify these scopes as the buffer-pool-load task solely
because they overlap loading or COUNT; the explicit load-function scope did not
cover the selected read scopes.

## Concrete source target, not an implemented correction

Pinned MariaDB `storage/innobase/buf/buf0rea.cc`206–231 implements
`buf_page_t::read_wait(trx_t *trx)`: tpool_wait_begin/end are both inside
`if (trx)`, while `lock.s_lock_nospin()` is outside that condition. The null-trx
path therefore performs the page-read completion-lock operation without those
accounting calls. The light observations corroborate this path on a pool worker
in read4; prior product-default read1 traces retain their separate long-wait
proof.

A minimal proposal for **review**, not an applied patch, is:

```cpp
// Proposed: pool accounting does not depend on transaction statistics.
tpool::tpool_wait_begin();
if (trx) { /* existing THD wait notification and statistics */ }
lock.s_lock_nospin();
tpool::tpool_wait_end();
if (trx) { /* existing THD wait completion and statistics */ }
```

Before implementation, confirm wrapper behavior for non-pool/long-task threads
and balanced begin/end semantics. A candidate would then need correctness and a
bounded comparison on the product-default read1 workload, preserving the original
source-bound slow cases rather than requiring further read4 sampling first.
Other unaccounted waits may remain, so do not promise this one function resolves
all400/800ms symptoms. Changing more parameters is not supported by this receipt.

## What was changed in observation

The runtime configuration stays read4/write2/purge1/nativeAIO0, with the same
seed, TCP queries, independent mutation and cleanup. The canonical v0.6.0 guest
and all pool timer/wait-accounting policy stay unchanged. The pre-start argv
selector, child-instance binding and optional existing phase-file bridge remain.

Routine stack walking is removed entirely. AtomicWait/AtomicNotify bodies are
byte-identical to pinned product source and no AtomicWait/Notify/pread hooks
are installed. Retained events are task submission/start/end, pool state,
maintenance, waiting-accounting calls, worker-start/route tags, page-read waits,
query/background function scopes and concurrency changes. Explicit source route
tags distinguish ordinary policy from maintenance's stall fallback without
CallersFrames. Existing child labels associate each COUNT with its own instance.

A COUNT that is still being observed after100ms may trigger one bounded goroutine
profile per process (maximum1MiB). This is after the suspected stall begins,
not on every event; capture timing/size/truncation and child index are retained.
The trigger and observer overhead must be distinguished from actual QueryContext/
wire delay. This is still an intrusive diagnostic, not an uninstrumented speedup
benchmark. Lower event volume does not quantify total timing perturbation.

Three processes ×48 children at parallel8 is the complete runtime budget.
No more trials are authorized by a missing case. All normal SQL/settings/cleanup
oracles and trace binding/cap checks must pass. No setting or engine/host fix is
implemented here. The question is what a captured residual wait is waiting for.

## Identity and retained evidence

Product v0.6.0 source `b3b3b46a8807482ad3f96725af86e031fe369b01`, annotated tag
object `b57183b08d48884840111e8b53daa500734337f0`. Measured clean harness source
`a22b92566bd132caa3a15c7a03b51156534de49d`. scripts/git_identity.py verifies exact
product/tag/clean source before build. One binary for all3 processes, SHA256
`d105c3ad5ddfe6c1e115cd94ef0b384fad627ad35529d6157701257dc40a09c1`.
Go1.27.3, CGO0, GOMAXPROCS8, macOS27.2 arm64, Apple M1/16GiB. All overlay hashes,
build information and the fixed process plan are in compact inputs. Canonical
WASM identity is not relabeled; the prior startup-argv selector is still an
experimental generated-data change. Generated function names are structural
correspondences, not a newly recovered WASM symbol map.

[Compact](forkcompare/results-read4-light/compact.json),
[summary](forkcompare/results-read4-light/summary.json),
[lightness check](forkcompare/results-read4-light/lightness-check.json),
[negative controls](forkcompare/results-read4-light/analysis-verification.json),
[source identity](forkcompare/results-read4-light/source-identity.json),
[raw reference](forkcompare/results-read4-light/raw-reference.json),
[checksums](forkcompare/results-read4-light/SHA256SUMS.json).

Raw archive: evidence commit `7039f98ece1ed156e86ad1fd4248853c35c1069e`, ref
`evidence/read4-light-20261102`, raw.tar.gz6,121,033bytes, SHA256
`54e17fcfd06587d658a332435cfc8a68f51240e258a4e512d681c1e75c5c0acc`.
Its480members include all events, reports, phase files, source/excerpts and
hashes. Raw stays on the evidence ref; report keeps compact knowledge.
Original/published member hashes describe workspace-prefix normalization.

Read-only verification after disposable workspace cleanup:

```sh
python3 benchmarks/forkcompare/analyze-read4-light.py --results benchmarks/forkcompare/results-read4-light --check
```

Extract the checksum-verified archive and add --evidence <directory> for full
raw reduction. Binding/drop negative controls pass. The normal-path selection
is recomputed from raw events, not inferred from a prewritten example. The slow
case and triggered-stack branch have no real slow case in this receipt and are
not empirically accepted by it. The initial observation builder stopped on an
incorrect single-anchor expectation before any DB run; its generated duplicate
maintenance branches were fixed before the measured clean build. No failed
runtime observation was relabeled as a normal PASS.

Reproduction uses the measured harness in a disposable workspace with the pinned
product at temp/product and light-run.py copied to evidence/run.py; run --phase
build then --phase measure. New runs produce new receipts. These3 observations
complete this task's runtime cap. No further repeats, wait-accounting/timer fix,
guest rebuild, Ubuntu/native comparison, CI, main adoption, qualification or
release were performed.
