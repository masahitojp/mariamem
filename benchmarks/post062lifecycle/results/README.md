# 0.6.2 versus adopted UCA + disconnect notification

**Conclusion:** all20 paired full-suite comparisons favor the adopted main. CPU time also decreases in every pair. At P4, the Fork-versus-Fresh median gap narrows from19.5% to2.8%; these five-process cells do not establish a meaningful remaining ordering. At P1 the two current paths are within0.8%. This completes the fixed comparison; no new optimization or investigation is started.

Single Apple M1 /16GiB /macOS27.2; Go1.27.3, CGO0, GOMAXPROCS8, GOGC100. Same Pipe driver/SQL/1,000-row seed and48 independent cases. Product defaults. Compilation/downloads are outside timing.

[Standalone graph](report.html) · [Summary](summary.json) · [Per-child spans](children.csv) · [Inputs](inputs.json)

## Full-suite wall and CPU

Suite is measured from the first Start through the last child/root/Snapshot cleanup, including preparation/capture. Values below are medians of five fresh processes per cell. Change percentages are medians of paired percentages, not ratios of the two independent medians. All observations and tails are retained.

| Mode | P | 0.6.2 suite ms [range] | Main suite ms [range] | Paired wall change | Paired CPU change | Main faster /5 |
|---|---:|---|---|---:|---:|---:|
|fresh|1|2686.3 [2563.4–2692.0]|1914.1 [1870.6–1977.1]|-28.6%|-13.4%|5|
|fresh|4|985.8 [941.2–1026.1]|771.0 [765.3–822.5]|-20.5%|-18.0%|5|
|fork|1|2535.8 [2490.6–2565.1]|1900.1 [1872.7–1931.5]|-25.5%|-13.0%|5|
|fork|4|1178.4 [978.5–1665.3]|792.4 [763.9–962.9]|-31.6%|-13.6%|5|

## Fresh versus Snapshot/Fork

| Version | P | Fresh ms | Fork ms | Fork relative to Fresh |
|---|---:|---:|---:|---:|
|baseline|1|2686.3|2535.8|-5.6%|
|baseline|4|985.8|1178.4|+19.5%|
|current|1|1914.1|1900.1|-0.7%|
|current|4|771.0|792.4|+2.8%|

Fresh independently starts a DB and recreates schema/seed for each case. Fork starts and prepares one root, retires its connections, captures once, then acquires48 independent children with cap equal to P. Fresh root Start is outside the Snapshot limiter; its worker count still bounds simultaneous cases. Both paths retire pools, WaitDisconnected and Close every DB.

Current Fork has about50ms(P1)/54ms(P4) of one-off root preparation/capture. Fresh puts its preparation inside every child. Saving repeated seed work must offset that one-off cost plus differences in restored startup and SQL. This tiny fixture is close to that crossover; it does not show the benefit for expensive migrations. Do not add independent per-phase medians to reconstruct exact critical-path time.

## Typical child phases

Each value is the median of five process-level child medians, milliseconds. Retire includes connection/pool Close + WaitDisconnected. It does not include final Database.Close.

| Version | Mode | P | Start/Fork | Seed | COUNT/SUM | Retire | DB.Close |
|---|---|---:|---:|---:|---:|---:|---:|
|baseline|fresh|1|35.96|8.51|0.88|5.654|2.94|
|baseline|fresh|4|47.42|13.35|1.15|5.082|5.51|
|baseline|fork|1|39.61|0.00|2.61|5.651|2.38|
|baseline|fork|4|53.37|0.00|4.51|5.093|4.76|
|current|fresh|1|25.40|8.61|0.89|0.064|2.96|
|current|fresh|4|34.94|12.66|1.12|0.106|6.36|
|current|fork|1|29.51|0.00|2.68|0.061|4.86|
|current|fork|4|40.94|0.00|4.28|0.120|5.10|

The combined change reduces both new-DB startup and restored-DB startup. Retire falls from about5–6ms to0.06–0.12ms. Some cost appears in DB.Close sooner, especially Fork P1; do not call the entire removed wait pure CPU savings. The full-suite CPU measurement still improves in all20 pairs. This two-version experiment does not separately attribute the UCA and notification contributions.

## Tails, correctness and diagnostics

