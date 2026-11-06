# Current mariamem versus pgmem — matched full Fresh/Fork suite

**Conclusion:** Fresh favors mariamem in all10 paired comparisons; Snapshot/Fork favors pgmem in all10 pairs. At P4, API-suite medians are666ms versus1,823ms for Fresh and708ms versus373ms for Fork. The remaining Fork gap is about1.9x on the ratio of independent medians. The small-fixture Fresh/Fork crossover in mariamem remains close; pgmem benefits much more from its Fork path.

Single Apple M1 /16GiB /macOS27.2; Go1.27.3, CGO0, GOMAXPROCS8, GOGC100. Pipe route,1,000 integer rows,48 cases. Product defaults; pgmem explicitly uses Database=test. This is a new cohort; previous mariamem/0.6.2 timings are not pooled.

[Standalone graph](report.html) · [All data](summary.json) · [Child phases](children.csv) · [Inputs](inputs.json)

## Complete API-suite elapsed

Measured from first Start through final root/Snapshot/child Close return, including preparation/capture. Five fresh-process medians and full ranges; ratios below divide independent medians. The pair data and paired percentages are retained separately in summary.json.

| Mode | P | mariamem ms [range] | pgmem ms [range] | mariamem / pgmem | Faster in all5 pairs |
|---|---:|---|---|---:|---|
|fresh|1|1721.1 [1676.3–1818.1]|3569.9 [3523.2–3611.1]|0.48x|mariamem|
|fresh|4|666.3 [661.4–741.8]|1823.2 [1761.9–1874.7]|0.37x|mariamem|
|fork|1|1707.0 [1638.8–1822.0]|665.5 [648.7–687.1]|2.56x|pgmem|
|fork|4|707.5 [647.8–884.5]|372.7 [347.2–409.8]|1.90x|pgmem|

## CPU time

API CPU is user+system across all threads during the same API suite. Process CPU is the independent child-rusage delta around spawn/wait and includes work outside the API timing until OS process exit. Neither is CPU utilization or exclusively Fork CPU.

| Mode | P | mariamem API CPU ms | pgmem API CPU ms | mariamem process CPU ms | pgmem process CPU ms |
|---|---:|---:|---:|---:|---:|
|fresh|1|2712.9|5879.6|2724.2|5959.6|
|fresh|4|3492.5|8370.5|3504.5|8456.2|
|fork|1|2541.2|939.0|2552.7|983.2|
|fork|4|3173.1|1307.6|3185.3|1353.1|

Including process CPU preserves the same direction. Pure process-exit **wall** time is unavailable: the measured controller starts that timer before the preflight disk guard, adding roughly a few hundred milliseconds. The misleadingly named external_process_ms is preserved but not used as a clean process-wall metric or chart. The report commit moves the timer after preflight for future new cohorts. No extra repeated campaign is added to repair this optional field; assessment.json records the missing evidence and bounded recovery cost.

## Child phase elapsed

Median of five process-level child medians, milliseconds. Retire includes connection/pool Close and, for mariamem, WaitDisconnected. PG has no identical WaitDisconnected step. Independent phase medians must not be added as an exact decomposition.

| Product | Mode | P | Start/Fork | Connect | Seed | COUNT/SUM | UPDATE | Retire | DB.Close |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
|mariamem|fresh|1|23.50|0.32|7.47|0.76|0.20|0.056|2.615|
|pgmem|fresh|1|65.76|2.86|3.72|0.09|0.22|0.010|0.069|
|mariamem|fresh|4|31.78|0.65|11.42|1.05|0.32|0.097|5.319|
|pgmem|fresh|4|125.28|5.12|5.63|0.11|0.35|0.012|0.159|
|mariamem|fork|1|26.37|0.33|0.00|2.42|0.25|0.054|4.250|
|pgmem|fork|1|5.96|2.77|0.00|0.52|1.95|0.012|0.093|
|mariamem|fork|4|35.67|0.67|0.00|4.66|0.45|0.110|5.196|
|pgmem|fork|4|11.16|6.69|0.00|0.95|3.44|0.012|0.161|

At P4 Fork, mariamem Start/Fork remains about35.7ms versus11.2ms. Connection establishment is cheaper for mariamem (0.67 versus6.69ms), while its COUNT/SUM and completed Close are more expensive in this recipe. The whole-suite gap is therefore not solely the last Close. Phase medians describe typical operations, not a proof of cause or an exact critical-path sum.

Fresh includes recreating the schema/seed for each child. Fork prepares/captures one root and then reuses it. PostgreSQL starts an additional requested test database in this fixed Database=test profile; this is not a measurement of the default postgres database or a pure engine-only comparison. Different engines, drivers, prepared behavior and shutdown work remain.

