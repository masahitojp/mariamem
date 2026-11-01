# Issue 56: 16 MiB protection-growth prototype

**The prototype reduced protection calls, but this bounded comparison did not
show a speed or CPU improvement. Recommend rejecting integration on the present
evidence.** The cost of a wider hardware-writable boundary and more failure-path
logic is not justified by an observed benefit. The strongest counterargument is
that five pairs on one host are noisy: this is not proof that batching can never
help. It is sufficient to stop this small prototype without widening its scope
or rerunning until a favorable result appears.

The Human requested [Issue 56](https://github.com/masahitojp/mariamem/issues/56)
first, then the prototype. This report completes that bounded work; integration,
Linux qualification, parallel acceptance and release were not undertaken.

## Question and implementation

The [preceding observation](https://github.com/masahitojp/mariamem/blob/463712dc2e262d154500cf729b3e20773b133fb8/benchmarks/fork-growth.md)
found 101 post-initial growths per child, 53 of them only 64 KiB. Arithmetic
rounding suggested 11–12 protections at 16 MiB granularity. The question here was
whether this actually reduces CPU or Fork latency without changing logical sizes.

The experimental host separates acknowledged logical bytes (`enabled`) from OS
RW extent (`rw`). Initial activation stays exact. Later extensions round RW up
to 16 MiB, capped at the existing maximum. Successful logical growth still
publishes exactly the requested size through the unchanged MemoryGrow path.
Guest source, converter, public API and logical memory.size are unchanged.

On protection failure the prototype restores the entire newly attempted interval
to PROT_NONE, then retries with the exact required extent. If restoration fails,
it rejects further growth and retains ownership for Close. The RW counter then
conservatively accounts the whole possibly enabled interval, rather than claiming
a precise permission state. Failed Close retains the owner for retry. Existing
valid data is outside the rollback interval.

Ahead-RW weakens the existing hardware boundary, even while software bounds stay
logical. Tests below verify the named paths; they are not a complete audit of all
unchecked accesses. This difference is explicit and remains a reason to reject
integration without a useful performance benefit.

## Measurement and results

Apple M1 / 16 GiB / macOS 27.2, Go 1.27.3, CGO disabled, GOMAXPROCS=8.
Five fresh-process pairs, alternating exact/batch order. Each process prepares
1,000 integer rows once, captures a Snapshot, then sequentially creates and holds
four children. TCP COUNT/SUM checks prove a pristine baseline in each child;
independent mutations remain present in each child's final check. All 40 measured
children passed, with zero remaining mappings/reservations/RW counters after Close.

Fork-only wall and process CPU exclude SQL verification, RSS sampling, root setup,
compilation and downloads. RSS is sampled externally with ps at baseline, after
each child's verified mutation, and after Close. Per-process timing is the median
of its four children, then the table gives the median across five processes.
This is a sequential Fork measurement with four retained DBs, not parallel Fork.
The controller's disk-budget checks and ordinary host scheduling were present in
both routes; this is not an isolated-machine latency measurement.

| Metric | Exact baseline | 16 MiB prototype |
|---|---:|---:|
| Protection calls per Fork, including initial activation | 102 | 12–13 |
| Fork wall, median of process medians | 36.259 ms | 37.696 ms |
| Fork CPU, median of process medians | 48.465 ms | 48.989 ms |
| RSS increase while holding four children | 312.203 MiB | 312.516 MiB |
| Process RSS after children and Snapshot Close | 61.719 MiB | 61.766 MiB |

The original 101→11–12 model excluded the initial activation; the table includes
it. Logical grow calls remained 102. There were no protection fallbacks or growth
failures in the positive measurement runs. RW permission is not physical residency;
these RSS observations show no material memory reduction or large increase.

| Pair (execution order alternates) | Exact wall | Batch wall | Wall change | CPU change |
|---|---:|---:|---:|---:|
| 0 | 43.556 ms | 38.188 ms | -12.32% | -11.99% |
| 1 | 39.170 ms | 37.696 ms | -3.76% | -5.26% |
| 2 | 35.675 ms | 38.046 ms | +6.64% | +2.53% |
| 3 | 35.195 ms | 36.010 ms | +2.31% | +2.63% |
| 4 | 36.259 ms | 37.211 ms | +2.63% | +1.08% |

The median paired change is +2.31% wall and +1.08% CPU; three of five pairs are
slower. Early baseline trials were slower than later baseline trials, so the
first two favorable pairs alone would give a misleading impression. No outlier
was discarded. This evidence establishes neither stable speedup nor a statistically
established regression; five pairs are the predeclared stopping point.

The useful finding is that fewer syscalls alone did not remove the measured cost.
The same memory ranges still need permission changes and subsequent initialization;
per-page work, page faults and other initialization remain possible contributors.
Those are hypotheses, not measured explanations here. The previous cumulative
CPU profile share cannot be converted into an equivalent expected latency saving.
Another chunk size or broader matrix is not automatically justified by this result.

## Correctness and limits

Nine focused top-level tests and five subtests passed: logical/RW separation,
zero/data/pointer preservation, maximum bounds, exact fallback, both attempts
failing with successful rollback, partially applied protection and failed rollback,
Close failure/retry, actual mapped-module growth, worker growth/futex visibility,
initialization failure ownership and join-before-unmap. Scalar MemoryEA and atomic
bounds helpers reject addresses in the ahead-RW region. Failure injection uses
real protection on part of an interval followed by an injected error; it does not
claim an organically occurring OS partial failure was reproduced.

The prior recoverable-protect test injector was narrowed to fail RW attempts while
allowing rollback to PROT_NONE. New tests separately cover rollback failure; the
old recovery expectation was not silently treated as a pass under a poisoned owner.
Two positive and two deliberately corrupt fixture pilots passed their expected
oracles before measurement. Five analysis tests cover incomplete pairs, order,
cleanup failure and SQL-oracle failure. Linux, race detection, simultaneous Fork,
large fixtures and a complete unchecked-access audit are **NOT RUN**. These are
limits of this experiment, not new release blockers or an implied acceptance plan.

## Evidence and reproduction

The baseline source_commit is `b3b3b46a8807482ad3f96725af86e031fe369b01` (v0.6.0),
tag_object_sha `b57183b08d48884840111e8b53daa500734337f0`. The clean measured
prototype/harness is `24e484accdadc2f9faedec294079ec272b40d272`.
Both binaries use this harness; the exact binary overlays only memory_mapping.go.
Removing its added counters reproduces the release file byte-for-byte. Both routes
are instrumented, not untouched public release binaries. Source, overlay and binary
hashes plus Go build identity are in [inputs](growthprototype/results/inputs.json).

[All compact observations](growthprototype/results/observations.json),
[summary](growthprototype/results/summary.json), [checks](growthprototype/results/checks.json),
[checksums](growthprototype/results/SHA256SUMS.json) and
[raw archive identity](growthprototype/results/archive.json) are retained. Raw logs,
pilots and setup failures remain on the pinned evidence ref. The initial sandbox
network failure and harness-signature compilation error were corrected before the
successful build/check/measurement source; neither is relabelled as a runtime pass.

```sh
python3 benchmarks/growthprototype/analyze.py --results benchmarks/growthprototype/results --check
PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/growthprototype/test_analysis.py
```

Recollection uses analyze.py --collect RAW --results OUT on the pinned raw tree;
verify raw SHA256SUMS.json first. This reproduces observations.json and summary.json
byte-for-byte without build scratch. To remeasure, create an owned workspace at the
measured source, copy benchmarks/growthprototype/run.py to evidence/run.py, and run
its build, test, pilot, measure phases in that order. It checks source identity,
clean status, toolchain, binary hashes, 8 GiB disk budget and 16 GiB free reserve.
The current report commit is not the measurement source. Build/temp are disposable;
any later main proposal must select a reviewed minimal change, not this history.
