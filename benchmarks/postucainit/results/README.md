# Issue121: remaining initialization after UCA adoption

**Conclusion:** the bounded investigation is complete. Current Fork still reconstructs substantial engine state: in the diagnostic P1 cohort, common initialization p50 is7.33ms and the InnoDB plugin9.52ms. Within InnoDB, the broad existing-file/open/recovery interval is6.49ms, compared with buffer-pool creation1.35ms. These are elapsed intervals, not removable CPU or a measured attribution of the whole pgmem difference.

**Recommendation:** for an immediately bounded configuration trial, select existing #88 (16→8MiB), with modest Fork expectations and explicit SQL/RSS tradeoffs. For a potentially larger local change, first assess build-time preparation of immutable charset registration/lookup data remaining in common initialization. Do not clone the whole live engine or bypass recovery. The strongest objection is that #88's directly targeted interval is small and the exclusive remaining charset cost is unmeasured; neither candidate promises to eliminate the pgmem gap. Candidate selection/implementation/adoption remain a separate decision.

[Issue121](https://github.com/masahitojp/mariamem/issues/121) · [summary](summary.json) · [all primary child spans](children.csv) · [exact inputs](inputs.json)

## What was missing, and what ran

The previous full-lifecycle comparison preserved UNDO owner events but no startup/initialization traces. The previous UCA stage campaign preserved guest startup markers but did not enable the finer initialization markers. Their original sources/results remain unchanged; prior-audit.json records this check. origin/main was still66f2fe9d when this task began.

The existing guest already contains common/plugin/InnoDB hooks. We reused the original stage/UNDO overlays and enabled MARIAMEM_INIT_DIAGNOSTICS only when guest timing is enabled. No C/guest rebuild, changed setting, product behavior or public API was needed. Actual observer code and before/after hashes are preserved, not substituted for canonical source.

Apple M1/16GiB/macOS27.2, Go1.27.3, GOMAXPROCS8, GOGC100, Pipe,1,000 integer rows,48 children, cap=P, product defaults. One binary runs observer off/on. Three alternating pairs each at P1/P4; P order rotates. Four separate warmups, positive4-child P4 pilot, wrong-seed1-child negative pilot:18 processes/773 children,576 primary children. No omitted tail, replacement or extra repetition. Compilation and downloads are outside observations. API suite includes preparation/capture/final Close. The process-wall collector starts after disk preflight, correcting the optional-field limitation in the prior harness without relabelling old measurements.

## Ordinary timing and observer cost

Pooled child quantiles over3×48 children per cell. These children are not144 independent process replications; process-level values are separately retained.

| P | observer | Fork p50 | Fork p95 | all3 API-suite wall ms |
|---|---|---:|---:|---|
|1|off|26.02|29.65|1688.0 /1719.9 /1655.5|
|1|on|27.96|32.26|1803.2 /1806.4 /1806.8|
|4|off|35.20|52.93|659.8 /643.4 /666.5|
|4|on|41.45|61.51|754.9 /732.4 /787.2|

Median paired process-Fork-p50 observer increase:1.87ms P1 /5.82ms P4. The observer combines startup/initialization counters, trace serialization and UNDO ownership capture. It also changes scheduling and COUNT/SUM timing; do not subtract one constant correction or use its wall/CPU as product performance. Ordinary primary Fork, COUNT/SUM and UPDATE each have zero>100ms spans here. This does not establish a tail rate or resolve #68; a long warmup remains in the original observations.

## Diagnostic stage breakdown

Milliseconds; pooled child p50, with P4 p95. Independent medians are not additive. summary.json also retains additive means, all process-level Fork/CPU/suite metrics and>100ms counts. No primary diagnostic server_init exceeds100ms.

| Interval | P1 p50 | P4 p50 | P4 p95 |
|---|---:|---:|---:|
| server_init total |22.75|31.19|53.44|
| common, before components |7.33|8.79|13.69|
| components before plugins |1.29|1.63|3.26|
| ↳ MyISAM key-cache initialization |1.24|1.55|3.14|
| all plugins |12.82|18.11|41.46|
| ↳ InnoDB |9.52|11.85|26.03|
| ↳ Aria |1.58|2.54|7.14|
| ↳ caching_sha2_password |0.60|0.63|4.09|
| components after plugins |0.85|0.93|4.16|

| Inside InnoDB | P1 p50 | P4 p50 |
|---|---:|---:|
| parameters-complete → buffer-pool begin |0.43|0.51|
| buffer-pool creation |1.35|1.68|
| memory/background setup after pool |0.03|0.04|
| existing-file checks/open/recovery |6.49|7.35|
| transaction section after that interval |0.14|0.15|
| background section |0.99|1.25|

P1 process medians for the broad open/recovery interval are6.504/6.469/6.527ms; for common initialization7.089/7.878/7.355ms. Both remain in each process. P4 open/recovery medians7.947/7.077/7.078ms. No precision inference beyond this finite single-host cohort.

On additive means, server_init increases23.19→32.98ms from P1→P4: InnoDB+4.13ms, Aria+1.73ms and common+1.49ms are large contributors. They are not independent CPU costs. The first P4 group (indices0–3) has server_init p50 50.25ms, later children30.72ms; both groups remain in the aggregate. A broad spread plus first-group contention is observed, not proof of one scheduler/I/O cause or a P4 hard ceiling.

## Source interpretation and resource limits

Fixed upstream source83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e, the adopted guest patches, and scripts/guest_init_hooks.py define these markers. Source hashes and selected line-numbered excerpts are retained. They are interpretation support; a snapshot of unpatched upstream is not the generated guest identity.

- Common initialization includes my_timer_init and init_common_variables. The latter still resolves character_set_collations and charset registrations. The adopted UCA prepared table removes one expensive construction, not all common work. Old #100 registry/handler timings cannot be relabelled as this source's exclusive costs. The current7.33ms is not a cacheable constant or a predicted saving.
- The broad InnoDB interval starts before the existing/new-database branch at srv0start.cc:1400 and ends before doublewrite creation at:1769. The existing-data route includes find_checkpoint, system/UNDO tablespace open, trx_sys.create, recv_recovery_from_checkpoint_start, dict_boot, redo apply, table and transaction-list initialization and integrity checks. A clean shutdown still follows the recovery entry. This is not6.49ms of physical I/O or6.49ms of replayed redo.
- Within that interval, P1 median wrapped read bytes are8,908,800 and wrapped successful I/O-call duration0.559ms, with no wrapped writes in the interval. The wrappers exclude libc-internal/mapped calls and may observe background work; they do not establish exclusive CPU, physical disk time or a removable copy cost. Do not subtract0.559 from6.49 and call the remainder CPU.
- P1 common wrapped allocation requests areabout5.90MiB; buffer-pool requests about16.08MiB. MyISAM key-cache initialization requests about15.92MiB and grows linear-memory addressability byabout128.06MiB. These are guest allocator/memory-growth counters, **not retained RSS**, and no current effective SQL setting was separately queried. No automatic third cache-tuning campaign is added.
- Guest process/thread CPU readings are null throughout. Whole-process CPU is retained separately; no per-plugin CPU claim is made.

## At most two next candidates

1. **Existing #88,16→8MiB buffer pool: small A/B is justified; default adoption is not.** The mechanism is smaller allocation/initialization and possibly lower retained RSS. Direct pool initialization is1.35ms at P1, so promise no10–20ms saving. Its downstream SQL/cache effects can exceed that interval in either direction. Keep the original effective-setting check, small and cache-exceeding fixture, held-child RSS and correctness/cleanup gates. The original finite5-pair plan is the next execution boundary, not a parameter sweep.
2. **Remaining common-init immutable data: source feasibility before a prototype.** Check whether registration/lookup structures can be emitted as immutable build-time data with per-child mutable state intact, extending the successful narrow-preparation approach without copying locks/TLS/host pointers or a live allocator. Current common-init is a substantial target, but its exclusively immutable share is missing evidence. Bound the next feasibility read to1hour, no measurement/build: enumerate actual structures, ownership/relocation and exact consumer references, then select one concrete table or defer. Do not spend an open-ended campaign trying to remove all7ms. A later prototype would need Unicode/collation/native-oracle and SQL-cost checks; this report does not authorize or implement it.

The InnoDB open/recovery interval is an important finding but **not yet a safe optimization candidate**. Removing checks or setting force-recovery to gain time would alter guarantees. This investigation stops without another nested instrumentation round. #103 whole-template reuse still lacks a safe cloning boundary. #119 cleanup overlap is independent, and #68 stays stopped.

## Relation to pgmem

The preceding ordinary comparison at fixed pgmem a61005d3 reported P4 Fork35.7/11.2ms and full suite708/373ms (mariamem/pgmem). Its source shows FS clone plus new cluster startup, not live PostgreSQL-memory cloning; connection backend work is deferred to connection establishment, and Close completion differs. This new experiment did not instrument PostgreSQL or remeasure it. It identifies mariamem's remaining costs, not an exclusive subtraction of engine internals across products. Fresh's additional pgmem unpack/setup/GC path also explains why a slower Fresh and faster Fork can coexist without contradiction.

## Verification, source and reproduction

- Product source_commit66f2fe9d4bbde9b20323e9ee9b1562f3af16b8a4; guest6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe. Harness source_commit3cfc71a256ea4d4739853fa7a314ca2dd260df48. Commit-object identity checked with git_identity; clean source, benchmark-only product delta, binary stamp and overlay hashes checked before execution.
- All772 positive children have SQL/independence/cleanup PASS; wrong-seed child fails the intended oracle and cleans up. All18 processes end with zero owned mappings/reserved/RW bytes and zero grow/release failures. Traces bind to each child via its context. No initialization drops or failed plugin markers.
- A reducer pilot exposed repeated plugin names: uuid appears twice for distinct registrations. The reducer pairs every invocation in original order and sums repeated names; it does not overwrite one with a dictionary entry. Four focused tests cover this case plus missing marker, drop, ordering/unpaired events, incomplete/duplicate matrix, cleanup leak and failed SQL mutations.
- All389 observer-on child UNDO traces are retained with original per-instance owner binding:100,224 complete purge scopes,0 aborts,3 query-rseg waits,6 background page waits,0 matched relays; max2,773 events/child. They do not explain a previous primary COUNT tail. No wait-triggered repetitions.
- `python3 -B analyze.py --check` and `python3 -B test_analysis.py` work from compact files without temp/build trees. Compact observations preserve every process/sample and stage event; resource deltas are separate. Full original counters/files are digest-bound in a local compressed archive, alongside389 owner traces; `diagnose.py --check` replays those local archives.
- Recreate the owned workspace on measured harness3cfc71a2, run benchmarks/postucainit/build.py then run.py with the recorded disk guard. New timings are new observations. Build/download costs are separate. All raw tails/pilots remain; no product change, main merge, CI, Qualification or release in this task.
