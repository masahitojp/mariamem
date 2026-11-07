# Remaining InnoDB startup attribution

Conclusion: **transaction-list startup is the dominant measured work** in the existing-data route. `trx_lists_init_at_db_start()` accounts for 5.620ms / 7.059ms (79.6%) of Fork's broad open/recovery interval, and 88.3% of its 6.363ms difference from Fresh within that interval. Normal startup `recv_sys.apply(true)` call time is only 0.002ms here. Do not describe the broad difference as redo application or snapshot byte copying.

Recommendation: if continuing, split the transaction-list function into `purge_sys.create()`, `trx_rseg_array_init()` and the remaining/empty-UNDO branch. Do not skip recovery or validation. No optimization or shared-state design is established by this measurement.

Strongest objection: this is one macOS host with observers enabled. The transaction-list function includes runtime management creation and potentially transaction resurrection. No counter here proves that the actual UNDO list was empty or how many redo pages were applied. The result localizes elapsed time to a function; it does not establish its internal cause, stage CPU, or an achievable speedup.

## Per-child partition

P1, three alternating 48-child pairs. Values below are means across equal-sized processes (144 primary children per route), ms. Zero means the particular route-specific call/region did not run; it does not mean Fresh does no transaction/dictionary initialization elsewhere.

| Non-overlapping component | Fresh | Fork |
|---|---:|---:|
| Before system-space call (checkpoint/fresh preflight) | 0.0125 | 0.0264 |
| System-space open/create | 0.0210 | 0.2317 |
| UNDO tablespace init | 0.0691 | 0.2204 |
| Recovery entry/body, before close_files | 0.0000 | 0.1873 |
| Dictionary create (Fresh route) | 0.0960 | 0.0000 |
| Dictionary boot (existing route) | 0.0000 | 0.0791 |
| Normal startup redo apply call | 0.0000 | 0.0020 |
| System dictionary load region | 0.0000 | 0.3843 |
| Transaction lists startup | 0.0000 | 5.6203 |
| Other, including gaps and unmeasured setup | 0.4971 | 0.3074 |
| **Host-clock broad interval total** | **0.6957** | **7.0590** |

The residual is explicitly retained. Every child's components plus residual add back to the same host-clock outer interval. The legacy guest-clock broad interval is also checked for containment/timing consistency. No medians of different components are added together.

| Fork metric | Mean | Median of process p50 | Median of process p95 | >100ms primary children |
|---|---:|---:|---:|---:|
| Transaction-list startup | 5.6203 | 5.3181 | 6.8627 | 0 |
| Host broad interval | 7.0590 | 6.8532 | 8.2636 | 0 |

Across the three pairs, Fork transaction-list means are **5.6512 / 5.4294 / 5.7804ms**. Broad Fork-minus-Fresh deltas are **6.4093 / 6.1676 / 6.5130ms**. No primary stage or API span exceeded 100ms and none was excluded.

## What this changes in our understanding

Fresh has no prior application transaction history initially, but creates redo/UNDO structures and system pages. Fork attaches shared snapshot file-block views and follows existing-database startup. The expensive call is not copying the entire database. The pinned native source calls `purge_sys.create()` and `trx_rseg_array_init()` before testing `trx_sys.is_undo_empty()`, so even an empty history would not eliminate this setup. Which part costs the 5.62ms remains unknown.

The small redo-apply call time makes it an unsuitable optimization priority for this specific workload. It does not prove that all workloads have no redo/UNDO work, nor does it prove zero applied pages. Fresh's creation work occurs in other places too; this table is a partition of one interval, not all startup work.

## Binding and correctness

Measured source_commit: `a3fe6e1509e6108c2fd70708e260e486fb952083`. Guest SHA256 unchanged: `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`. Native source basis: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e` (MariaDB12.3.3), four re-fetched files verified against retained blob/SHA256 identities.

Exact generated mapping: srv_start caller Fn18569; UNDO tablespaces Fn17510; dictionary create Fn17052; dictionary boot Fn17054; transaction-list startup Fn18291. Recovery is inlined between L1752 and L1850; the latter precedes close_files' vector iteration. System dictionary loading is L3479 through L3613, including four normal index loads, load_sys_tables and mtr destruction. Normal redo apply is the Fn17465 call at L3470, with its surrounding mutex/concurrency work retained in residual. Whole generated-file hash and unique caller needles fail closed. layout.json in the parent directory and mapping-verification.json record identities and native/source anchors.

One combined Go binary, no guest rebuild. Both routes use the same warm static-page prototype and have a baseline prepared before children. Fresh creates child schema/seed; Fork uses that baseline. P1 fixed waves fully dispose before advancing. Two positive semantic pilots (4 children each), two wrong-seed controls (1 each), two warmups (48 each), six primary processes (48 each): **12 processes /394 children**, all observers on. No repeated attempts or additional samples. Complete child owner logs retained without truncation.

All positive processes and expected negative controls, actual branch markers, route-specific phase coverage, interval nesting/non-overlap, exact COUNT/SUM state oracle, wave ordering, zero final mappings and image FDs passed. Controlled wrong-seed failures clean up. Race harness units and base observer units passed. Nine private-copy analysis mutations are rejected; phase mutations rebind trace checksums so checksum integrity alone cannot satisfy the phase negative tests. No Linux/native SQL parity/product adoption claim is made.

The diagnostic Go build took 132.1s (the full build script also ran focused units). This task made one build, 12 measurement processes and no CI submissions. Absolute timings differ from the previous observer-on campaign; do not treat 9.19 -> 7.06ms as an optimization, because instrumentation/compiler layout and host conditions are different. Paired attribution is within this campaign only.

## Replay and retention

From this results directory: `python3 -B analyze.py . --check`, then `python3 -B check_analysis.py`. These require no temp/build state and leave original inputs unchanged. SHA256SUMS.json covers every retained file. summary.json contains process quantiles, means and all paired deltas. observations.json.gz retains every child trace; original-process-reports.tar.gz retains unmodified reports, console and merged timing JSON. Every owner archive, original file/member hash and archive digest is preserved. process-observation.json alone normalizes the owned local workspace prefix; original/published hashes are recorded.

To regenerate a new campaign: check out the measured source in an owned experiment worktree, use the parent plan/budgets, run `python3 -B benchmarks/innodbremainder/build.py` then run.py. This is a recipe, not authorization for new samples. The optional upstream re-fetch script uses the fixed source-files.json identities; its original plan/source_commit comes from docs/reviews/innodb-startup-source/plan.json (the campaign plan's source is the generated Go product source, not the upstream commit).

No product/API/guest-source/generated-source changes, main integration, qualification, version or release is included. A follow-up split can reuse this harness: at most30min mapping/tooling, one diagnostic Go build <=20min and the same <=15min finite P1 matrix; if exact boundaries cannot be mapped, stop without a guest rebuild and report missing evidence/cost.
