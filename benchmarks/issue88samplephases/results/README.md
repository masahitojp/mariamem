# Issue88: sample-loading SQL phases,16/8MiB

**The usual work is dominated by item INSERT, but the long delays in this
campaign mostly occurred in PrepareContext, before executing the sample writes.**
No stock UPDATE or COMMIT exceeded100ms. The8MiB arm slightly reduces typical
order/item/stock execution and Fork elapsed, but still has more long preparation
calls in this finite observation. Its RSS/startup candidacy remains useful;
this is not evidence to change the product default or dismiss tails as random.

The original question is answered at the caller operation boundary. We have
not identified the engine/host function, lock, owner or scheduling mechanism
inside those calls. A further investigation should target PREPARE for INSERT
into orders/order_items, rather than assume UPDATE/COMMIT is responsible or
restart a general parameter sweep. No further sampling is authorized here.

## Fixed source and execution

2026-11-08, source_commit
`f824a6b262f8aa632ef1afa3d91c88778644588d`, based on the previous shop suite
`f66b7dbb58e2e402ffc11a35749e607a0eb235ea` and product source_commit
`a3b2b6457147e2b8edbd31fec77ab6ec04f11b22`. Origin guest SHA256:
`14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`.
Source identity and clean status checked before build. Same binary and previously
validated two-argv16/8MiB selector; no tracked runtime/guest/API/release changes.
Inputs bind binary, origin, overlay and source hashes separately. This is a
caller diagnostic, not canonical guest regeneration or release acceptance.

Same shop70 cases, same SQL/order/trigger/transaction semantics, Pipe, P8,
MaxForks9 (one held reader + up to8 writers). MacM1/16GiB/macOS27.2,
Go1.27.3/CGO0/GOMAXPROCS8/GOGC100. Five alternating16/8 pairs, one process at a
time, plus two separate warmups and two observer-off sanity processes. Pgmem is
not rerun here. The diagnostic module manifest contains MariaDB dependencies
only; to reproduce the prior pgmem comparison use its original pinned branch.

Each of21 loaders per suite has exactly1 BEGIN,3 PREPARE,40 order INSERT,
100 item INSERT,100 stock UPDATE,1 COMMIT,3 statement Close and1 deferred
rollback cleanup. Counts are asserted per loader. That is52,290 primary caller
operation durations in210 loaders/700 test cases. All14 processes PASS; every
process reports50 reads,20 writes, successful Close and final active mappings0.

## Typical costs

All primary observations included, no outlier filtering. The first two columns
are per-loader phase-total p50 (ms), the last two per-call p50 (ms). Component
medians are not additive. Elapsed includes concurrent work/scheduling; it is not
exclusive engine CPU time.

| Phase |16MiB total/loader|8MiB total/loader|16MiB/call|8MiB/call|
|---|---:|---:|---:|---:|
| Orders INSERT ×40 |11.708|11.279|0.202|0.195|
| Items INSERT ×100 |40.616|39.382|0.272|0.272|
| Stock UPDATE ×100 |20.715|19.678|0.1365|0.134|
| COMMIT ×1 |0.285|0.255|0.285|0.255|
| BEGIN, connection acquisition included |3.073|2.972|3.073|2.972|
| PREPARE ×3 |4.237|5.800|1.107|1.317|

The small pooled reductions are not consistent across paired process medians:
order INSERT improves2/5 pairs, item INSERT3/5, stock UPDATE3/5, COMMIT3/5.
PREPARE's per-loader median is slower at8MiB in5/5 pairs (increments0.52–3.50ms),
even apart from its rare large calls. This is a further reason not to read the
pooled normal-operation medians as an established whole-workload8MiB win.

Total loader p50:86.665→83.972ms (approximately3.1% lower); p95:114.559→431.725ms.
Median per-loader unassigned time is0.193ms for both settings; maximum0.371/
0.246ms. It includes loop/result checking, observer bookkeeping, call boundaries
and microsecond rounding. Thus the captured operations account for almost all
of the observed sample interval. The phase totals include trigger work in their
caller statement: item INSERT also refreshes the order's denormalized total.
COMMIT is the full database/sql Tx.Commit boundary, including any automatic
prepared-statement retirement. Deferred rollback after successful commit returns
ErrTxDone and performs no additional SQL. Sub-microsecond durations can round0;
that is not proof of zero cost.

## Long calls

Thresholds are descriptive classifications, not performance acceptance gates.
All individual durations are retained; context/global clock positions are kept
for calls≥50ms. Primary calls≥100ms:

