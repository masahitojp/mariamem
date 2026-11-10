# Millisecond-resolution probe prototype

The Human authorized this prototype on2026-11-11 to return to the original
startup-time question. It builds on the [working SQL timer correction](../../docs/reviews/wasi-timer-runtime/README.md).
This is an experiment, not adoption. The earlier roughly0.93–0.94ms per-child
median resolution-probe cost is an opportunity, not a promised saving.

## The one change

`guest/experimental.patch` retains the two SQL clock-selection guards and adds
one conditional branch in pinned MariaDB `mysys/my_rdtsc.c:my_timer_init`.
For **WASI + no compiled Performance Schema + MONOTONIC clock_gettime + no
runtime cycle counter**, replace only the millisecond-resolution busy probe with
`milliseconds.resolution=1`. This is the nominal integer millisecond unit used
by the clock adapter, **not measured hardware/scheduler resolution**.

`my_global.h:89–91` derives HAVE_PSI_INTERFACE from
WITH_PERFSCHEMA_STORAGE_ENGINE. The pinned portability profile disables that
engine. The exact initializer's later frequency-calibration paths require a
runtime cycle counter, so they cannot consume this nominal resolution on the
shortened path. The preceding full-source consumer audit found the resolution
metadata's external consumers in disabled PFS; SQL ANALYZE uses the separate
microsecond frequency/clock selected by the correctness fix.

Preserve discovery (including the current initial-zero-read unavailable policy),
all frequencies, overhead measurement, nano/microsecond resolution, real reads,
timeouts, InnoDB clocks, native behavior and other WASI profiles. If PFS or a
runtime cycle counter is enabled, or the clock route changes, retain upstream
probing. No Go shim change or global MY_TIMER_ROUTINE_CYCLES change is made.
There is no environment switch or public API.

## Local source-unit result

Source_commit `51dfa1ab8bc1604acd13d6ded837bfc71d4b99cd` passes all10 initializer
profiles /4 negative controls and the previous6 SQL selection profiles /2 negative
controls. The target reduces deterministic millisecond reads1001→21; all other
profiles match before/after. [Compact receipt](local-evidence/assessment.json)
and checksummed detailed observations preserve that source. Checkout-identity
regression and Python syntax checks also pass. These are controlled-clock source
units, not the new guest's runtime/performance acceptance. CI repeats the units
at its submitted source before the single guest build.

## Before a performance claim

1. Compile the **exact pinned initializer and its three helpers** with controlled
   clocks. Ten before/after profiles cover the target, PFS, cycles, native,
   unavailable/initial-zero, other clock, seconds and ftime. Require all metadata
   identical in these fixtures, reduce target millisecond reads1001→21 and leave
   other profiles identical. Four mutations must fail (cycle/PFS/native guards
   and frequency corruption). These counts prove removed work in the fixture,
   not real guest elapsed savings.
2. Repeat the previous exact SQL selection units; either missing half must fail.
3. CI builds exactly one UNQUALIFIED guest with source/patch/tool/guest identities.
   No stale guest hash or CRC/ownership binding is accepted. On artifact return,
   inspect and bind generated code before actual-host execution, and confirm the
   shortened branch is present in that actual generated initializer.
4. Require delayed ANALYZE meaningful/finite timing, subsequent SELECT, two-child
   isolation and confirmed cleanup. Compare **corrected-clock baseline** against
   **corrected-clock plus probe omission**, not the old zero-reporting guest.
5. Use the same Go version/host/SQL/settings/transport. Fresh/Fork: six alternating
   batches per arm, wall and CPU. Whole workload: Go Pipe shop70 atP4/P8, one
   warmup and five alternating pairs per cell. Keep all tails. Report per-child
   p50/p95 and batch/whole-suite time. Do not infer startup or suite gains from
   the controlled-clock tests. The detailed arms/budget are in `plan.json`.

Correctness failure stops performance/adoption. No measurable benefit is an
acceptable experiment result. Native SQL comparison and both-platform adoption
remain separate; do not turn the previous Mac correctness receipt into coverage
for this new guest. The historical benchmark/CI receipts keep their original SHAs.

## Reproduce / limits

From a clean committed source, Python3.14 locally (CI Python3.12) and C++17:

```sh
python3 benchmarks/timerselection/check.py --work /absolute/owned/selection --output /absolute/owned/selection.json
python3 benchmarks/timercalibration/check.py --work /absolute/owned/calibration --output /absolute/owned/calibration.json
```

Upstream files are hash-pinned at MariaDB commit
`83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`. Patches apply with fuzz0. The new
source check also proves all original C bytes survive outside the single added
branch. The actual unit fixture uses deterministic clocks, not the Mac clock
implementation or a complete MariaDB link. CI and local performance are distinct.

Local preparation budget60min/4GiB owned/8GiB free, zero local guest builds.
One guest CI build has a100-minute ceiling. Keep compact receipts and source;
remove extracted files/fixture binaries/worktree after push. CI handoff ends
this stage; runtime/performance work resumes from the completed artifact.
