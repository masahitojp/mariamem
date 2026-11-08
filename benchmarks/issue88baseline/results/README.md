# Issue88: current-main 16MiB baseline

Single-Mac observation, 2026-11-08. **Baseline established; the 16/8MiB A/B has
not been run.** This does not decide the buffer-pool setting or complete #88.

Product source_commit `a3b2b6457147e2b8edbd31fec77ab6ec04f11b22`;
measured harness source_commit `83fd60a9e7a8792404a491250d6486010540eab1`.
Only `benchmarks/issue88baseline/{main.go,plan.json}` differ from product main
at the measured source. Guest SHA256:
`14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`.
No runtime overlays or timing diagnostics. Binary identity and build info are
in inputs.json. Later report/runner additions do not relabel the measurement.

Go1.27.3, CGO0, GOMAXPROCS8, GOGC100; local M1/16GiB/macOS27.2.
Pipe, one client connection, 1000 rows with 32-byte payload, MaxForks4.
Both effective buffer-pool variables equal16,777,216, checked on all ten roots
and first measured serial child. Five fresh serial processes alternate with five
independent retention processes. Each serial process has one separately recorded
warmup, then48 measured children. All240 primary observations remain included.
Retention measures0/1/4 children after SQL and connection retirement; at each
point GC, FreeOSMemory and100ms settling precede the OS RSS probe.

| Per-child operation | p50 ms | p95 ms | maximum ms |
| --- | ---: | ---: | ---: |
| Fork elapsed |18.673|22.409|26.950|
| Fork process CPU, all threads |28.069|31.866|38.684|
| First SQL, including lazy Pipe connection |1.686|2.098|3.831|
| Pool Close + WaitDisconnected |0.047|0.062|0.263|
| Database.Close |1.852|2.045|3.564|

The first SQL verifies COUNT/SUM(id)/SUM(payload length), not the earlier
70-operation comparison suite. SQL UPDATE and subsequent point-read correctness
are checked but their latency is not separately measured. Process CPU includes
all in-process runtime/GC activity during serial Fork, excludes counter-helper
subprocesses, and is not CPU percentage. Medians are not additive.
Fork process medians:18.692/18.931/19.137/18.559/18.046ms.
No measured operation in the table exceeded100ms. This does not resolve #68 or
establish a general absence of tails. No outlier exclusion or rerun selection.

| Held state, median of5 processes | RSS MiB |
| --- | ---: |
| Snapshot only |53.516|
| One child, increment over same process0-child point |72.859|
| Four children, total increment |296.016|
| Four-child increment divided by4 |74.004|

One-child increments range72.313–72.891MiB; four-child totals294.609–297.438MiB.
RSS is a process checkpoint, not peak/PSS, and the divided result is not an
individual-child attribution. Checkpoint scavenging differs from ordinary
latency conditions and earlier cohorts; don't compute historical speedups.
Desktop VM/services remained active; this is not an isolated-host performance
claim. Workspace disk monitoring was active, identical for all runs.

Each measured child verifies pristine seed, commits an UPDATE and checks its
result. A final pristine child in every process verifies baseline preservation.
All ten processes report success, Close succeeds, and final active mappings are0.
Total children:240 measured serial,5 serial warmups,20 held,10 final oracles.
This is bounded harness correctness, not release or both-platform qualification.

## Recompute without build/temp or network

```sh
python3 benchmarks/issue88baseline/results/analyze.py --check
```

This is read-only and asserts stored summary equality. observations.json retains
all process observations, warmups, settings, retention counters and cleanup
outcomes. SHA256SUMS.json covers the report, observations, inputs, summary and
analyzer. No build trees, binary, fixture data or routine logs are retained here.

## Reproduce measurements

Use a clean disposable checkout of this report's branch, Go1.27.3/native C tools,
and the same host/runtime settings. Prepare via experiment-workspace with8GiB
free reserve,10GiB budget,900s total timeout. Execute the checked-in runner under
that helper, e.g. from a newly prepared checkout:

```sh
python3 scripts/experiment_workspace.py run --timeout 900 issue88-baseline -- python3 benchmarks/issue88baseline/run.py
```

The helper runs from its worktree. The runner checks a clean source identity and
empty runtime/guest/module diff against the pinned product source before building;
it records the actual reproduction source rather than claiming original83fd60a9.
Build/download cost is excluded. The original run used an identical runner in
external evidence; the checked-in version adds durable workspace resolution and
allows later report-only sources after the same runtime equality assertion.
Keep measurements in evidence, reduce to the structured observation format and
run the analyzer; commit results separately, then finalize/clean disposable state.

Question answered: what is the present16MiB baseline? Fixed exit is these ten
successful processes and checksum-bound report, or explicit failure; no additional
sampling. Default budget:2h active/30min tooling, no heavy CI. Next: same-source
16/8MiB alternating A/B plus small/over-pool-size SQL guard, followed by Human
candidate decision. This report alone neither proves a benefit nor changes defaults.
