# Startup preload OFF: bounded adoption check

## Decision now
The requested finite workload and lifecycle check is complete. Recommend **proceeding to clean productization of OFF if the Human accepts the measured local latency tradeoff**, not directly merging this experiment. Modelcase P1 again improves and prior P8 repeats favor OFF; over-pool reads show no consistent whole-lifecycle regression. The strongest objection is real: small-fixture P1 first scan slows in5/5 pairs (paired median+7.08%, independent medians6.027→6.308ms), and P8 Fork slows in4/5 (+8.01% paired;33.903→38.081ms independent medians). These absolute costs appear modest relative to whole-suite gains, but a universal “all operations faster” claim is false. This is the predeclared return-to-Human condition, not an automatic rejection or permission to silently relax an old guard.

Main/product defaults unchanged. Formal product implementation, both-OS/runtime/consumer acceptance, main integration and release are not completed or approved by this report. No additional sampling or causal tracing started.

## Fixed identity and conditions
Measured source_commit **a7d284c1fd612278de4e50d0fee79933d2aca0b1**, base main **ac8849d806bdd8fd504c1e44c27a809e8beed658**. Main differs from prior6558ee8 only by project-status documentation. Same experimental per-instance my.cnf ON/OFF selector; no generated engine or guest changes. Guest SHA77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450. Code under benchmarks/preload-adoption is a standalone read probe in the benchmarks Go module. Binary hashes and git_identity output are saved. Go1.27.4, darwin arm64, CGO0, GOMAXPROCS8, GOGC100,16MiB pool/read1.

One initial build at73d9f9f7 ran modelcase semantics but invoked the read probe from the root Go module; build failed because benchmarks is a separate module. The corrected build only changes working directory/package target; first failure is retained, no invalid timing was collected. Disposable cache was recreated. All subsequent fixed runs completed without retries/exclusions.

Power recorded before/after every measured/warmup process: modelcase44/44 and read-probe96/96 observations AC. Lowpower0 before/after. Thermal status unavailable; no battery comparison or no-throttling claim. No internal trace and no recursive disk monitor during timing.

## Normal modelcase P1
Same70 cases (SUM/status audit/preaggregated revenue, synchronous Close, MaxForks16). Five alternating ABBA/BAAB blocks plus2warmups:22processes,1540 bodies PASS.

| Metric | ON median | OFF median | Paired OFF/ON median | OFF wins |
|---|---:|---:|---:|---:|
| Whole internal elapsed ms |1229.557|1210.023|-1.58%|4/5|
| External wall ms |1273.353|1258.285|-1.39%|4/5|
| Process CPU ms |1672.562|1448.761|-13.18%|5/5|

