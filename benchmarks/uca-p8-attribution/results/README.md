# UCA P8 tail attribution: hold adoption for now

**Decision informed: adopt the UCA startup optimization now, or retain it while
isolating the P8 tail risk. Recommend hold, not rejection.** The observer-off
P8 disadvantage repeated in8/10 pairs, despite lower Fork wall and suite CPU.
The strongest case for adoption is real startup savings and that the captured
wait is an existing PREPARE/read-completion path present in both arms, with no
new SQL/correctness/cleanup failure. That does not justify dismissing a repeated
whole-suite disadvantage when total execution time is the product priority.
This investigation ends with these tradeoffs; it does not authorize adoption,
further sampling, runtime changes or a new release gate.

## What became decidable

- The prior adverse P8 result was not confined to the original five pairs.
  The same binaries again show more >100ms sample spans in the candidate.
- In the diagnostic runs, **all individual sample calls >100ms were PREPARE**:
  orders INSERT or stock UPDATE preparation. INSERT execution, UPDATE execution
  and COMMIT had no >100ms calls in either arm. This does not relabel every
  unobserved sample tail as PREPARE.
- Four usable natural profiles (two per arm) show the foreground in the same
  buffer-page/read-completion shared-lock path, ending at host `AtomicWait`'s
  untimed notification branch. The UCA constructor is not on those stacks.
  This is structurally the Issue140 PREPARE path, not evidence of the older
  Issue143 UPDATE-execution/UNDO writer-lock wait.
- Why the candidate encounters more tails **with diagnostics off** is still
  unknown. A profile cannot identify the page's I/O task/owner, enqueue-to-start
  delay, callback delay, wake timing, or prove continuous waiting for400ms.
  Faster startup changing overlap is a hypothesis, not an established cause.

## Fixed experiment and results

[Plan](../plan.json) was committed before execution. Sources, binary hashes,
collector injection and host are in [inputs](inputs.json). Baseline500020e7,
experimental guest originf4325722, identical SDK/host code and Go1.26.10.
Go Pipe/P8/cap9, pool16MiB/read1, GOMAXPROCS8/GOGC100; Apple M1/16GiB/macOS27.2.
The observer-off runners match the previous measurement's binaries exactly.
SQL text/order/data remain fixed; only separate diagnostic runners add labels,
phase timing and the reused single20ms watcher. Guest/C build count0; heavy CI0.

Two actual SQL SLEEP(0.25) controls pass before natural sampling. Invalid DB,
outside-window, truncated and no-guest profiles are rejected. Then one off
warmup pair, ten alternating off pairs and four diagnostic pairs; all32 processes
complete without retries. All2240 suite cases, sample shape checks, mappings0
and empty owned scratch pass. Compilation and recursive disk scanning finish
before execution; disk checks occur between processes, with150s watchdogs.

| Observer-off P8 metric | Baseline | Candidate |
| --- | ---: | ---: |
| Whole-suite wall median | 467.528ms | 571.206ms |
| Whole-suite CPU median | 2363.025ms | 2327.322ms |
| Child Fork median | 26.941ms | 25.774ms |
| Child sample median | 66.961ms | 67.616ms |
| Sample >100ms | 5/210 children | 8/210 children |
| Batches with sample >100ms | 4/10 | 7/10 |
| Fork >100ms | 0/210 | 0/210 |
| Process peak RSS median | 706.63MiB | 708.97MiB |

Candidate is faster in2/10 pairs; median paired wall change **+15.70%**.
The difference between independent suite medians is+22.18%; it is a different
statistic. Both are reported without replacing the original five-pair result.
Candidate's maximum/p95 suite is795.240ms versus812.238ms baseline: the result is
more tail-affected batches, not a uniformly longer worst-case duration. Child
sample medians/p95 are nearly unchanged; neither arm's Fork exceeds100ms.
Do not treat210 children as210 independent experiments: there are ten batches.

## SQL and current-source attribution

In each diagnostic arm,84 loaders execute252 PREPAREs,3360 order INSERTs,
8400 item INSERTs,8400 stock UPDATEs and84 COMMITs. PREPARE >100ms counts are
3 baseline /2 candidate; other sample operations have zero >100ms. Diagnostic
instrumentation changes timing and has only four pairs, so that reversed count
cannot cancel the observer-off result or estimate population tail probabilities.

