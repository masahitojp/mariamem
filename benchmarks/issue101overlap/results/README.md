# Issue101: mixed versus phased Fork/SQL/Close

## Conclusion to the original question

**Keep the existing mixed scheduling.** This fixed experiment does not support
separating application Fork, SQL and cleanup into global waves as a general way
to shorten the suite. At P4, removing cross-child SQL/cleanup overlap did not
reduce typical Fork time and made every suite slower. At P8, typical Fork is
somewhat shorter in two of three pairs, but whole-suite results are mixed and
one phased run is much slower because two long SQL calls stall entire waves.
No claim about CPU bandwidth, scheduler, a specific InnoDB lock, or a product fix
follows. This finite investigation is complete; no extra sampling is recommended.

This is a new cohort, not a reanalysis of the historical 34ms/692ms figures.
The earlier Close timeout investigation is paused by Human decision. This run
neither fixes nor dismisses it; no unexpected Close failure occurred here.

## Inputs and fixed scope

Human approved this comparison on 2026-11-10 after the Issue101 proposal.

- Product source_commit: `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`.
- Measured harness source_commit: `6c48c1784acbbeac0b7e7dd64f2539ee674e272f`.
  Only `benchmarks/issue101overlap/` differs from the product source. No product,
  guest, generated, public API, option or release change.
- One binary SHA256:
  `b1d6b30f0a04f7bc42c193c00e271691c34e14af2d90dc3592248e53853b64f7`.
  Both arms select their scheduler at runtime. Exact input/toolchain/module and
  source tree identities are in [inputs.json](inputs.json).
- Apple M1 / macOS27.2 arm64, Go1.26.10, CGO0, GOMAXPROCS8, GOGC100,
  Go Pipe, default read1/16MiB buffer pool, 1,000 integer rows, 48 independent
  children per suite. Fork cap equals P4 or P8 in both arms.
- Three alternating pairs at each P. Four distinct warmups and four controls
  precede the twelve primary processes. Four separately instrumented diagnostic
  processes follow; none are pooled with primary speed results.
- 24 workload processes, no retries or discarded primary outliers. 22 normal
  processes succeed; the two wrong-seed controls fail their intended oracle and
  successfully dispose resources. Primary SQL/isolation checks pass for 576
  children. All controls/results retain their kind in runs.json.
- A pre-measurement Go module-name collision was corrected at the measured
  commit. The earlier build attempt ran no workload. Its error is preserved;
  it is not silently relabeled as a measurement failure or retry.

This was a shared Mac, with desktop/virtualization/on-device services active;
[host-load-note.json](host-load-note.json) records sampled background activity.
There was no other observed Go build at the build preflight; our own build had
finished before workloads. This is exploratory scheduling evidence, not an
isolated-host performance guarantee or Ubuntu acceptance.

## What differs

Mixed: each of P workers repeats Fork → connect/SQL → retire/Close and immediately
starts its next child. Phased: create at most P children, wait for all Fork calls,
run connect/SQL for all, wait for all SQL to finish, retire/Close all, then admit
the next wave. Both retain capacity until cleanup completes. The same one()
function owns SQL, oracles and cleanup in both modes.

All barrier waits, initial root preparation/Snapshot and final cleanup are charged
to suite time. Batch excludes initial root preparation but includes child cleanup.
The observer distinguishes Fork call time from waiting at the post-Fork barrier.
The phased schedule is **not an isolated change to CPU sharing**: it also changes
burstiness, SQL timing, idle gaps and how tails delay later admissions.

## Primary comparison

Each table cell is a median across three processes. Fork p50 is calculated per
process first, then the median of those three p50 values. CPU covers the complete
suite, not Fork alone. RSS is process lifetime high-water, not retained child RSS.

| P | Metric | Mixed | Phased |
|---|---|---:|---:|
|4|Whole suite, ms|472.856|502.989|
|4|48-child batch, ms|416.448|445.185|
|4|Per-process Fork p50, ms|24.336|25.329|
|4|Per-process Fork p95, ms|29.545|30.882|
|4|Whole process CPU, ms|2234.248|2145.649|
|4|Lifetime peak RSS, MiB|421.188|435.422|
|8|Whole suite, ms|422.054|428.315|
|8|48-child batch, ms|361.558|369.818|
|8|Per-process Fork p50, ms|40.111|37.632|
|8|Per-process Fork p95, ms|56.085|47.429|
|8|Whole process CPU, ms|2405.034|2319.689|
|8|Lifetime peak RSS, MiB|631.141|617.500|

Do not read the P8 median as stable equivalence; all three pairs follow.

| P | Pair | Mixed suite, ms | Phased suite, ms | Phased change |
|---|---:|---:|---:|---:|
|4|0|472.856|502.989|+6.37%|
|4|1|449.247|497.431|+10.73%|
|4|2|476.643|507.855|+6.55%|
|8|0|553.707|428.315|−22.65%|
|8|1|422.054|419.639|−0.57%|
|8|2|409.000|1185.956|+189.97%|

