# Issue140: settings-only read1/read4 comparison

**Read4 did not remove the global-dispatch tail.** It reduced tails in the
diagnostic cohort, but the observation-disabled cohort had3 long PREPARE calls
in each arm and only a2.2% difference in median whole-suite time. Keep read4 as
a possible mitigation, not a verified fix or an approved new default.

## Observation-disabled comparison

Same binary; observer registration and profile watcher disabled. Hook calls,
some task-word reads, empty registry lookups, SQL phase timers and pprof DB
labels remain. This is not a pristine product benchmark. Five alternating pairs,
16MiB/shop70/Pipe/P8/cap9, unchanged SQL and seed. Warmups excluded.

| Metric | read1 | read4 |
| --- | ---: | ---: |
| Whole-suite wall median |597.595ms|584.289ms|
| Process CPU median, all threads |2857.040ms|2803.404ms|
| Process peak RSS median |760.891MiB|766.625MiB|
| PREPARE >=100ms |3/315|3/315|
| Processes with a long PREPARE |2/5|3/5|

Whole-suite time includes boot/schema/seed/Snapshot,70 cases, sample loading,
connection retirement and cleanup. It excludes compilation and post-workload
observer serialization. CPU covers the same workload through cleanup. RSS is
Darwin Getrusage process peak, not held-child RSS or per-DB incremental memory.
Paired wall outcomes are3 faster/2 slower; individual deltas are -51.09%,+39.52%,
-2.45%,+28.52%,-2.23%. A single median is not a stable speedup claim. CPU and
RSS deltas are mixed as well; no consistent resource improvement is established.

## Diagnostic cohort

Five separate alternating pairs, full inherited same-request admission observer
and20ms/100ms PREPARE profile watcher enabled. These hooks scan actual global
queue membership under the existing guest mutex and perturb scheduling. Do not
advertise the39.3% diagnostic wall reduction as production performance.

| Metric | read1 | read4 |
| --- | ---: | ---: |
| Whole-suite wall median |980.388ms|594.630ms|
| Process CPU median |3175.007ms|3166.773ms|
| Process peak RSS median |773.625MiB|774.875MiB|
| PREPARE >=100ms |5/315|2/315|
| Read requests (including background/startup) |19280|17427|
| Requests with a global stage >=100ms |999|431|
| Group stages >=100ms |0|0|
| Median of per-process global-stage p95 |22.500ms|22.120ms|
| Median of per-process global-stage p99 |401.030ms|26.223ms|

Each read has an initial and completion dispatch stage. The999/431 counts are
correlated requests within five processes, not independent stalls. Per-process
p50/p95/p99/max and full timing tuples are retained; the table aggregates the
five per-process percentile values, not a pooled quantile. Background work makes
read-request denominators differ despite identical foreground SQL oracles.

## Read4 still waits in global dispatch

The effective SQL variable is4, and the bound gate snapshots show global cap4.
Both natural read4 profiles bind the foreground PREPARE frame (Fn7142), DB/scope,
page, parked channel request and actual notifying callback request:

| Run / page | PREPARE | Initial global queue | Completion global queue | Initial / completion group |
| --- | ---: | ---: | ---: | ---: |
|natural-9-read4-on / [10, 0]|409.141ms|395.609ms|12.972ms|0.000/0.001ms|
|natural-16-read4-on / [10, 0]|387.705ms|391.309ms|4.696ms|0.000/0.000ms|

Both requests also have a locked queued-task snapshot with **active7 - long0 -
waiting2 =5 > cap4**, rejecting wake/create. These particular snapshots occur
late in the long interval; they do not prove uninterrupted rejection over391ms
or identify the first release event. The fact established is that raising read
count to4 did not eliminate the same global-dispatch layer of delay.
The read task group still does not account for the long interval.

One read1 PREPARE profile (natural7) contains a background read scope rather
than a directly bound foreground read_wait. It is not relabeled as foreground
read causality. The other five natural foreground bindings, and all captures,
remain available. The live SLEEP positive control is separate.

## All measured pairs

