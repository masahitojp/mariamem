# Additional three UPDATE-wait observations

**Result: NOT_REPRODUCED.** Exactly the three additional natural processes requested by the Human completed, separately source-bound from the earlier three. No UPDATE>100ms or natural snapshot occurred. The original366ms UPDATE still cannot be classified as execution/commit/flush. No more repetitions or setting changes were added.

| Process | Children | UPDATE p50 ms | UPDATE max ms | UPDATE>100ms | Captures |
|---|---:|---:|---:|---:|---:|
| extra-0 |48|0.450|12.269|0|0|
| extra-1 |48|0.422|8.761|0|0|
| extra-2 |48|0.495|24.210|0|0|

COUNT and check SELECT also have no>100ms cases; all144 children pass SQL/pristine seed/independent update/verification/cleanup. The three processes run sequentially, P8/48children, load-off/current25other arguments, Pipe,1,000rows, GOMAXPROCS8/GOGC100. There were no additional DB preflights, artificial pilots or warmups in this newly authorized round.

The observer now records an ExecContext entry timestamp immediately before the actual call. Its strict predicate requires the entire profile interval to lie between that marker and return. Unit controls reject a pre-Exec artificial-hold interval, missing entry, or capture extending past return. Label/parser and argv selector units also pass. Because no natural profile occurred, this round does not claim a real-engine phase-classification branch was exercised.

Original100ms timer, child labels and maxone2MiB profile/process remain. Observer scheduling can affect reproduction; zero occurrences are not a performance result, frequency estimate, resolution proof or grounds to discard the old symptom. The previous three and these three have different observer hashes and are not pooled into a single performance cohort.

Measured harness source_commit `1e6d34520e10b259b471ad65bceae18d0d669087`; parentf00c506da34c247045a2a51bbd8879ae68168cfa; product1862f4a89397bddfa1820d835106d3437a438cf7; origin guest6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe. Commit identity and clean source verified before build. Same UNQUALIFIED translated-Go load-OFF argument prototype; no canonical guest build/default/API changes. Go1.27.3/CGO0/macOS arm64, one host. Exact binary/overlay hashes in inputs.json.

Conclusion: the additional bounded request is complete; execution-versus-autocommit/commit/flush and linkage to the older COUNT queue remain unknown. Preserve the residual without repeatedly opening more capture attempts. Previous OFF throughput improvement and failed P8 Fork guard remain under their original evidence; this non-reproduction does not supersede either.

receipts.zip contains all three reports, fixed plan/input/overlay hashes, collector/build/reducer and unit logs. Extract to an empty directory and run `python3 analyze.py --check` for read-only exact3-process/window/summary/CSV replay with missing-process rejection, no temp/build tree needed. Canonical source/guest/CI acceptance, both-platform performance, product adoption, main integration, Qualification and release are outside this round.