## Close completion is different

- mariamem retires its session workers and guest execution, releases owned mappings and removes its temporary area before confirmed disposal/slot release. Non-cooperative or failed cleanup retains ownership/capacity; Close is not a promise of immediate RSS decrease.
- pgmem Server.Close stops the listener and kills its discarded cluster, then returns its Fork slot. Process.Done is signaled before module.Close, and shared segment-file cleanup is asynchronous. Client sockets may linger. Kill has a timeout/log path rather than a full disposal error result.
- Thus the very small pgmem Close spans are not equivalent to complete module/segment/client retirement. API-suite timing is useful for caller latency but not an equal-resource-drain benchmark. Process exit can terminate outstanding Go cleanup and leave OS reclamation to process teardown; it does not establish that every asynchronous cleanup callback completed.

Pinned source: [pgmem Server.Close](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/pgmem.go#L235), [engine process/kill](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/internal/engine/cluster.go#L106), [mariamem disposal](https://github.com/masahitojp/mariamem/blob/66f2fe9d4bbde9b20323e9ee9b1562f3af16b8a4/internal/host/disposal.go).

## Tails, controls and observer

-40 primary processes /1,920 children; all SQL/version/pristine count+sum/one-row mutation/value/isolation/cap and cleanup oracles pass. Each product/mode has a positive2-child pilot and wrong-seed1-child control (8 processes), plus8 warmups and2 mariamem-only diagnostics:58 total. Public MaxForks() is read back for both products. Logical case concurrency is bounded by P; asynchronous PG cleanup is not included in that logical count.
- One primary SQL>100ms: mariamem Fork P4 rep2, child3 COUNT/SUM800.95ms. All other primary cells, including pgmem, have zero. That child and process are retained. All five P4 Fork pairs still favor pgmem; the observed difference is not confined to that one tail. This does not identify the cause or establish a product-wide tail rate.
- Separate mariamem P4 Fresh/Fork diagnostic runs retain96 complete UNDO holder traces. No UPDATE>100ms in either diagnostic. There are25,472 complete purge scopes, zero aborts, zero query-rseg atomic waits,906 background page waits and no bound query→purge→page relay; maximum3,715 events/child remains below8,192. These startup/background observations are not attributions of the uninstrumented primary COUNT tail.
- Owner IDs/pages are linked only inside the original instance. IO/WRITE_FIX snapshots describe internal ownership, not physical disk latency. Primary timing has no detailed observer; diagnostic timing is excluded. #68 stays stopped.

## Limits and reproduction

- One host, small fixture, five pairs/cell; no statistical significance, general support/performance or retained-memory claim. Lifetime MaxRSS raw fields are not per-child retained RSS.
- Product order alternates within adjacent pairs and the four mode/P cells rotate over five rounds; first-arm counts are3/2 because five is odd. No outlier omission, replacement or extra measurement repeat.
- mariamem source_commit:66f2fe9d4bbde9b20323e9ee9b1562f3af16b8a4 (UCA+notification adopted). pgmem v1.18.2 source_commit:a61005d37d01e6671f814fe8ca828222e8147df4; annotated tag_object_sha:145e5d2fc70983b89a4bdd8438e547fcd60244ed.
- Measured harness source_commit:5792b9788bf90c311893582e1e0196a775738ade. Binary VCS stamps identify the harness, while inputs.json separately binds replaced library source, toolchain and binary SHA. Commit/tag objects and clean sources were verified before build. PG guest_sha256 is explicitly null; its compiled inputs are identified by the pinned upstream source rather than an invented MariaDB-style guest hash.
- Identical harness and basic SQL/oracles for both wrappers. Driver pins:mysql1.9.3 andpgx5.11.0, retaining their defaults. Builds/downloads and warmups are outside primary timing.

Run `python3 analyze.py --check` beside the saved files for read-only summary/CSV replay without build/temp trees or file writes. `test_analysis.py` exercises rejected-oracle mutations and the complete58-record matrix; test_undo.py retains the binding mutations. All58 full numeric observations are in observations.json.

Original JSON/console outputs and96 owner traces are in verified compressed local evidence under build/experiment-work/pgmem-current-lifecycle/evidence/published; archive and member digests are recorded. `python3 diagnose.py --check` replays holder reduction beside that retained archive. The report, all numeric process data, source and checksums are preserved on the experiment branch, with no automatic main merge.

For the original measurement recipe, recreate the workspace at harness5792b978, clone the pinned PG tag into temp/pgmem, run benchmarks/pgcurrentlifecycle/build.py and run.py. For corrected process-wall observations, use the later timer-fix source and treat results as a new cohort. No runtime/product/API/setting/default/CI/release change is made by this measurement.