| Captured call | SQL | Call wall | Snapshot cost |
| --- | --- | ---: | ---: |
| diagnostic-0-baseline | orders INSERT PREPARE | 410.906ms | 2.947ms |
| diagnostic-1-candidate | stock UPDATE PREPARE | 404.114ms | 3.823ms |
| diagnostic-2-candidate | orders INSERT PREPARE | 401.030ms | 4.923ms |
| diagnostic-3-baseline | orders INSERT PREPARE | 400.705ms | 3.416ms |

All four have same-DB labels and complete snapshot windows inside the actual
caller entry/return. One capture/process is the fixed cap, so one other long
baseline PREPARE has no stack. A sample span >100ms can also be accumulated short
calls: candidate diagnostic0 has such a sample but no individual call >100ms.

The five selected wait-chain functions were re-extracted from **both current
arms**, hashed and checked structurally against the historical Issue140 mapping.
Non-numeric tokens match; analysis does not substitute those comparisons for an
execution hash guard. [Binding](source-binding.json) and
[current excerpts](source-excerpts.md) retain the exact hashes and control-flow
checks, with complete matching-DB profile blocks retained for inspection. Unrelated DB/runtime
blocks are omitted; captures.json records original and retained SHA256 separately. Native names are
structural correspondences, not a complete C symbol map:

```text
PREPARE (table/index metadata opening)
  -> buf_page_get_gen             Fn18164
  -> buf_page_t::read_wait        Fn16787
  -> block_lock::s_lock_nospin    Fn16624
  -> futex wrapper Fn216 -> Fn88
  -> host.Futex_wait -> AtomicWait32At -> AtomicWait
                                      untimed notify/failure branch
```

Foreground membership is selected by the current command-dispatch chain and DB
label, not by an arbitrary background worker that happens to wait. The host
profile points to base.go:1946's untimed select, not the timed branch below it.
This localizes where the foreground was stopped at capture time. It does **not**
prove which background thread owns the page, whether work is still queued, or
whether its completion notification was late. It also does not rule out layout,
first-touch, scheduling or initialization overlap contributing upstream.

## Actionable boundary

No new UCA correctness defect is observed, but adopting it as a general total-time
improvement is not supported. Keep the candidate and its demonstrated1.1ms
isolated Fork saving; associate this tail with Issue140's **current-source
PREPARE/read-completion attribution**, without reopening the completed Issue68 or
claiming Issue143's UPDATE/UNDO mechanism reproduced.

If the Human wants one further diagnostic, reuse Issue140's existing page/request
and dispatch observer, rebind its exact anchors for these two guests, and capture
one long PREPARE per arm. Needed evidence is the same read request's submission,
worker start, completion callback and wake times, with current pool counters.
This distinguishes queue starvation from work/notification latency and tests
whether the UCA change alters overlap. It is a separate bounded decision: expect
one local Go overlay build per arm, at most one fixed small diagnostic block,
no C rebuild or heavy CI; allow up to2h active/30m tooling and stop if current
anchor rebinding exceeds that allowance. Do not silently implement that observer
or make unlimited reproduction a new adoption prerequisite.

Alternatively, explicitly accepting the P8 risk while taking P4/startup savings
is a valid product tradeoff for the Human. The evidence does not support claiming
that risk has disappeared merely because the wait class already existed.

## Retention and reproduction

`python3 benchmarks/uca-p8-attribution/results/analyze.py --check` recomputes the
summary from retained compact CSV. Per-child stages, per-loader phase counts,
maxima/totals and >100ms counts, all >=50ms operations, bounded matching-DB captures and current
source anchors are retained. Unused raw trace/operation arrays, console logs,
REST responses, guest archives and generated/build/cache trees are not committed.
The previous measurement stays unchanged under its original source.

Use an owned disposable workspace as in the previous comparison. The reproduction
scripts use the same pinned guest/translation/Mac artifacts and original source
checkout; `build.py` additionally verifies observer-off binary equality and builds
identical injected collectors. Complete builds before `run.py`; validate controls
before natural runs. `compact.py`, `analyze.py` and `bind.py` retain/replay the
finite result. SQL literals/order and unchanged surrounding seed code are asserted
by `instrument.py`; its initial pilot only discovered the missing recorder clock
accessor, fixed before any build/natural sampling. No failed performance sample
was replaced. Read the plan before executing; there is no automatic extra trial.
