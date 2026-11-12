# Issue156: dictionary-wait C candidate, fixed comparison

**The localized notification is a promising tail-reduction candidate.** The actual
C guest completes all30 fixed suites with ordinary SQL/lifecycle checks intact.
P8 improves in3/5 primary pairs; P4 improves in2/5. Separately timed PREPARE has
4/189 calls over100ms in baseline and0/189 in candidate. This is evidence for
reviewing the narrow correction, not proof that it removes all natural delays.

Recommend Human review before preparing a minimal product candidate and
both-platform acceptance. The strongest objection is that this is one Mac,
only five primary pairs per parallelism, and three secondary pairs: P4 does not
improve, PREPARE median rises, and P8 Fork median rises. Scheduling variation or
instrumentation can influence the result. Prior controlled cases establish the
mechanism, but the original pending/refusal/read-generation/recovery sequence is
still unobserved. No further sampling is implied by completing this fixed plan.
No adoption, main merge, Qualification, release or Issue closure is performed.

## Inputs and boundary

- [Precommitted plan](../pool-dict-c/PLAN.md), actual C candidate
  `7de45ac19718f37d1552824acfd6477dea6caf17`, execution source
  `8084518e2e3ed39a97aba6ed05d3b2dc705a99fd`.
- Both arms use product host `8df45792a927e440972266ee799d6f7223713e14`.
  Only the experimental guest changes: dictionary eviction's contended exclusive
  lock wait gains balanced tpool begin/end notification. No read-thread/timer/
  buffer-pool configuration change; purge shared-latch waits excluded.
