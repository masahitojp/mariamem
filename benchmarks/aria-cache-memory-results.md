# Aria cache memory A/B results

Decision: **reject 128 → 16 MiB as a production candidate**. Ready-state paired
median savings on the canonical fixture are only approximately 2–5 MiB/DB.
After the large Aria workload, physical accounting savings are substantial
(≈81 MiB macOS / ≈108 MiB Ubuntu, paired medians), but Ubuntu wall and CPU
regress in all five pairs. This trade-off fails the combined acceptance
criteria. Correctness/lifecycle passed. Do not tune another setting.

## Evidence and measurement validity

[Successful run 36370036508](https://github.com/masahitojp/mariamem/actions/runs/36370036508)
measured source `0ff27c1ccb3aff625661683339ab0311490195a0` on
`experiment/aria-cache-memory`. See the [protocol](aria-cache-memory-experiment.md)
for boundaries and fail-closed correctness checks. Twenty balanced measured
rounds plus two warmups per condition/count; 1,000-row canonical fixture;
Go 1.26.8; embedded MariaDB 13.1.0. Native manifest/provenance embedded in each
JSON match the independently uploaded metadata. CI verified exact WASM/AOT
inputs and bytes before measurement. Both conditions use the same platform AOT.

Ubuntu: 24.04, x86_64, kernel 6.17.0-1022-azure, glibc 2.39, 4 reported CPUs.
macOS: 15.7.9, arm64, 3 reported CPUs. These are different hosted machines;
absolute latency, memory accounting and CPU must not be compared as equivalent.

**CPU caveat:** this run’s macOS helper incorrectly divided Mach CPU ticks by
1e9 without applying the machine timebase. Its macOS CPU values and amplification
are not a valid quantitative baseline. A local check against `getrusage`
confirmed the unit issue; the corrected helper applies and records
`mach_timebase_info`, with a regression test against process CPU time.
A corrected rerun is pending. Do not retroactively apply an assumed runner
timebase to these historical numbers. Ubuntu CPU is unaffected. Memory and
latency do not use that clock and remain valid.

## Fork latency

Pooled per-DB first SQL / barrier-to-group-ready distributions, ms p50 / p95.
Percentiles describe different distributions; do not add or subtract medians
as if they were a single paired sample.

| Platform | DBs | 128 MiB first SQL | 16 MiB first SQL | 128 group ready | 16 group ready |
|---|---:|---:|---:|---:|---:|
| linux | 1 | 548.4 / 566.5 | 548.3 / 563.0 | 548.4 / 566.5 | 548.3 / 563.0 |
| linux | 4 | 730.3 / 824.9 | 722.9 / 834.6 | 795.8 / 849.2 | 802.7 / 867.0 |
| linux | 8 | 1292.5 / 1471.0 | 1300.4 / 1447.7 | 1410.0 / 1537.7 | 1434.7 / 1491.1 |
| darwin | 1 | 576.1 / 642.7 | 520.1 / 584.5 | 576.2 / 642.8 | 520.1 / 584.6 |
| darwin | 4 | 897.4 / 1236.7 | 937.0 / 1156.0 | 930.7 / 1242.7 | 984.5 / 1215.5 |
| darwin | 8 | 1617.1 / 2312.1 | 1590.8 / 2240.4 | 1739.0 / 2327.9 | 1726.5 / 2317.2 |

Measured paired group-ready median improvement (control minus experiment):
macOS +29.1 / −5.9 / +46.7 ms and Ubuntu −3.2 / −13.9 / −11.7 ms at ×1/4/8.
Latency effects are mixed; this single run does not establish a portable benefit.
No additional tail repetition is needed to reject the failed memory criterion.

## Incremental real-memory accounting

Primary metric: Linux PSS sum; macOS physical-footprint sum. MiB p50 below.
G(0) includes the Go host with no runtime children; G(n) includes host and all
n runtimes. Incremental/n is computed within each sample. Paired saving is the
median of per-round control-minus-experiment incremental/n differences.
G(0) and G(n) columns are separate medians, not an identity to recompute savings.

| Platform | DBs | G(0) control | G(n) control | Incremental/DB control | Incremental/DB 16 | Paired saving/DB |
|---|---:|---:|---:|---:|---:|---:|
| linux | 1 | 19.10 | 420.58 | 401.68 | 400.83 | 4.05 |
| linux | 4 | 18.88 | 1389.78 | 342.76 | 339.43 | 4.88 |
| linux | 8 | 19.34 | 2673.49 | 331.70 | 326.62 | 4.81 |
| darwin | 1 | 9.81 | 250.59 | 240.86 | 239.02 | 2.45 |
| darwin | 4 | 10.31 | 988.32 | 244.53 | 241.31 | 2.96 |
| darwin | 8 | 13.35 | 2031.70 | 252.31 | 248.53 | 4.15 |

Derived control marginal growth per additional DB, matched sequential rounds:
Ubuntu 1→4 ≈321.9 MiB, 4→8 ≈321.3 MiB; macOS ≈245.4 and ≈258.9 MiB.
These are process accounting measures, not globally unique physical-memory totals.
Linux private bytes support the same small reduction: median ready-group private
128→16 is 420.3→419.1 MiB at ×1, 1311.1→1297.9 at ×4,
2594.2→2553.9 at ×8. macOS private bytes are unavailable.

Raw RSS remains secondary: median ready-group control RSS is Ubuntu
424.8 / 1634.3 / 3230.7 MiB and macOS 357.9 / 1387.0 / 2455.3 MiB.
PSS/footprint differ materially from RSS, validating the decision to avoid RSS
alone as the FAST memory KPI. Inference: the large cache mapping/default size
does not translate into an equally large ready-state physical charge in this
workload. The exact remaining ready-state allocation ownership is still unknown.

After the >16 MiB Aria/temp-table workload, paired after-workload group savings
are approximately 80.9 MiB on macOS and 107.7 MiB on Ubuntu. Separate-distribution
median group primary bytes are 450.4→367.9 MiB macOS and 661.2→561.8 MiB Ubuntu.
These groups include the host and one runtime; no separate G(0) was captured for
this auxiliary workload, so these are paired group savings, not the canonical
G(n)−G(0) KPI. Actual `.MAD` length was 65,544,192 bytes (≈62.5 MiB).
Inference: cache-related physical pages are material after this heavier work,
while the normal ready-state fixture does not pay the full configured cache size.

Sampled group peaks have the same reported median as the all-ready measurement
in this run. macOS retained 103 startup sampling gaps; Ubuntu retained none.
Incomplete samples never enter peak calculations; brief peaks can still be missed.
All mandatory G(0), ready and after-close samples succeeded. Runtime inventories
were empty after every Close. Paired create/destroy cycles showed small
after-close increments (p95 <0.8 MiB per cycle on both platforms); this establishes
bounded-run cleanup, not a proof of long-term absence of memory retention.

## CPU control baseline and cache-overflow workload

Ubuntu combined process CPU per DB, seconds p50 / p95:
128 MiB control ×1 0.530/0.560, ×4 0.567/0.580, ×8 0.565/0.583.
16 MiB ×1 0.535/0.551, ×4 0.563/0.585, ×8 0.570/0.584.
Control ×1 median host delta is 0.19 s and runtime lifetime CPU 0.34 s.
×8 amplification (same interval, matched rounds) is control 1.073/1.109 and
16 MiB 1.057/1.123. Kernel ticks limit CPU precision. The provisional <0.5
CPU-sec target is not yet met by this control; do not convert it into a hard gate.
CPU includes Go sampler/startup bookkeeping and excludes counter-helper/ps CPU
and shutdown. macOS CPU baseline awaits corrected measurement.

Both conditions passed five fresh large-Aria forks: actual `.MAD` >16 MiB;
24,000 unique 2,048-character rows; count/length/CRC validation; disk-backed
internal temporary-table counter increase; fork-local writes isolated.
Go race/lifecycle and Python multi-client/interruption checks passed in both
conditions/platforms. Aria and other plugins remained enabled.

Over-cache correctness workload wall time, seconds p50/p95:
Ubuntu 128M 1.192/1.198 →16M 1.318/1.337; combined CPU
1.200/1.200 →1.320/1.344. Derived separate-distribution p50 change is
about +10.6% wall/+10.0% CPU. All five Ubuntu pairs regress: wall +111–145 ms,
paired median +131 ms; CPU +0.12–0.15 s, paired median +0.12 s. This is
reproducible within this bounded run, not a broad workload guarantee. macOS wall 1.779/1.809 →1.824/2.290; CPU invalid as above.
This test aggregates scans, checksum, grouping/temp-table work and a mutation;
it does not attribute the increase to a particular cache miss/file operation.

## FAST strategy implications

Fact: reducing this cache misses the ≈64 MiB ready-state saving on the canonical
fixture; heavy Aria usage does show >64 MiB paired group savings. It incurs
consistent CPU/wall regression in that Ubuntu workload.
Decision: reject this setting change under the combined criteria; keep
production Aria unchanged.
The control establishes Ubuntu incremental PSS around 402 MiB at ×1,
332 MiB/DB at ×8 and marginal growth around 321 MiB/additional DB. macOS
footprint is around 241 MiB at ×1 and 252 MiB/DB at ×8; its accounting differs.
The provisional 256 MiB/DB and 2 GiB ×8 budgets must be evaluated by platform
and scope rather than raw RSS. No numeric target is changed here.
Both control first-SQL p50 values remain above the v0.2 ≤500 ms KPI in this run.
A future strategy review must address remaining latency/resource costs with
maintenance cost in mind. This result authorizes no new cache tuning or
restore/VFS/runtime architecture implementation.

## Artifact identities

- linux `init-aria-cache.json` SHA256: `7eee73b7ade001747a672b840df873c9dc509586ffa7e5086c894aea1e510464`
- darwin `init-aria-cache.json` SHA256: `35340a9472a08e49ca8b54cbcff7cce641f1e6b912f48bbfa11e4347d6052e53`
