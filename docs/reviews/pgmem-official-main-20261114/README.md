# Official-method prepared-output post-integration comparison

**Prepared INSERT shows no improvement in this cohort.** The per-pair median
candidate/baseline ratio is1.004 (autocommit),1.018 (one transaction). Text INSERT
is0.935 with a wide0.816–1.064 paired range, so its apparent improvement cannot be
attributed confidently to raw prepared-row reuse. DML without result columns
bypasses the changed row-copy/validation path; engine/input remain unchanged.
The observed INSERT result is consistent with that limited mechanism, not proof
of CPU attribution. No performance threshold, runtime fix or adoption reversal
is inferred from these measurements.

Library sources: old main eb175ae23292c1c40cfbeb4b9b73132873c4cc6f and integrated
main eeef899a296be8aa38cc9e3de0a550c428d4dca9. Harness source
d3ed44a766e7a3464bc25a54b173f78795567d8d; the same main.go was used for both.
Go1.26.10/CGO0, MySQL driver1.9.3, Apple M1, one machine,5 alternating fresh-process
pairs, existing default16MiB buffer pool. No guest rebuild, CI or product change.

| Metric | Old median | Main median | Median of paired time ratios |
| --- | ---: | ---: | ---: |
| Start→TCP SELECT1 |46.618ms|48.791ms|1.028|
| Schema + seed |153.280ms|153.764ms|0.972|
| Indexed SELECT, TCP |141.246us|141.265us|0.991|
| Indexed SELECT, Pipe |99.318us|98.961us|1.006|
|200k MD5 + real filesort + COUNT |1556.848ms|1548.772ms|1.015|
| Snapshot |3.173ms|3.255ms|1.047|
| Fork→first JOIN query |33.125ms|33.285ms|0.989|
| Fork/query/drain/Close isolation |43.485ms|45.158ms|1.036|
| Text INSERT/autocommit, per row |154.348us|142.748us|0.935|
| Prepared INSERT/autocommit, per row |122.699us|124.425us|1.004|
| Prepared INSERT/one transaction, per row |104.935us|108.337us|1.018|

Displayed cohort medians and median paired ratios are different statistics: ratios
are formed within each old/new pair before taking their median. Do not divide the
displayed medians and call that the paired effect. All samples, plans, source/build
inputs and exact ratios/ranges are in JSON. Startup/Snapshot have particularly
large ranges (startup paired0.285–3.498); small point differences do not establish
improvement/regression. Slow observations are retained, not discarded.

[Method and adaptations](../../../benchmarks/pgmemofficial/README.md) explain the
SQL/driver changes, inserted control cases and validation. The primary upstream
method is pinned, but PostgreSQL, its different defaults, official Docker/VM memory
runs and the separate parallel modelcase were not run. The heavy plan contains
filesort on both sources and returns200000; all measured processes completed and
all included row/affected-count checks passed. Pilots are retained and excluded.
No recognized heavy build/benchmark was present before measured runs or afterward;
this is not proof of exclusive machine use. ps RSS is reference only, not peak or
phys_footprint. No conclusion covers Linux, pgmem-vs-mariamem speed, large writes,
total MariaDB upgrade-hours or future engine versions.

The bounded cohort is complete. Results/source are preserved in the experiment
branch; disposable sources/binaries/compiler cache are removed after collection.