| Setting |Pair (1-based)|Caller operation|Duration ms|Case|
|---|---:|---|---:|---|
|8MiB|2|PREPARE orders INSERT|394.851|TestApplyDiscount/books_10|
|8MiB|2|PREPARE order_items INSERT|797.773|TestCreateOrder/out_of_stock|
|8MiB|3|PREPARE orders INSERT|799.041|TestCancelOrder/another_paid|
|8MiB|4|PREPARE orders INSERT|387.765|TestShipOrder/one_paid|
|16MiB|5|First orders INSERT, order_id1|400.391|TestApplyDiscount/music_25|
|8MiB|5|PREPARE orders INSERT|395.470|TestDeleteUser/user_15|
|8MiB|5|PREPARE orders INSERT|401.243|TestDeleteUser/user_36|

The PREPARE subtype is reconstructed from its unique exact duration in the
ordered3-PREPARE duration array (orders/items/stock); the analyzer asserts
uniqueness. No extra experiment was needed to identify these statements.

| Caller boundary |16MiB maximum ms|8MiB maximum ms|≥100ms count16/8|
|---|---:|---:|---:|
| PREPARE |14.122|799.041|0 /6|
| Orders INSERT |400.391|5.914|1 /0|
| Items INSERT |11.682|11.723|0 /0|
| Stock UPDATE |10.640|7.777|0 /0|
| COMMIT |1.071|2.532|0 /0|

The timing is around Go's PrepareContext/statement execution, so it includes
protocol, guest SQL processing and host/goroutine scheduling. PREPARE has not yet
executed the requested INSERT. It may still touch metadata/engine structures;
these records alone do not identify that path, a page, UNDO, physical I/O, a
mutex owner, or a missing syscall. Earlier #68 observations are not relabeled
as the explanation for this cohort. No engine/host owner logger was added.

## Full diagnostic suite and controls

| Setting |Run1 ms|Run2 ms|Run3 ms|Run4 ms|Run5 ms|Median ms|CPU median ms|
|---|---:|---:|---:|---:|---:|---:|---:|
|16MiB|516.596|552.690|569.657|525.848|582.541|552.690|2891.536|
|8MiB|584.193|1236.867|1222.039|639.822|833.778|833.778|2898.090|

8MiB improves0/5 suite pairs in this diagnostic cohort; median paired suite
change+43.13%. CPU median is approximately unchanged. Pooled Fork elapsed p50:
39.600→35.646ms. These instrumented durations are a separate cohort, not a new
uninstrumented performance claim or a speedup versus the earlier866/1412ms run.
The normal repeat work and the long-delay risk must be evaluated separately.

Observer-off sanity totals:16MiB1002.557ms,8MiB510.476ms. The16MiB control has an
865.751ms sample span but deliberately has no per-call record, so its internal
operation is **unknown**. This confirms long sample spans also occur without
the observer and at16MiB. One off-run per arm does not bound observer overhead
or establish tail probability. It must not be pooled with the five primary runs
or used to select a favorable headline. Both primary and prior realistic
campaigns observed more tails at8MiB; don't dismiss that direction, but do not
infer a precise risk or its cause from these small separate cohorts.

Normal order/item/stock totals and earlier held-RSS results support the user's
8MiB hypothesis. Against that, no full-suite advantage was established and long
calls concentrate at8MiB in this run. Recommendation: keep8MiB as a candidate,
retain16MiB default while deciding whether to investigate the identified PREPARE
entry or explicitly accept the tradeoff. Canonical configuration/regeneration,
both-platform functional acceptance and adoption remain separate Human gates.
No automatic root-cause campaign follows this report.

## Record and reproduction

```sh
python3 benchmarks/issue88samplephases/results/analyze.py --check
```

Read-only recomputation verifies all counts and caller/sample clock alignment,
then compares summary byte-for-byte. observations.json retains all14 coarse
suite traces, all per-phase microsecond durations and contextual long calls.
There is no per-SQL file I/O or global lock: each loader appends local values,
emits one record after deferred cleanup, and files are written after the suite
CPU/elapsed boundary. Recording can perturb scheduling; this is explicit
instrumentation, not an invisible overhead claim. SHA256SUMS.json covers the
compact report/source identities/observations/summary/analyzer/assessment.

For a new diagnostic run, prepare a clean disposable worktree of this branch:

```sh
python3 scripts/experiment_disk.py --work-dir WORKSPACE --min-free-gib 8 --budget-gib 10 --timeout 900 -- python3 WORKTREE/benchmarks/issue88samplephases/run.py WORKSPACE
```

WORKSPACE has worktree/,temp/,evidence/. The checked-in runner adds an explicit
workspace argument to the original external execution script; assessment keeps
its original digest. It validates source identity/runtime equality, builds the
same single binary, executes fixed warmups/controls/pairs, checks case counts,
per-loader phase census, effective settings and final mappings, then aggregates
results. Build/download costs are excluded. Preserve the new compact observations
and analyze in a new result directory, then finalize/clean owned temp/build.
The finite exit is complete; no extra samples were taken. Default active/tooling
budgets2h/30min and zero heavy CI submissions apply; no measurement subsystem or
product feature is introduced.