Mean whole1242.230/1214.110ms; all samples retained. P8 was not rerun: [prior independent P8 evidence](https://github.com/masahitojp/mariamem/blob/84b40d984b2a164b18127595a6f7e88d3a935dd6/benchmarks/buffer-load-control/repeat-20261117/README.md) remains a separate cohort, paired-3.35% (9/10) with two long ON samples. Do not pool P1/P8 or claim a universal CPU reduction.

## Read-focused control
4096/24576 rows with1024byte payload. Actual table allocation5,783,552/28,901,376bytes (~5.52/27.56MiB), the latter exceeds16MiB pool. P1/P8,8 children per process, two full COUNT/SUM/payload-length scans, one independent update, disconnect/Close, then a final pristine child and Snapshot Close. Five alternating pairs/cell plusone warmup/arm/cell:48processes,432 ordinary child lifecycles all validated, all zero remaining active memory mappings. Batch excludes root preparation and final pristine check; whole includes both. No per-child discarded warmup. Settings checks are present identically in both arms after scans, included in lifecycle. Parallelism does not make phase medians additive.

All percentages below are **median of five OFF/ON paired changes**, not ratios of the displayed independent medians.

| Fixture / P | Whole % | 8-child batch % | Fork p50 % | First scan p50 % | Second scan p50 % | Child lifecycle p50 % |
|---|---:|---:|---:|---:|---:|---:|
|5.52MiB /1|-1.15|-1.32|-2.45|+7.08|-3.33|-0.35|
|5.52MiB /8|-0.40|-2.95|+8.01|-13.61|+0.95|+1.47|
|27.56MiB /1|-1.29|-0.16|-1.36|-2.16|-0.51|-2.07|
|27.56MiB /8|+0.52|+0.40|-12.89|-3.84|-4.15|+1.01|

Independent batch medians ON→OFF:236.038→233.136,79.736→77.380,625.472→618.274,185.294→185.234ms in table order. Whole medians500.803→498.104,349.632→343.367,1943.275→1901.254,1475.729→1465.999ms. The near-equal large P8 batch has mixed pairs (2/5 OFF wins); it is not a stable improvement. Paired vs independent-median differences can even have different signs, so use the paired table for directional conclusions.

The small P1 first-scan increase occurs in5/5 pairs, but whole improves4/5 and batch3/5. Small P8 Fork is slower4/5; child lifecycle is slower4/5 even though whole/batch improve4/5. Thus the latency/throughput tradeoff from the older [preload study](https://github.com/masahitojp/mariamem/blob/6d18915a478b7d116fbf382e98a83a4e002843fe/benchmarks/bufferloadrepeat/results/README.md) is still material on this current runtime. Historical thresholds are retained as a warning, not relabelled PASS or silently waived.

No measured read probe first scan>200ms or Fork>100ms: maxima137.233/82.335ms. This excludes neither rare stalls nor other workload failures. Both warmups and all primary observations are retained. Five pairs/cell on one shared Mac are limited evidence; large positive/negative parallel phase swings remain visible in large-summary.json.

## Correctness and detection net
- Both modelcase matched semantics checks passed, including equivalent revenue SQL and audit trigger behavior. These are SQL oracles, not full distribution qualification.
- Independent acceptance processes ON/OFF run8 mutated children, validate a pristine sibling, mutate/reSnapshot/Fork again, check preserved row count and changed payload, expected load setting and16MiB/read1, then require zero active mappings. Both passed; see acceptance-ON/OFF.json and main.go. Correctness assertions also run in every read process.
- Fresh0/restoredON1/OFF0 is checked; old fresh creation override is not a failure. Public API remains unchanged.
- Performance regressions and the tradeoff are invisible to ordinary CI; this bounded analysis exposes them. No timing oracle was weakened to call a regression PASS.
- Current adapter reads ambient EXPERIMENT_BUFFER_LOAD and is explicitly not product form. Normal CI does not establish intended production defaults or protection against that experimental selector. A production change must remove it, use fixed internal configuration and add effective-value/root/Fork/resnapshot and configuration-failure checks.
- Existing generated runtime inventory checks own source/guest binding, but handwritten runtime adapter correctness is not established by a generated SHA. No canonical guest regeneration is claimed or needed for this prototype's unchanged engine.

## Review of acceptance and gaps
Object inferred from the authorized task: pinned measured SHA above against pinned current main. Review used the local review skill, source diff, raw JSON/logs and independent reduction; no CI success is claimed and no CI was submitted.

Satisfied: fixed source and arm parity; bounded P1 and size/P read controls; complete lifecycle times; no outlier removal; semantic/isolation/resnapshot/cleanup checks; power context; preserve earlier P8 cohorts.
Needs Human judgment: the predeclared local regression flag fires for small first scan and parallel Fork. Recommend accepting these measured absolute costs for test-suite throughput, then productizing; this remains a recommendation, not approval.
Unverified/not in this bounded experiment: Ubuntu, product toolchain Go1.26.10, Python consumer/distribution acceptance, config-write failure injection, rare-tail prevention and mixed-mode ambient selector concurrency. Productization should not expose mixed-mode ambient selection as a public API; #144 remains separate.
No public guide contract changes found; no generated-engine/guest ownership changes; no claim of completed CI/productization; no removed-behavior stale comments found in the touched adapter. Retained experimental comment marks the selector explicitly. Historical #68 close and deferred#143 are unchanged; no claim their causes were fixed.

## Next step if the tradeoff is accepted
Create the smallest clean host-side internal startup configuration change from current main, without ambient override, experimental harness or raw evidence. Guest rebuild is not required by the demonstrated configuration route. Add deterministic configuration/effective-value coverage, run the canonical runtime-boundary checks and submit the exact candidate for existing both-OS/consumer CI. Return the CI URL/SHA/operation and stop; do not supervise CI. Review merge separately from release. No new public resource-setting API, broad tuning sweep or extra long-wait trace campaign is implied.

## Reproduction / retention
Follow PLAN.md and saved build.py with workspace/worktree,temp,evidence siblings. Run measure-p1.py then measure-large.py, then analyze.py, with localhost bind permission and budget6GiB/free floor8GiB. Each measured binary is fixed within its campaign. Scripts use original local absolute paths only through their workspace root. JSON, full process logs, toolchain/source identity, power context and original failed build are hashed. Cache, binary, copied harness and completed worktree are disposable. Source refs/evidence are retained; no unrelated user edits are removed.
