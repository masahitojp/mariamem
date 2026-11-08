# Issue88: 16/8MiB buffer-pool comparison

**Conclusion: advance8MiB as a bounded candidate for review, with an explicit
large-scan tradeoff.** On this single Mac, small-fixture Fork and CPU improved
in5/5 paired process medians, and retained RSS fell about8MiB per child.
A27.56MiB allocated table's repeated scan slowed in5/5 pairs. This supports the
startup/memory hypothesis, not an unconditional default change. Human choice on
that exchange precedes canonical regeneration and both-platform acceptance.
No product default, version, main integration or release is authorized here.

## Source and mechanism

2026-11-08, product source_commit
`a3b2b6457147e2b8edbd31fec77ab6ec04f11b22`; measured harness source_commit
`caaebef0f4ac49f61fe4d7828092c80bb39f18bd`.
Origin guest SHA256
`14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`.
All tracked runtime/guest/release files equal the product source. **Experimental
execution uses a Go overlay**: the generated embedded-server call validates the
full25-item argv preimage and changes just two string values before
mysql_server_init. The same binary and validation path serve both arms:

- `--innodb-buffer-pool-size=16M` → `8M`
- `--loose-innodb-buffer-pool-size-max=16M` → `8M`

The guest hash identifies the origin, not a separately regenerated8MiB guest.
inputs.json binds the binary, source, generated overlay before/after hashes,
selector hash, toolchain and host. Both variants and4 malformed-input paths pass
selector tests, including exact memory changes and no partial mutation on error.
An initial stale-callsite preflight failed before build/measurement; corrected
current callsite is Fn5739. assessment.json preserves distinct source identities.
No samples were selected from the failed attempt. No guest C rebuild was needed
for this experimental setting comparison; a product candidate requires its own
canonical representation and acceptance.

## Fixed workload

M1/16GiB/macOS27.2, Go1.27.3/CGO0, GOMAXPROCS8/GOGC100, Pipe, MaxForks4.
Five alternating16/8 pairs, four fixture/mode cells rotated between pairs,
40 fresh processes. Small:1000×32-byte payload,48 measured serial children/process.
Large:24,576×1024-byte payload,8 measured serial children/process; ANALYZE TABLE
then information_schema DATA_LENGTH+INDEX_LENGTH reports28,901,376bytes
(27.5625MiB), exceeding both pools. This is engine-reported allocated table space,
not merely24MiB inserted payload or process RSS. Small stats are not ANALYZEd
and must not be treated as precise allocated size.

The two arms share every other setting, fixture, SQL, host and toolchain.
Both effective variables are checked on every root and the first measured child
of each serial process. All requests and effective values are retained.
There are560 primary serial children,20 separate warmups,80 held children and40
final pristine children. No exclusions, extra sampling or timing acceptance gate.
First SQL connects lazily then scans COUNT/SUM(id)/SUM(payload length). A second
identical scan follows; committed UPDATE+point verification is timed separately.

The prior16MiB-only report is historical baseline context; this new same-harness
A/B adds the second scan and uses VARBINARY(1024) for both fixtures. Do not subtract
its numbers from the previous run or combine cohorts.

## Timing results

Pooled child p50; percentage column is median of5 paired process-median changes,
so its percentage need not equal the ratio of pooled medians.

| Fixture / boundary |16MiB ms|8MiB ms|Paired change|Improved pairs|
|---|---:|---:|---:|---:|
| Small Fork elapsed |19.010|18.343|−3.04%|5/5|
| Small Fork process CPU |28.586|27.954|−2.74%|5/5|
| Small first scan, connection included |1.705|1.702|+0.03%|2/5|
| Small second scan |1.054|1.050|−0.44%|3/5|
| Small UPDATE+point verification |0.367|0.366|−0.31%|3/5|
| Large Fork elapsed |19.665|18.455|−6.96%|5/5|
| Large Fork process CPU |30.909|28.190|−6.45%|5/5|
| Large first scan, connection included |32.216|33.448|+3.71%|1/5|
| Large second scan |31.572|32.883|+4.96%|0/5|
| Large UPDATE+point verification |0.588|0.583|−2.69%|4/5|

Small Fork p95:22.358→22.885ms: the p50 gain is not a uniform tail improvement.
Large Fork p95:25.218→21.768ms. All primary operations in the measured table have
0 observations above100ms; this does not resolve #68. Full extrema, per-pair
values, disconnect and Close remain in summary/observations. Process CPU spans
all in-process threads/GC during each serial Fork; it is not CPU percentage.
No stage attribution, queue distribution or P4/P8 throughput was measured.
Do not add medians into a whole-suite total. Full application suite benefit
remains workload-dependent, especially with repeated scans larger than the pool.

## Retained RSS

Independent processes; same-process Snapshot-only baseline subtracted at1/4
children after SQL+disconnect. GC, FreeOSMemory and100ms settling at each point.

| Fixture / held state |16MiB increment MiB|8MiB increment MiB|
|---|---:|---:|
| Small,1 child |72.750|64.719|
| Small,4 children total |296.188|264.250|
| Large,1 child |72.797|64.656|
| Large,4 children total |289.266|256.766|

About8MiB/child is an observation here, not a promised saving for every fixture.
RSS is checkpoint process RSS, not PSS/peak or a per-child allocation census.
The two fixture baselines differ; compare matched arms within each fixture.
Desktop VM/services and Spotlight remained active; disk monitoring was active.
This is paired local evidence, not an isolated-host or Ubuntu performance claim.

## Correctness, scope and exit

40/40 processes succeed. Every primary child verifies pristine seed, committed
mutation and a point result. Every process ends with a pristine child to verify
baseline retention. All Close calls succeed; final active mappings are0 in every
process. This does not constitute release Qualification, every teardown fault
path, real disk durability or both-platform acceptance.

The fixed comparison is complete. Recommendation: candidate review, strongest
objection the consistent approximately5% large repeated-scan slowdown. Accepting
it is a product choice about startup/RSS versus query cache, not another missing
sample. If unacceptable, retain16MiB and close this experiment; don't start a
parameter sweep. If accepted, specify the smallest canonical configuration diff,
regenerate and validate both supported platforms before main-adoption review.

## Recompute and reproduce

```sh
python3 benchmarks/issue88poolab/results/analyze.py --check
```

Read-only summary verification needs only committed observations.json. The compact
bundle retains all40 process records, individual measurements/warmups, effective
values, physical size, RSS and cleanup. SHA256SUMS.json covers the bundle.

For a new measurement, prepare a clean disposable worktree from this branch.
Use the same toolchain/host, explicit8GiB free reserve and10GiB owned budget:

```sh
python3 scripts/experiment_disk.py --work-dir WORKSPACE --min-free-gib 8 --budget-gib 10 --timeout 1200 -- python3 WORKTREE/benchmarks/issue88poolab/run.py WORKSPACE
```

WORKSPACE contains worktree/,temp/,evidence/. The runner checks actual clean
source identity and no runtime/guest/release/module diff from pinned main before
build, records new identities, executes selector tests and the finite40 processes.
Build/download costs are excluded. Original run used an external copy of that
runner; checked-in copy adds an explicit workspace argument for reproduction.
Combine the40 result JSON files in pair/fixture/mode/arm order into observations
with pair numbers, then run the analyzer. Preserve compact evidence and finalize/
clean owned scratch. Default2h active/30min tooling budget, zero heavy CI runs;
no new measurement infrastructure or ongoing campaign is introduced.