P4 per-pair Fork p50 changes are −0.147, +1.517, +0.745ms. P8 changes are
+1.059, −5.346, −2.208ms. The largest whole-suite win is not a corresponding
Fork-p50 win, so whole-suite speed must not be attributed solely to faster Fork.

## Did the intervention actually remove overlap?

Yes. From the saved common-clock child intervals, each Fork is intersected with
other children's connect/SQL and retire/Close intervals; overlapping intervals
are unioned to avoid double counting. Per-process fractions use total such
intersection time divided by total Fork time. Median fractions are29.63% at P4
and55.99% at P8 for mixed; every phased primary has exactly zero.

The verifier also asserts that each wave finishes every Fork before any connect,
finishes every SQL before any retire, and finishes every Close before the next
wave starts. SQL/cap/cleanup checks and these ordering assertions are independent
of the timing comparison.

Despite removing that overlap, phased Fork still rises from about25.3ms at P4 to
37.6ms at P8. Other children's application SQL/Close overlap therefore does not
explain all parallel Fork growth. Startup versus startup contention and internal
background engine work remain possible; this experiment does not isolate them.

## Why did the phased P8 run take1.186 seconds?

In pair2, child30 COUNT/SUM took380.811ms and child40 COUNT/SUM took388.345ms.
Other seven children in each wave spent about378–379ms or385–387ms at the SQL
barrier. Do not sum those seven waits into suite wall: they happen concurrently.

The critical SQL wall interval for each eight-child wave was:

| First child | Pair0, ms | Pair1, ms | Pair2, ms |
|---:|---:|---:|---:|
|0|3.301|3.948|5.536|
|8|3.471|8.524|5.587|
|16|4.286|3.302|9.505|
|24|4.741|3.557|384.529|
|32|4.769|5.263|7.278|
|40|4.513|3.242|391.158|

The two delayed waves account for roughly0.77 seconds of SQL wall. Their Fork
wave intervals were43.104 and41.622ms; cleanup intervals9.010 and13.143ms.
The time expansion is in SQL plus the enforced all-child barrier, not a40-second
Close timeout. Mixed P8 pair0 also contains a397.740ms COUNT/SUM. Neither arm
eliminates long SQL tails. There is no internal owner/lock trace here, so do not
assign these waits to Issue140's PREPARE or Issue143's old UPDATE mechanism.

## Diagnostic scope and missing attribution

The separately instrumented four processes provide48 bound outer Fork traces
per process. Their startup envelope (snapshot_handle_ready → startup_returned)
p50 values are: P4 mixed26.121/phased26.662ms; P8 mixed41.506/phased41.393ms.
They do not contradict the P4 result, and provide no stable P8 Fork advantage.
These are one process per cell with timing enabled, not additional primary pairs.

**Per-child server_init is unavailable in this campaign.** The callback retains
only the final outer Fork trace, overwriting nested operation traces in its
child-named file. Automatically emitted startup records also contain no guest
stage payload. The bound outer traces do not expose MariaDB server_init, memory
construction or InnoDB phases. This limitation was found during reduction; no
extra runs, guest changes or stage attribution by approximate matching were added.

If finer attribution is subsequently selected, use per-child *and operation*
record names, verify the required guest payload before primary timing, and budget
a new diagnostic-only run explicitly. That work is unnecessary to conclude that
the tested wave scheduling does not consistently reduce complete suite time.

## Validation and preservation

- Barrier unit/race checks: wait-for-all, cancellation and Fork-error participation
  pass. Real wrong-seed controls complete cleanup in both scheduling modes.
- All processes respect capacity and finish with zero active mapping/RW/reserved
  bytes and release failures, creates equal releases, and empty scratch.
- Read-only compact replay recomputes summaries and checks phase separation,
  original SQL oracles, cleanup, per-child trace census and SHA256SUMS.
- Four semantic mutations are rejected without relying on checksum failure:
  cross-wave overlap, occupied mapping, failed child oracle and missing trace.
- Read-only replay: `python3 benchmarks/issue101overlap/results/analyze.py --check`.
- Per-child public spans are in children.csv, outcomes/root spans in trials.json,
  bound outer traces in stages.json. Summary includes all runs and separate kinds.
  Original raw successful reports/trace hashes are in original-files-sha256.json;
  there is no unexpected failed workload to retain. No raw CI artifact bundle.

To reproduce a newly authorized run, use the experiment-workspace helper with
6GiB owned /12GiB free-space budget. Check out measured harness6c48c178 as its
clean worktree, then run build.py followed by run.py with a1800-second runner
budget. The scripts require Go1.26.10, verify commit identity/clean source and
build one binary. The plan fixes24 workload processes and stops on unexpected
failure. Reduction/replay tooling added after measurement is not relabeled as
measured source. Rebuilding/downloading/compiling is outside measured time.

Recommendation: retain mixed scheduling and finish this bounded Issue101
comparison with its limits. Do not implement global phase barriers. If choosing
a further performance task, use evidence for a concrete initialization target or
consider the separately scoped prewarm design (#84); do not continue a broad
CPU/bandwidth investigation merely because the precise parallel slowdown remains
unknown. No public contract change, main adoption, version or release is implied.