- All40 primary processes /1,920 children pass SQL/version/seed/value/affected-row/isolation/cap and cleanup checks. Four positive2-child pilots, four wrong-seed1-child controls, eight48-child warmups and two48-child diagnostics give58 total processes. No process or child is removed/replaced, and no extra measurement repeat is added.
- Primary SQL spans over100ms: baseline Fork P4 has3 spans/3 children; current Fork P4 has2 spans/2 children. All other primary cells have zero. The P4 Fork wall change is tail-sensitive; its five paired changes range from about−54% to−2%. This does not prove a reduced rate or cause of SQL tails.
- Separate current-only P4 diagnostics retain96 complete UNDO holder traces,26,112 complete purge scopes, zero aborts and a maximum4,576 events per child (limit8,192). Neither diagnostic process has UPDATE over100ms. Three query rseg waits and258 background page waits are recorded; no matching query→purge→page relay is bound. The maximum recorded background page wait is28.31ms.
- The owner records are point-in-time snapshots in their original instance; identifiers are not joined across DB instances or between incompatible thread-ID domains. IO/WRITE_FIX is an internal owner state, not evidence of physical disk latency. No #68 reopening follows.
- Baseline generated identity differs, so the existing diagnostic overlay is not applied to0.6.2. Diagnostic timing is excluded from primary statistics. Uninstrumented primary SQL tails have no owner attribution.

## Boundaries and limitations

- One host, one small fixture, five paired processes per cell. No general workload/platform speed promise or statistical significance claim. Other hosts, larger preparation and current-versus-pgmem are not measured here.
- Both versions are compiled under the same Go1.27.3 toolchain; this is a source comparison, not execution of the old shipped Go1.26.10 binary. Both use MariaDB12.3.3 with different guest build identities.
- API-suite timing excludes Go process initialization and JSON/report IO. External process wall is retained, but includes the controller/disk-guard polling and is not the primary application timing. Disk guards monitor both the controller and owned subprocesses; timing may reflect that bounded monitoring overhead.
- RSS raw fields are process lifetime high-water observations only, not retained-child RSS, and no memory-improvement conclusion is made.
- No product, guest, setting, public API, main merge, CI or release change is made by this measurement.

## Source identities, order and reproduction

- Baseline source_commit: `47121e1be0b399ba4e2270ce3e25c411ade0e2eb`; v0.6.2 annotated tag_object_sha: `cebdb4114187171bd418b0a1b419e1c27368808d`.
- Candidate source_commit: `66f2fe9d4bbde9b20323e9ee9b1562f3af16b8a4`, includes UCA main61973daa and notification main2434a536.
- Measured harness source_commit: `bc5763308fd2914ec5a34233f1e0b178b0d4dead`. Binary Go VCS stamps identify this harness; replaced library source identities, guest hashes and binary hashes are separate fields in inputs.json. Commit/tag identity and clean checkout were checked before build.
- The existing full-lifecycle harness comes from00cbd779; changes are Pipe route, explicit resolved-cap readback and diagnostic child binding. Original library sources are pristine for both primary binaries; diagnostic overlays are separate.
- Five rounds rotate Fresh/Fork × P1/P4 cells and alternate baseline/current within adjacent version pairs. Five is odd, so first-arm counts are3/2 within a cell; all five values and pair effects remain in summary.json.
- A pre-measurement build-controller path collision was corrected atbc576330; the failed attempt produced no timing observations. Final binaries all bind the corrected clean source.

Run `python3 analyze.py --check` beside the saved files for read-only summary/CSV replay; it reads compact observations.json without temp/build dependencies or writes. Run test_analysis.py and test_undo.py for the retained negative binding controls. Publication changes only the reducer data loader, not validation/calculation functions; publication.json records original/published hashes.

For new timings, recreate a disposable workspace and check out measured harnessbc576330. Execute benchmarks/post062lifecycle/build.py, then run.py using the pinned plan and toolchain. The build script verifies source/tag objects and archives the exact baseline. Compilation/downloads and warmups remain separate; new timings are a new cohort. Do not run the build from a later report-only commit: its source guard expects the measured harness.

All58 full numeric process records are in observations.json. Original process JSON/console streams and96 diagnostic event streams are retained as checksum-verified compressed local evidence under `build/experiment-work/post062-lifecycle/evidence/published/`; archive hashes and member hashes are recorded. These archives are not proposed for main. The report and compact verifiable source/data set are preserved on the experiment branch.

The canonical release pin is also recorded in `release/baselines/v0.6.2.json`; its tag/commit resolution was verified against the same identity fields frozen in the measured plan. Diagnostic archive replay is available with `python3 diagnose.py --check` beside the retained local archive.