- [CI43225605324](https://github.com/masahitojp/mariamem/actions/runs/43225605324)
  passed guest and translation jobs. Exact job/artifact identities and verified
  ZIP digests are in [bindings.json](bindings.json). This is Linux build and
  source-only translation, **not Ubuntu runtime acceptance**.
- Downloaded guest and locally reproduced translation match CI. Whole-body
  thread/CRC functions and the complete CRC table match canonical anchors.
  Existing adapters run unchanged except selecting this reviewed guest SHA in
  process-local modules. No canonical guard or input file is edited.
- Generated Fn17744 audit confirms failed try-lock→begin→original wait→end;
  successful try-lock bypasses notification. Additional exception edges reach
  termination; no exceptional-path equivalence or fault injection is claimed.
  Nested/LONG inputs and broader caller contracts remain prior limitations.
- Apple M1,16GiB, macOS27.2 arm64, Go1.26.10, GOMAXPROCS8/GOGC100.
  Shop70 Go Pipe,16MiB/read1, cap=P+1;50 shared-child reads and20 isolated writes,
  hence21 Forks/sample loads per suite. Every load has3 PREPARE,40 order INSERT,
 100 item INSERT,100 stock UPDATE,1 COMMIT. This is not48 independent children.
- Exact runner sources, binary digests, build metadata, host and completion are
  in [execution.json](execution.json). Four runner builds passed (183.0/4.0/
 178.6/4.0s); static-image layout also compiles its existing helper. No new C
  build or CI run was needed locally. Build time is excluded from runtime data.

## Primary comparison: SQL observer off

One warmup per arm/P, then five paired suites at each P, alternating arm order
and P order. Four warmups excluded as planned; all20 primary suites retained.
Wall starts before root boot and includes schema/seed, Snapshot, tests and final
cleanup. CPU covers the same workload; RSS is process maximum, not per-DB RSS.
Process wall including launch/exit is also retained in summary.json.

| Metric | P4 baseline | P4 candidate | P8 baseline | P8 candidate |
| --- | ---: | ---: | ---: | ---: |
| Whole-suite wall p50, ms | 546.252 | 552.429 | 506.617 | 469.045 |
| Whole-suite wall max, ms | 608.055 | 563.249 | 645.765 | 473.596 |
| CPU p50, ms | 2174.547 | 2222.384 | 2422.083 | 2400.604 |
| Process peak RSS p50, MiB | 491.08 | 431.05 | 712.52 | 710.11 |
| Fork p50 / p95, ms | 21.769 / 27.608 | 20.968 / 27.687 | 26.611 / 45.946 | 30.468 / 48.920 |
| Sample-load p50 / p95, ms | 46.230 / 61.403 | 47.557 / 59.236 | 70.757 / 103.562 | 71.706 / 99.457 |
| Sample-load max, ms | 73.872 | 61.696 | 441.312 | 102.696 |
| Sample-load >100ms /105 | 0 | 0 | 8 | 4 |
| Cleanup p50 / p95, ms | 3.178 / 4.728 | 3.010 / 4.446 | 3.538 / 8.409 | 3.623 / 8.021 |

Stage distributions pool105 observations/arm/P; cleanup includes20 writer closes
and final shared-child/Snapshot cleanup, not21 equivalent per-child Close calls.
p50 is median, p95 nearest rank. For five suites p95 equals maximum and does not
provide a reliable population-tail estimate. Parallel stage durations are not
additive components of suite wall.

| Paired changes (candidate / baseline −1) | P4 | P8 |
| --- | ---: | ---: |
| Wall, all five pairs % | −11.19, −8.93, +3.99, +1.13, +4.56 | −7.42, +7.97, −28.14, −26.66, +5.36 |
| Median wall change / faster pairs | +1.13% /2 of5 | −7.42% /3 of5 |
| Median CPU change | +0.23% | −0.89% |
| Median peak RSS change | −0.21% | −0.83% |

Arm RSS medians can suggest a larger difference than paired deltas; do not claim
memory reduction from this campaign. P8 Fork p50 increases3.86ms while suite wall
median decreases37.57ms: the useful signal is shorter sample-load tails, not a
faster common Fork path. Observer-off measurements cannot attribute those tails
to PREPARE specifically.

## Secondary: lightweight SQL phase timing at P8

Three additional pairs,21 loads×3 PREPARE×3 suites =189 calls/arm. Same SQL,
statement timing enabled, stack capture disabled. Do not merge these six suites
with primary timing or treat189 dependent calls as189 independent trials.

| PREPARE per-call metric | Baseline | Candidate |
| --- | ---: | ---: |
| p50, ms | 0.856 | 1.233 |
| p95, ms | 6.476 | 6.583 |
| max, ms | 397.921 | 26.942 |
| >100ms count | 4/189 | 0/189 |
| Counts by suite | 2,1,1 | 0,0,0 |

Long baseline PREPARE occurs in all three secondary suites; the candidate has
none in this finite sample. Typical PREPARE is not faster. Zero observed tails
is not a guaranteed absence of future tails. The secondary candidate's second
suite takes600.5ms and has9 sample loads over100ms despite no PREPARE over100ms;
other work/scheduling can still delay a complete sample load.

## Correctness, limitations and completion

All30 suites returned0 with existing row/count/query/isolation assertions,
50/20 executed tests,21 Fork/sample loads, active mappings0 and empty owned
scratch. Phase counts match in all126 secondary loads. No retries, failed
runtime samples or tail exclusions. No native parity, installed distribution,
race, Ubuntu runtime, exception injection or natural owner/queue sequence was
added. Prior controlled experiments retain their original source/meaning.

The analyzer initially encountered Go's null representation of an empty long-
operation list; normalization to an empty list fixed analysis only. Measurements
were neither changed nor repeated. The earlier archive tooling used Python3.9
without tar filter support; rerunning extraction with3.14 preceded all execution.
The measured source/runtime remain8084518e and the pinned guest; later changes
are compact evidence, analysis, reproduction and reporting only.

[compact.json](compact.json) retains all30 suite metrics, every Fork/sample/
cleanup duration and lane, all secondary PREPARE durations, operation counts and
selected long operations. Its original-observation SHA identifies the discarded
raw record; unclaimed per-call INSERT/UPDATE durations are deliberately omitted.
[summary.json](summary.json) is regenerated solely from compact.json. No CI REST
payload, generated source dump, full logs or local build paths are published.

Verification: read-only replay, four corrupted-evidence controls, Python syntax,
publication boundary and diff checks PASS. Unchanged product runtime is not
requalified by these tooling checks.

Read-only replay (also rejects missing-suite, cleanup-debt, mapping-debt and
wrong-Fork-count mutations):

```sh
python3 benchmarks/pool-dict-measure/analyze.py \
  --compact benchmarks/pool-dict-measure/compact.json \
  --summary benchmarks/pool-dict-measure/summary.json --check
```

## Reproduction

Use a fresh disposable workspace with worktree at8084518e, sibling temp/ and
evidence/. Budget8GiB/free6GiB; Python3.14 and Go1.26.10. First inspect source
commits with scripts/git_identity.py. Add a clean detached worktree at
7de45ac1 as temp/origin. Download the three ZIP artifacts in bindings.json via
`gh api repos/masahitojp/mariamem/actions/artifacts/ID/zip`, writing raw stdout
to a file. Verify SHA256 before ZIP extraction into temp/guest, temp/translation,
and temp/build. Reject unsafe member paths. The translated tar need not be
expanded: build.py independently reproduces and checks the full inventory.
Expired remote artifacts require an explicitly authorized new source build;
never substitute a different guest or relabel the old receipt.

Run build.py then run.py under scripts/experiment_disk.py with the budgets above
and respective2400s/1800s timeouts. Keep the execution worktree clean. These
scripts pin and verify source identity, reuse original binding validators,
build four runners, and run exactly the fixed30 suites. Do not run an unrelated
compiler/benchmark concurrently. On completion, use analyze.py from this report
with --raw evidence/observations.json and output --compact/--summary paths in
evidence/. A performance reproduction has new observations; only --check of the
published compact data should byte-match the published summary.

Keep compact results/source identities/checksums; remove owned guest downloads,
generated trees, binaries, module/build caches and worktrees after preserving
results. Scope ends at this fixed comparison; follow-up product work needs its
own Human decision.
