# Official modelcase adaptation after async Close integration (2026-11-16)

Conclusion: P8 independent suite medians Maria sync431.456ms / async447.954ms /
PG369.333ms. Sync is+16.82% and async+21.29% versus PG (ratios of independent
medians). Corresponding round-paired suite ratios are+16.85%/+17.93% (see
summary for exact values). Process wall medians461.412/479.170/470.339ms.
The different timers/statistics must not be interchanged.

This70testsuite does not establish a consistent async speedup: round-paired
async/sync medians P1−0.58%(3/5faster),P4+2.86%(2/5),P8−0.67%(3/5). P8range
−4.51..+12.28%. Independent P8async median is3.82% slower than sync although
paired median is−0.67%, because sample ranks and execution variation differ.
No A/A or inferential significance test in this cohort. Keep both statistics;
do not discard slower observations or add gains from the480child workload.

## Fixed source and workload

Maria product source_commit6558ee8fb2211313a8aa0ea6070ac5256767811a (PR217 merge).
Harness source identity7d8e6938 (full in inputs.json). PG official main
3433a40bd4167daea2d8e364666bd5fcf18ef654, clean and unmodified.
Both built Go1.27.4, CGO0/GOMAXPROCS8/GOGC100, macOS27.2.1 arm64. This matches
our prior comparison compiler, not release qualification's Go1.26.10. Same
Maria binary for sync/async, hashes/buildinfo retained. No concurrent benchmark.

Official site https://shibukawa.github.io/pgmem/benchmarks/ describes70tests:
50read/20write,20categories/500products/1000users,40sampleorders. Official
current read/write test sources are byte-identical to the preserved PG adapter.
PG store.go differs only in the revenue selector/import. Website published
numbers are another machine/date/cohort and are not comparison measurements.

Adaptations: both close the original parent after Snapshot and Fork a shared
reader DB plus20writerDBs. MaxForks16explicit on both (one shared reader leaves
spare capacity at P1/P4/P8). Maria uses default interpolation/in-process transport,
PG uses pgx/nativewire. SUM recalculation and audit triggers remain. Maria uses
AFTER UPDATE OF status plus unchanged-value guard. Both REVENUE_PREAGG=1 SQL
preaggregate bycategory thenLEFTJOIN allcategories; original SQL remains in
store.go. Both TestMatchedSemantics PASS: original/rewrite same results,
non-status or status=status no audit, changed status exactlyone auditrow.
This is a matched adaptation of the official workload, not byte-identical SQL.

Maria writer cleanup closes SQL pool and waits WaitDisconnected in BOTHmodes.
Sync thenClose; async calls publicCloseAsync, retains allhandles and finally
Wait/Disposed before snapshot/readersClose and trace end. A cleanup_drain span
is recorded. No error ignored. PG uses the matched fixture's nativeClose path.
The archived Maria fixture referenced an omitted diagnostic loadUnlessProbe;
we replaced both references with ordinary store.LoadSample before timing.
Original build failure is retained separately, not counted as a suite run.

## Results

One warmup plus5measured suites/arm/P, P1/P4/P8,3armorder cyclically rotated.
All54processes PASS:3,780testbodies,1,080writerForks,1,134sampleloads including
warmups. No exclusions/adaptive repetitions. Full traces/logs, timing nodes,
processCPU/maxRSS and UTC retained. Internal suite elapsed includes explicit
cleanup/drain. Process wall includes startup/exit and has a different boundary.

|P|Maria sync suite|Maria async suite|PG suite|sync process wall|async process wall|PG process wall|
|---|---:|---:|---:|---:|---:|---:|
|1|1205.159|1205.361|779.690|1250.423|1247.982|836.792|
|4|508.485|507.449|410.803|553.834|560.540|507.115|
|8|431.456|447.954|369.333|461.412|479.170|470.339|

P8CPU medians sync2238ms/async2267ms/PG1442ms; process maxRSS medians
667/675/1121MB(decimal). RSS is observed process peak, not unique physical
memory/ceiling; CPU is process-tree usage from the external runner.

|P8 phase p50 ms|Maria sync|Maria async|PG|
|---|---:|---:|---:|
|boot|42.702|43.163|53.181|
|import|28.272|27.882|68.060|
|snapshot|5.243|5.078|16.451|
|reader_fork|15.649|14.982|9.760|
|fork|23.827|27.470|27.212|
|sample|74.142|69.788|40.020|
|test|1.656|1.608|0.688|
|cleanup_drain|0.000|0.844|0.000|

Phase statistic: perprocess p50, then median of5measured processes. Overlapping
phase sums cannot be added into elapsed time. Remaining differences concentrate
in sampleload and testbody; initialization/import are shorter on Maria. These
observations do not isolate engine/driver/OS-lock causal contributions. The
async drain is included, about0.844ms median atP8; zero syncdrain means no pending
async handles rather than zero totalcleanup cost.

Recommendation: keep async as an optional capacity-dependent API; do not advertise
this suite as a demonstrated async speedup. Compare new optimization hypotheses
against sampleload and querycost only after approval. No new optimization task
is started here. Prior69second observation did not recur: maximum54suite elapsed
1,219.759ms,maximumprocess1,283.259ms. Different workload/finite observation,
not proof that the prior cause is resolved. No recurrence Issue opened.

## Reproduce and retention

PLAN-async fixed before execution. Resolve committed module placeholders in temp
copies. Verify both pinned git identities before compilation. run-current.py
builds both store packages, semanticcontrols then54suites. The committed script
expects its isolated workspace layout, caches/temp inside the budgeted workspace.
Initial run script also preserved externally. Full raw data live on this evidence
branch; no bulk evidence merge into main. summary.json/results.json/inputs.json,
allspans/logs and checksums preserve this cohort. Priorresults were replaced only
on this new experimentbranch; previous fixed evidence commits remain unchanged.
Main integration of GoAPI is completed independently; no release is requested.
Owned clonedsource/build/caches are deleted after remote/history verification
and preserving source/harness identities. No large artifacts are needed to read
or independently recompute this comparison.
