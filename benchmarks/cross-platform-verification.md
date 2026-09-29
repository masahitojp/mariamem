# Ubuntu versus macOS prepared-state attribution

Status: full-startup comparison available from [run 36517366853](https://github.com/masahitojp/mariamem/actions/runs/36517366853); isolated verification experiment pending.
No production optimization, validation bypass or trust change.

## Comparable boundaries

Measured host `9f20b21550bb7ee4d11ed727b1d7faa1a9be0f25`, 30 independent
trials per condition/platform, fresh Go process/1,000-row prepared fixture.
Ubuntu 24.04 x86_64 has four CPUs; macOS 15.7.9 arm64 has three CPUs.
Go 1.26.8 and Wasmer 7.4.2. OS, CPU ISA and hosted hardware differ together:
this is a platform/environment comparison, not an isolated causal OS experiment.

Production diagnostics-off p50/p95 is 455.074/498.673 ms macOS versus
534.336/554.333 ms Ubuntu (delta +79.263/+55.661 ms). Attribution-on total
is 436.207/534.612 versus 540.972/565.070 ms (delta +104.765/+30.458).
Different distribution shifts on macOS prevent assigning the 79 ms production
median difference exactly to attribution-on phase medians.

Each row below reports the same boundary on both platforms, milliseconds.
Delta means Ubuntu minus macOS. Percentile deltas are distribution comparisons,
not a per-Fork causal decomposition. Do not sum columns to reconstruct totals.

| Phase | macOS p50 | Ubuntu p50 | Delta | macOS p95 | Ubuntu p95 | Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Native verification | 59.013 | 65.816 | 6.803 | 70.632 | 66.397 | -4.235 |
| Snapshot verification | 87.842 | 105.167 | 17.325 | 104.104 | 105.699 | 1.595 |
| Process spawn call | 1.258 | 0.282 | -0.977 | 2.009 | 0.388 | -1.620 |
| Restore | 160.755 | 232.150 | 71.396 | 181.813 | 241.568 | 59.755 |
| MariaDB initialization | 65.856 | 87.532 | 21.676 | 89.706 | 105.027 | 15.321 |
| Startup residual | 47.169 | 39.789 | -7.380 | 60.917 | 42.591 | -18.326 |
| Ready-frame decode | 0.060 | 0.050 | -0.011 | 0.139 | 0.110 | -0.030 |
| Ready-response observation | 0.017 | 0.013 | -0.004 | 0.048 | 0.022 | -0.026 |
| Listener ready | 0.073 | 0.063 | -0.010 | 0.182 | 0.122 | -0.061 |
| Connection | 6.482 | 6.679 | 0.197 | 12.367 | 9.183 | -3.184 |
| First SQL | 1.096 | 0.948 | -0.149 | 3.834 | 1.418 | -2.415 |
| API/host handoff | 0.160 | 0.096 | -0.063 | 0.545 | 0.134 | -0.410 |

Native resolution and snapshot validation are sequential, disjoint host work.
Guest restore and MariaDB init are sequential within spawn-to-ready. Process
spawn is cmd.Start duration, not child first execution. The startup residual
subtracts the recorded guest duration from the host envelope; it includes
unobserved pre-main/runtime/CRT initialization and delivery/publication, and
cannot be labelled pure Wasmer cost. Guest/host clocks do not align. Nested
public API/host intervals overlap; they are not additional independent costs.
No separate runtime-initialized boundary exists without changing the runtime.

**Measured fact:** verification phase median differences total about +24 ms
(+6.8 native, +17.3 snapshot); restore differs by about +71.4 ms and MariaDB init
by +21.7 ms. The residual is smaller on Ubuntu by about 7.4 ms. Verification
therefore is not presently the sole explanation for the platform difference.
Those sums describe phase distributions, not exact attribution of the 79 ms
production p50 gap. Earlier x16 throughput/latency results do not contradict
localized x1 work differences on unequal hosted machines.

## Verification work and isolated experiment

Production uses Go standard crypto/sha256, serial file scans, via the same
snapshot.Digest/io.Copy implementation on both platforms. Snapshot data contains
11 files/four directory entries and about 138.17 MiB; manifests/inventory are
validated separately. Native Go startup hashes three files: runtime, AOT and
sidecar, excluding the unused packaged Python host. Native binaries necessarily
differ: ~81.1 MB macOS / ~89.8 MB Ubuntu logical reads. Source/build identity and
integrity semantics match, but native byte workloads are not literally identical.
Snapshot logical workload matches; its manifest includes its own identity bytes.

The new benchmark-only `--verification-probe` in the canonical Go runner:

- Prepares the unchanged public API fixture/Snapshot; production Resolve and
  Validate establish valid input. Setup and environment commands are excluded.
- Measures complete unchanged production native Resolve and snapshot Validate
  separately from startup, with getrusage SELF CPU over the same wall interval.
- Measures the complete content scan separately at 1/2/4 workers, using exactly
  the same file list, expected hashes, SHA-256 routine and regular-file/size
  checks at each worker count. All files are hashed every repetition; no cache
  of digests, early success, skipped large files or persistent trust is used.
- Rotates/reverses order over 30 rounds after two labelled warmups, recording
  raw wall/CPU samples, file/byte counts, hashes and Go heap-allocation deltas.
- Rechecks the full production contracts after all experimental content scans.

The parallel experiment is **only a content-phase experiment**, not a parallel
production validator. Full manifest/inventory/build/platform/mutation semantics
are measured in the separately labelled serial full-validator cases and remain
unchanged in all real Start/Fork paths. Hash-only speedup must not be reported
as an end-to-end or full-validation result. Benchmark code is never called by
product startup. Corruption/missing input fails the probe at every worker count.

Process cumulative peak RSS is retained but cannot reset per operation and is
not incremental/PSS memory. Allocation deltas observe the potential extra hash
buffers; stack/runtime physical costs are not precisely attributed. No expensive
memory diagnostics are added. CPU counters include all benchmark worker threads,
with no guest process alive during isolated verification.

Filesystem sanity records df/mount output for both native and snapshot paths,
Linux filesystem types and lscpu, macOS hardware/SHA capability sysctls, Go build
information and GODEBUG/GOMAXPROCS. Flags show availability, not proof that an
assembly branch executed. Runs are repeated warm-cache work; no cache flushing,
disk-I/O claim, privileged tuning or overlay assumption is made. A full native
Resolve includes macOS sw_vers, while its content-only case does not.

CI reuses exact verified unchanged WASM/AOT inputs. The existing
`final_latency_baseline=true` dispatch repeats the comparable full-startup
profile and then isolated verification in the same job. Raw evidence is
`init-final-latency*.json` plus `init-verification.json/.md` in
`initialization-<platform>-<candidate SHA>`. Nothing is released.

## Cross-platform latency attribution

Current evidence localizes much of the difference to restore, with smaller
verification and MariaDB contributions; it does not establish a platform-wide
Wasmer constant. Isolated wall/CPU/throughput/cache results are required before
assigning the cause to hashing, filesystem servicing or CPU architecture.

## Parallel verification hypothesis

Verdict pending the isolated 1/2/4-worker measurements. No SUPPORTED/PARTIALLY
SUPPORTED/NOT SUPPORTED verdict is manufactured from theoretical subtraction.
The observed production Ubuntu p95 requires >54 ms improvement. The earlier
~47 ms optimistic independent-smaller-file bound alone does not establish this.

## Next optimization candidate

None selected before isolated measurement. At most one candidate will be named
once its measured wall/CPU/resource effects and the platform comparison are
available. This task implements no production parallel hashing or restore change.