| Mode | Pair | read1 wall ms | read4 wall ms | Delta | read1/read4 long PREPARE |
| --- | ---: | ---: | ---: | ---: | ---: |
|disabled|1|1136.758|555.946|-51.09%|2/0|
|disabled|2|606.848|846.699|+39.52%|1/1|
|disabled|3|597.305|582.643|-2.45%|0/0|
|disabled|4|545.656|701.250|+28.52%|0/1|
|disabled|5|597.595|584.289|-2.23%|0/1|
|diagnostic|1|851.771|594.630|-30.19%|1/0|
|diagnostic|2|980.388|990.255|+1.01%|1/1|
|diagnostic|3|1106.032|735.221|-33.53%|1/1|
|diagnostic|4|1215.842|565.125|-53.52%|2/0|
|diagnostic|5|579.439|568.441|-1.90%|0/0|

## Recommendation and stopping point

The requested settings-only comparison is complete. **Do not adopt read4 as the
fix for #140 from this evidence.** It remains a possible mitigation, but benefit
is much clearer with observation enabled than disabled, and tails remain in both.
This does not prove no other configuration can help, nor that a code fix is
strictly necessary. No additional read-count/flush/pool-size sweep is started.

If continuing the remedy work, choose a small design that addresses actual
global-pool progress: either correct waiting accounting for the pool workers
that really block, or separate transient global startup concurrency from the
read-group limit. The current captures do not yet identify each blocked worker
or prove that moving the conditional read_wait notification alone fixes it.
A next proposal should name its invariant and correctness checks before adding
implementation or another capture layer. No product fix/default/main/release
decision is made here. #68 old UPDATE/UNDO evidence is not declared the same
cause; #88 buffer8/16MiB remains a separate decision.

## Identity, controls and retention

Measured source_commit `428fbfc942b6c6feafef38980fa117417cd07870`; product source
`a3b2b6457147e2b8edbd31fec77ab6ec04f11b22`; origin guest
`14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`.
Go1.27.3, macOS27.2 arm64, Apple M1,16GiB, GOMAXPROCS8/GOGC100/CGO0.
`git_identity.py` checked the clean commit before build. Committed internal/,
guest/,release/,go.mod/go.sum are unchanged from the product. The only treatment
changes one byte of argv read1 to read4, after all25 original arguments are
verified. Same binary/hash for every arm; observation mode is separately labelled.
Both buffer variables and read thread count are asserted through SHOW on each
root, and every observed read request group limit is checked against the arm.

Race-enabled original10 observer tests plus read selector/disabled-observer
tests and existing pool-selector controls pass. The read selector accepts only
1/4 and checks exact memory mutation; invalid values cannot partially mutate
argv. Disabled observation still invokes the original guest operation.

One live control,4 separate warmups and20 natural suites: **1750 SQL cases PASS**,
zero active mappings after25 processes,286 registered observers closed, no
truncation. Warmups and control are retained but excluded from comparisons.
Single Mac only; no Ubuntu or new native reference campaign is claimed.

All-request compact timing tuples, SQL phase arrays, traces, selected full read
metadata, profiles, inputs and checksums are retained in about5MiB. Unreferenced I/O metadata (including long background requests) is reduced to an explicit census and digest; their full
counter history cannot be reconstructed from that digest. Queue observations
are N/A when disabled, never zero-delay evidence.

```sh
python3 benchmarks/issue140readsetting/results/analyze.py --check
```

Replay verifies settings, SQL/cleanup, stage chronology/group limit, queued gate
formula, same-page/request notifier/profile binding, all-request census, summary
bytes/checksums and five negative mutations. It needs no deleted build/cache.

For a separately authorized reproduction, create a disposable checkout at the
measured source with worktree/temp/evidence directories, then run the workspace
helper with `python3 benchmarks/issue140readsetting/run.py WORKSPACE`. The fixed
plan is in ../plan.json; network may be needed for module acquisition. New
receipts retain their own identity. No new natural capture is guaranteed.

Work stayed within the2h active/30min tooling budget; heavy CI0. Elapsed wall time through initial reporting was about9min, including123s
compilation. Active/tooling time was not separately metered; both fit within
the wall-time upper bound. Owned recreated
build/cache/worktree are removed after preservation; prior user edits remain.
