# Aria cache memory A/B results

Final decision: **reject 128 →16 MiB as a production candidate**.
Canonical ready-state paired savings are only ≈4–6 MiB/DB. The large Aria
workload saves ≈108 MiB macOS / ≈116 MiB Ubuntu after execution, but wall and
CPU regress in all five pairs on both platforms. This fails the combined
acceptance criteria. Correctness/lifecycle passed. Keep production Aria unchanged;
do not continue by tuning another setting.

## Verified evidence

[Final run 36371206896](https://github.com/masahitojp/mariamem/actions/runs/36371206896)
measured source `b2e84fe94fc60d13feaee39cfad9e10bebf1b975` on
`experiment/aria-cache-memory`. Twenty balanced measured rounds plus two warmups
per condition at ×1/4/8; 1,000-row canonical fixture. Go 1.26.8, embedded
MariaDB 13.1.0. See [protocol](aria-cache-memory-experiment.md) for timing scopes.
Downloaded JSONs are complete with all 120 measured groups per platform.
Embedded native manifest/provenance equal the independently uploaded records.
CI verified immutable WASM/AOT input hashes before measurement; both cache
conditions use the same platform AOT. Verified reuse retains the original
guest/AOT build commit `54b046bc3059b14d114192e10c5b1b21d38b8b24`; the
measurement SHA identifies the current Go harness/counter, not a relabelled
guest build. All ready process inventories are n+1
(host plus runtimes), and all baseline/after-close inventories contain only host.

Ubuntu 24.04 x86_64: kernel 6.17.0-1022-azure, glibc 2.39, 4 reported CPUs.
macOS 15.7.9 arm64: 3 reported CPUs. Do not compare absolute timings or memory
accounting as equivalent hardware/platforms. macOS records its CPU timebase
125/3 and converts Mach ticks to seconds. The native counter regression test
matches the standard process CPU clock. These CPU values are valid.

The earlier [run 36370036508](https://github.com/masahitojp/mariamem/actions/runs/36370036508)
at `0ff27c1` supported the same rejection, but its macOS CPU values omitted
Mach timebase conversion and must not be used as a CPU baseline. Its valid
memory/latency evidence is historical only. No retroactive conversion was applied.

## Fork latency

Milliseconds p50 / p95. First SQL pools per-DB samples; group ready is the
barrier-to-all-ready distribution. Their percentiles are distinct, not additive.

| Platform | DBs | 128M first SQL | 16M first SQL | 128M group ready | 16M group ready |
|---|---:|---:|---:|---:|---:|
| darwin | 1 | 358.9 / 394.8 | 343.4 / 368.4 | 358.9 / 394.8 | 343.4 / 368.4 |
| darwin | 4 | 718.9 / 1070.7 | 674.9 / 1024.3 | 757.5 / 1079.1 | 706.9 / 1069.3 |
| darwin | 8 | 1589.7 / 2786.8 | 1622.1 / 2986.0 | 1742.9 / 2858.5 | 1752.4 / 3036.4 |
| linux | 1 | 532.2 / 557.1 | 540.9 / 561.0 | 532.2 / 557.1 | 540.9 / 561.0 |
| linux | 4 | 720.1 / 831.8 | 735.4 / 827.7 | 789.8 / 836.6 | 801.3 / 838.9 |
| linux | 8 | 1296.7 / 1443.7 | 1310.5 / 1446.2 | 1426.8 / 1500.0 | 1432.0 / 1546.5 |

Paired group-ready median improvement (control−16M), ×1/4/8:
macOS +9.2 / −3.6 / −53.5 ms; Ubuntu +0.1 / −8.2 / −19.2 ms.
There is no consistent portable latency benefit. macOS ×8 group p95 is
2.858→3.036 s; one run does not establish a reproducible parallel-tail regression,
but it provides no reason to override the failed combined criteria.

## Incremental ready memory

Primary metric: Linux PSS sum; macOS physical-footprint sum. MiB p50 below.
G(0) includes Go host with zero DBs; G(n) includes host and n runtimes.
Incremental/n is calculated within each sample. Paired saving is the median
per-round control−16M difference, not subtraction of separately pooled medians.

| Platform | DBs | G(0) control | G(n) control | Incremental/DB control | Incremental/DB 16M | Paired saving/DB |
|---|---:|---:|---:|---:|---:|---:|
| darwin | 1 | 9.68 | 253.59 | 243.96 | 237.88 | 4.73 |
| darwin | 4 | 11.00 | 992.89 | 245.50 | 242.44 | 3.90 |
| darwin | 8 | 12.53 | 2018.49 | 250.73 | 245.52 | 4.33 |
| linux | 1 | 14.98 | 413.83 | 398.81 | 400.26 | 6.11 |
| linux | 4 | 15.31 | 1384.43 | 342.34 | 337.63 | 5.24 |
| linux | 8 | 18.24 | 2672.02 | 331.67 | 325.45 | 5.68 |

Control marginal growth, matched sequential rounds (1→4 / 4→8):
- darwin: 246.0 / 254.8 MiB per additional DB.
- linux: 321.6 / 322.1 MiB per additional DB.

Raw RSS and Linux private bytes are retained in JSON; macOS private bytes are
unavailable. These process accounting measures are not globally unique physical
memory. Linux PSS can change with sharing; macOS footprint is an accounting charge.
Unmapped kernel/filesystem cache is outside this process scope.

Sampled incremental group-peak p50, ×1/4/8:
- darwin 128M: 244.0 / 982.1 / 2005.9 MiB.
- darwin 16M: 237.9 / 969.7 / 1964.2 MiB.
- linux 128M: 398.8 / 1369.4 / 2653.6 MiB.
- linux 16M: 400.3 / 1350.5 / 2603.7 MiB.

Sampled peak medians equal the all-ready values in this run. macOS retained
108 transient startup counter gaps, Ubuntu none; incomplete samples never enter
peak calculations. Brief peaks may be missed. All mandatory baseline/ready/
after-close measurements succeeded. All runtimes disappear after every Close.
Per-cycle after-close increases have p95 <1 MiB, across repeated create/destroy
groups. This is bounded-run cleanup evidence, not proof of indefinite stability.

## CPU baseline

Combined host/runtime CPU seconds per DB, p50 / p95. All components use the
same G(0)→all-ready collection interval; shutdown/correctness SQL excluded.
Host includes sampler/bookkeeping, runtime includes all process threads.
Counter-helper/ps CPU excluded. Version query and sequential collection are
included. Linux CPU precision is limited by scheduler ticks.

| Platform | DBs | 128M CPU-sec/DB | 16M CPU-sec/DB |
|---|---:|---:|---:|
| darwin | 1 | 0.379 / 0.397 | 0.361 / 0.393 |
| darwin | 4 | 0.499 / 0.596 | 0.457 / 0.611 |
| darwin | 8 | 0.554 / 0.882 | 0.560 / 0.845 |
| linux | 1 | 0.520 / 0.550 | 0.530 / 0.550 |
| linux | 4 | 0.562 / 0.583 | 0.570 / 0.578 |
| linux | 8 | 0.572 / 0.589 | 0.572 / 0.589 |

Control ×1 component medians: macOS host 0.136 s / runtime 0.243 s;
Ubuntu host 0.190 s / runtime 0.330 s. These separate medians should not be added
as an exact decomposition of the combined median. Control ×8 amplification
CPU(8)/(8×CPU(1)), matched rounds: macOS 1.492 / 2.294 (p50/p95),
Ubuntu 1.092 / 1.151. The provisional 0.5 CPU-sec / 1.5× ideas must be considered
with these platform-specific scopes and variance, not promoted to CI gates.

## Aria and temporary-table workload

Actual `.MAD`: 65,544,192 bytes, ≈62.5 MiB, exceeding the 16 MiB cache.
Five fresh forks/condition passed 24,000-row count/length/CRC validation,
disk-backed internal temporary-table activity and isolated fork-local mutation.
Existing Go race/lifecycle and Python multi-client/interruption checks passed
in both conditions/platforms. Plugins remained enabled.

| Platform | 128M workload wall s p50/p95 | 16M workload wall | 128M CPU s p50/p95 | 16M CPU | Paired post-workload memory saving MiB |
|---|---:|---:|---:|---:|---:|
| darwin | 1.214 / 1.269 | 1.304 / 1.463 | 1.214 / 1.275 | 1.292 / 1.423 | 107.8 |

| linux | 1.187 / 1.198 | 1.312 / 1.322 | 1.190 / 1.198 | 1.320 / 1.328 | 115.6 |

Both platforms regress wall and CPU in all five pairs. Paired median
wall/CPU increases: macOS +93/+96 ms; Ubuntu +123/+130 ms.
Derived separate-distribution p50 increases are ≈7.4% wall / 6.4% CPU macOS,
≈10.5% / 10.9% Ubuntu. Five pairs support this bounded-workload trade-off;
they do not establish all application behavior. The aggregate includes scans,
checksum, GROUP BY/temp-table work and mutation; exact cache-miss attribution
is unknown. Post-workload group savings include host and one runtime and lack
a separate auxiliary G(0); they are not the canonical incremental-memory KPI.

Inference: physical cache-related pages become material after heavier Aria
activity, but the small reference fixture does not pay the full configured
128 MiB physically. Shrinking the cache trades heavier-workload CPU/wall for
memory, without the required ready-state isolation gain.

## Implications and remaining limits

- Reject this setting change; preserve the production cache and SQL semantics.
- The valid control baseline is macOS ≈244 MiB/DB footprint / 0.379 CPU-sec at
  ×1; Ubuntu ≈399 MiB/DB PSS / 0.520 CPU-sec. At ×8 the corresponding averages
  are ≈251/332 MiB per DB. RSS alone overstates this measure of marginal cost.
- The macOS control meets the 500/750 ms latency KPI in this run, Ubuntu p50
  532 ms does not. Previous macOS run was 576 ms, despite no product optimization;
  hosted-run variance prevents claiming a new canonical product improvement.
  ×8 macOS tail is also noisy; CPU amplification identifies continuing cost.
- Further attribution of non-Aria ready memory, restore and parallel scaling
  remains evidence for a strategy review. No additional cache tuning or
  architecture change is selected here. Numeric CPU/memory goals remain
  provisional; this experiment supplies scoped baselines for that decision.

## Final artifact identities

- darwin `init-aria-cache.json` SHA256: `c7f63584dd9d2ade6143b1742da63e37b63714b2e3f6e6dc5e35ab1f689bec8c`
- linux `init-aria-cache.json` SHA256: `19d60810f9ae5cbfa3fefe20dcd63f2c0b8bd718fef9d7ffc4cd75044d8de72d`

- Common WASM SHA256: `8603578dd5774645598234c86833db61dfcc7b07c25b39180b61635f60b078e8`
- macOS AOT SHA256: `386d610d0bd15865d7f1111119034d8aa771c6ae8861c0be0f709d8b5ebd5f80`
- Ubuntu AOT SHA256: `81c88817991fbc1a169bb763bc23beb612a998c25ff6f0c9a2d3ed675128e63b`
