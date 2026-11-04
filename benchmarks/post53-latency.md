# Post-#53 lightweight Go latency check

**No large regression is visible in this bounded comparison.** Current main is
−6.2% to+1.2% versus v0.6.0 remeasured on the same host. Recommend no further
performance investigation for this adoption based on these samples. Three pairs
are a screening check, not a statistical equivalence claim or a general speedup.

## Inputs and comparison

- Baseline: v0.6.0 source_commit `b3b3b46a8807482ad3f96725af86e031fe369b01`,
  tag_object_sha `b57183b08d48884840111e8b53daa500734337f0`.
- Candidate: adopted main source_commit `6e29c1cd125aa95f564969b905cbff462d4f0e74`.
- Apple M1,8 logical CPUs,16 GiB,macOS27.2 arm64; Go1.26.10,
  CGO_ENABLED=0, `-p1 -trimpath -buildvcs=true` on both clean standalone clones.
  Source/tag identity and actual clean binary VCS stamps were checked before use.
- Same `benchmarks/ownedprepared/main.go` and resources.go bytes on both sources.
  App-connections workload,4 instances per suite; Light/serial10MiB/parallel4
  10MiB cases, Fresh and Fork. No explicit cap override: current auto has enough
  capacity for4 on this host; this is not saturated-cap wait performance.
- One warmup pair per cell, then3 alternating pairs;48 executions total,
  12 warmup excluded from medians,36 ordinary. Existing SQL/Close assertions
  remain. No failure in the completed48-execution campaign.

Milliseconds, median. Whole-suite `suite_product_seconds` includes preparation,
SQL use and cleanup; parallel phases use wall intervals, not summed overlapping
timers. Build/acquisition and diagnostic enumeration are excluded. Positive is
slower. “Old report” is the v0.6.0 side of the previous six-pair post-release
measurement at evidence commit `13e261d4b56fd109e602a49825823e86de67576b`.
It is historical context, not the direct comparison denominator.

| Case | Old report v0.6.0 | v0.6.0 now | main now | Paired median change | Slower pairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| light-fresh | 226.7 | 225.3 | 220.6 | -2.1% | 1/3 |
| light-fork | 255.5 | 252.8 | 255.9 | +1.2% | 1/3 |
| fixture-fresh | 2684.1 | 2766.4 | 2756.3 | -0.4% | 0/3 |
| fixture-fork | 1149.0 | 1186.3 | 1182.4 | -0.3% | 0/3 |
| parallel-fresh | 894.7 | 979.6 | 945.1 | -3.5% | 1/3 |
| parallel-fork | 806.6 | 918.6 | 861.7 | -6.2% | 1/3 |

Serial10MiB is near-flat, Light is within a few percent. Parallel4 main medians
are lower in this run, but ranges overlap and only3 pairs were taken. Historical
parallel Fork was806.6ms; today's v0.6.0 is918.6ms and main861.7ms. That illustrates
why old-versus-new dates alone cannot establish a code regression. No attribution
to #53, #63, TCP, allocation or queue behavior follows from these whole-suite data.

MariaDB version remains12.3.3; guest build identities differ between releases
and main (both hashes are in inputs.json). This compares complete source states,
not an isolated Fork-limiter A/B. No Python, RSS, peak memory, cold setup,
Ubuntu, broad performance qualification or performance threshold is claimed.

## Evidence and reproduction

[Compact evidence](post53-latency-evidence/README.md) retains every measured/warmup
phase record, summaries, source/binary/harness hashes and the recipe, with
checksums. The release pin is in `release/baselines/v0.6.0.json`. The historical
report source is preserved on its original evidence ref, not silently imported
or merged into main. This report is on a measurement branch; main adoption is
not requested by running this check.

Two pre-measurement orchestration failures are recorded in plan.json: a relative
interpreter path, then an extra wrapper-only FD equality assertion that rejected
initial5→6. The latter was removed as outside the original latency scope; FD
values remain in all completed records, and SQL/Close assertions were unchanged.
Failed-attempt scratch cleanup ended during final warmup, before ordinary pairs.
Normal OS/app activity remains; no claim of machine exclusivity is made.
