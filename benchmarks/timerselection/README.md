# WASI SQL timer selection experiment

This candidate changes **two preprocessor conditions in MariaDB's SQL execution
tracker**, not Go's clock shim. On WASI, both `measure()` and
`timer_tracker_frequency()` select the existing microsecond fallback. Native
selection, global cycle-counter availability, timer calibration and InnoDB
timekeeping remain unchanged. No performance saving is claimed yet.

The [baseline observation](https://github.com/masahitojp/mariamem/blob/809036801dc8d3f6d4dae543e73eb57bfca42b23/benchmarks/shopforkstages/detail-results/README.md)
found three delayed ANALYZE queries taking24.7–25.5ms while reporting zero table
and other execution times. CPU-cycle metadata was zero. The compiler selected
the cycle builtin anyway and optimized its unavailable result to zero. Choosing
the existing fallback in the SQL tracker is the bounded correctness hypothesis.
The microsecond route uses gettimeofday, matching upstream's existing fallback;
this is not a new guarantee against wall-clock adjustments.

Do not change `MY_TIMER_ROUTINE_CYCLES` globally for this trial: that also selects
`my_pseudo_random` in `my_rdtsc.h`, broadening the change beyond SQL reporting.
Likewise, do not set a nonzero frequency on a clock that still returns zero.
Both tick source and conversion frequency must agree. The unchanged global
millisecond discovery/calibration behavior is a separate question.

## Stages and stopping conditions

1. Hash-check the two pinned upstream headers. Apply `guest/experimental.patch`
   with fuzz0 and require exactly the two SQL guards to change. Compile the exact
   extracted tracker methods with controlled clocks: original WASI must exhibit
   the problem, changed WASI must report20ms, both native clock profiles must
   preserve behavior. Reverting either half must fail. This is a selection unit,
   not an actual guest test.
2. Submit one Linux-arm64 development guest build. The new workflow is restricted
   to this experiment branch, with a100-minute ceiling and no publication rights.
   Record exact source/patch/toolchain/guest identities and mark it UNQUALIFIED.
3. After the artifact is available, inspect the new generated bindings before
   installing the host. `runtime_crc32c.py` is pinned to the old guest/table/body;
   do not bypass it or silently substitute a new hash. New compiler output may
   change function numbering because actual SQL timing is restored.
4. Rerun the baseline ANALYZE oracle on the actual guest: finite meaningful delayed
   timings, following SELECT, two-child isolation and confirmed cleanup. Only
   afterward compare calibration omission separately. Native SQL comparison and
   platform acceptance remain distinct from this source/guest-build stage.

The source-only pass or successful guest build is not a repaired-runtime claim.
Codex hands off after CI submission under AGENTS.md; no monitoring or automatic
adoption follows. No canonical source.patch, generated runtime, public API,
release provenance or product defaults are changed.

UCA attribution remains an independent next observation on the stable product:
identify the expensive IDs/branches inside five calls totaling about2.2ms. The
77 collation-hash growth calls totaled only about0.03ms and are deprioritized.
This timer guest does not alter UCA data or add unreviewed collation sharing.

## Reproduce

`plan.json` pins product and MariaDB commits and upstream file checksums. In a
clean experiment checkout, with a fresh disposable output path:

```sh
python3 benchmarks/timerselection/check.py --work /absolute/owned/unit --output /absolute/owned/selection.json
```

The local fixture needs C++17 and network access for two hash-pinned headers.
It reports compiler, source identities, six cases and two negative controls.
The CI workflow repeats it at the exact submitted head, then invokes the existing
`build_generated_guest.py --development-output` route exactly once. Runtime
testing is intentionally not wired to stale CRC bindings. `receipt.py` verifies
the development contract and different guest identity and explicitly records
runtime ANALYZE and host regeneration as NOT_RUN.

Local scope is preparation/source verification only (60min,4GiB owned/8GiB free).
The one CI build has its separate100-minute ceiling. Compact source/test receipts
and pushed commits survive cleanup; downloaded headers and native fixture binaries
are disposable. Main's unrelated active checkout is preserved.
