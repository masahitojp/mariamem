# Ubuntu versus macOS prepared-state attribution

Status: completed [run 36519208622](https://github.com/masahitojp/mariamem/actions/runs/36519208622).
Measured main `dcfa03ae576ffa99de7b187c081a429c8a12a5ab`. No product
optimization, validation bypass or trust change. Raw artifacts remain ignored.
Historical comparison: [previous independent profile](final-v02-latency.md).

## Identity and measurement

Go 1.26.8, Python 3.14.7, Wasmer 7.4.2, unchanged production guest/settings,
1,000 rows/32-character payload. macOS 15.7.9 arm64 has three vCPUs; Ubuntu
24.04 x86_64 has four (kernel 6.17.0-1022-azure, glibc 2.39). OS, ISA and hosted
hardware vary together; this cannot causally isolate an OS implementation effect.

Each platform completed 30 independent full-startup trials per condition plus
two labelled warmup rounds, and 30 isolated verification rounds per case after
two warmups. All 64 startup children and 256 isolated operations passed.
Downloads were verified against the common WASM reuse seal, AOT manifest against
provenance, common WASM identity across platforms, and harness source hashes
against the measured commit. AOT bytes are absent from result bundles; CI, not
local analysis, rehashes them. Both runs used the same reused WASM/AOT hashes.
Product sources did not change between the two runs; changes are benchmark,
tests, workflow and analysis only.

Results: `initialization-<platform>-dcfa03a...` contains the full raw startup
reports/logs and `init-verification.json`; common guest files are in
`guest-wasm-dcfa03a...`. There are no tracked raw results or evidence commits.

## Full-startup distribution and runner variability

Milliseconds; public Fork entry through connected client's successful fixture
COUNT. Setup/Snapshot precedes Fork. No slow measured trial is removed.

| Platform / condition | n | min | p50 | p95 | max |
| --- | ---: | ---: | ---: | ---: | ---: |
| macOS production | 30 | 339.157 | 377.825 | 458.899 | 586.436 |
| macOS attribution | 30 | 353.906 | 400.289 | 475.295 | 573.224 |
| Ubuntu production | 30 | 421.967 | 434.187 | 453.558 | 510.239 |
| Ubuntu attribution | 30 | 425.971 | 437.523 | 460.453 | 468.755 |

**Measured fact:** unchanged Ubuntu now meets p50/p95 <500 ms in this run.
One trial still reached 510.239 ms. macOS also meets both percentiles here, with
an outlier of 586.436 ms. This is not an optimization or proof of stable
performance across hosted runs. The previous Ubuntu distribution was
522.725/534.336/554.333/564.033 ms min/p50/p95/max, with all 30 >=500 ms.
Its p50/p95 therefore fell by 100.149/100.775 ms without a product change.
The previous evidence must not be discarded when judging the final milestone.

The diagnostics-off platform p50 gap is now 56.362 ms, versus 79.263 previously.
The diagnostics-on gap is 37.234 ms, versus 104.765 previously. Paired diagnostic
wall delta median is +3.181 ms Ubuntu, +22.354 ms macOS; the macOS paired range
is -213 to +207 ms. These are different fresh processes/snapshots with alternating
order, not identical-instance counterfactuals. Diagnostic effects and hosted
variation cannot be subtracted as a fixed correction.

## Comparable phase breakdown

Attribution-on condition, milliseconds. Delta is Ubuntu minus macOS. Identical
boundaries are used, but percentile deltas are distribution comparisons, not
causal slices of the diagnostics-off p50 gap. Do not sum percentile columns.

| Phase | macOS p50 | Ubuntu p50 | Delta | macOS p95 | Ubuntu p95 | Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Native verification | 58.108 | 58.646 | 0.539 | 76.671 | 59.158 | -17.512 |
| Snapshot verification | 80.938 | 93.761 | 12.824 | 96.169 | 94.313 | -1.856 |
| Process creation call | 1.127 | 0.301 | -0.826 | 1.981 | 0.345 | -1.636 |
| Restore | 136.499 | 173.423 | 36.923 | 182.772 | 178.298 | -4.473 |
| MariaDB initialization | 66.356 | 70.495 | 4.139 | 98.613 | 88.230 | -10.384 |
| Unobserved startup envelope | 44.312 | 34.904 | -9.408 | 57.859 | 36.783 | -21.076 |
| Ready frame decode | 0.059 | 0.052 | -0.007 | 0.110 | 0.064 | -0.046 |
| Ready observation | 0.016 | 0.014 | -0.002 | 0.070 | 0.023 | -0.047 |
| Listener ready | 0.070 | 0.067 | -0.003 | 0.317 | 0.080 | -0.237 |
| Client connection | 5.760 | 5.445 | -0.315 | 13.165 | 6.643 | -6.522 |
| First SQL | 1.028 | 0.746 | -0.283 | 3.757 | 0.867 | -2.890 |
| API/host handoff | 0.152 | 0.083 | -0.069 | 0.500 | 0.114 | -0.386 |

Native and snapshot validation are sequential, disjoint host work. Restore and
MariaDB init are sequential inside spawn-to-ready. The residual subtracts the
recorded guest duration from the host envelope; host/guest clocks cannot be
aligned. It includes unobserved pre-main/runtime/CRT work, guest publication and
ready delivery, not directly measured pure Wasmer time. Process creation is
cmd.Start duration, not child first execution. Nested API/host scopes overlap.
The guest's minor bootstrap/ready preparation and other API bookkeeping remain
in raw traces; there is no distinct Wasmer-runtime-initialized hook.

**Measured fact:** restore is the largest positive phase difference (+36.923 ms),
followed by snapshot verification (+12.824), MariaDB init (+4.139) and native
verification (+0.539). The startup residual favors Ubuntu by 9.408 ms.
Readiness decode/observation/listener work is <0.1 ms median on both.
Thus the difference is localized mainly to restore and secondarily verification,
not a broad constant penalty across every stage or process creation.

Compared with the previous unchanged Ubuntu run, restore fell 232.150→173.423 ms,
snapshot validation 105.167→93.761, native validation 65.816→58.646, MariaDB
init 87.532→70.495 and residual 39.789→34.904. The largest phase change is
restore (~59 ms); variability also spans other work. These separate medians do
not reconstruct the exact 100 ms end-to-end improvement. Prior CPU model/cache
conditions were not recorded, so the cause of the run-to-run shift is unknown.
This does not contradict good Ubuntu x16 throughput on unequal hosted machines.

## Equivalent verification work

Both use the same Go standard `crypto/sha256`, production `snapshot.Digest`
and `io.Copy`, serial file scans and unchanged integrity/identity semantics.

| Dataset | macOS | Ubuntu | Contract |
| --- | ---: | ---: | --- |
| Native content | 3 files, 81,100,256 bytes (77.343 MiB) | 3 files, 89,791,560 bytes (85.632 MiB) | Runtime/AOT/sidecar hashes, manifest/platform/build and handoff mutation checks |
| Snapshot content | 11 files, 144,885,810 bytes | 11 files, 144,885,818 bytes | SHA-256 for every file; inventory, sizes, manifest/build/storage and types |
| Snapshot inventory | 15 entries | 15 entries | 11 files + four directories |

The fixture semantics match, not all physical bytes across OSes. Native runtime
and AOT binaries necessarily differ. The snapshot's eight-byte size difference
is in `ib_buffer_pool`; fixed redo/system/undo and fixture table sizes match.
Per-platform snapshot contents have their own hashes, including generated engine
state; no byte-identical cross-platform snapshot claim is made. Within each
1/2/4-worker experiment, the file list, sizes, contents and expected hashes are
exactly identical and every item is read and checked every time. Native hashes
exclude the unused packaged Python host. Counts above exclude manifest reads
and the small sidecar interpretation reread included in full validation.

## Isolated verification wall and CPU

All values p50/p95 milliseconds, n=30. CPU uses getrusage SELF over exactly the
same operation, including all worker threads. No DB/runtime remains active.
The macOS full native validator invokes sw_vers: its child CPU is excluded from
SELF; content-only cases have no child process. CPU here does not inherit the
subsecond ps precision problem of earlier lifecycle measurements.

| Case / workers | macOS wall | macOS CPU | Ubuntu wall | Ubuntu CPU |
| --- | ---: | ---: | ---: | ---: |
| native_full1 | 57.600 / 70.563 | 49.431 / 58.484 | 58.391 / 58.804 | 58.646 / 59.367 |
| snapshot_full1 | 88.824 / 103.339 | 88.696 / 104.172 | 93.335 / 93.662 | 93.850 / 94.903 |
| native_hashes1 | 46.271 / 57.307 | 46.337 / 55.154 | 58.290 / 59.112 | 58.655 / 59.733 |
| native_hashes2 | 38.394 / 47.118 | 45.566 / 54.944 | 44.981 / 45.972 | 59.035 / 60.477 |
| native_hashes4 | 38.655 / 44.291 | 46.070 / 54.105 | 45.075 / 45.856 | 59.190 / 60.713 |
| snapshot_hashes1 | 82.248 / 99.533 | 82.458 / 100.331 | 93.413 / 93.932 | 94.239 / 95.402 |
| snapshot_hashes2 | 59.918 / 79.016 | 88.138 / 110.996 | 64.965 / 66.571 | 94.335 / 97.664 |
| snapshot_hashes4 | 58.954 / 69.293 | 83.076 / 99.731 | 65.378 / 66.315 | 96.133 / 97.105 |

Full cases call unchanged production Resolve/Validate. Hash cases measure only
the complete content phase, including per-file regular-file/size checks; full
manifest/inventory/platform/build/mutation work is not repeated inside those
hash-only timings. The real contracts run before/after the experiment. Parallel
hash-only code returns no trusted artifact/snapshot to a lifecycle caller and
never runs on the product startup path. It is not a parallel full validator.
Order rotates/reverses over all cases; each case is sampled every round.

**Measured fact:** Ubuntu full-validation wall and SELF CPU are almost equal
(native ~58/59 ms, snapshot ~93/94 ms). Waiting is not dominant in these warm
isolated operations. This is consistent with CPU work in read+SHA256/syscalls/
copies, not proof that all CPU is inside SHA-256 compression. macOS snapshot
shows the same pattern; native full wall exceeds SELF CPU due to its platform
process and other scheduling work. No reliable per-read/hash CPU split exists.

Isolated native content is ~12 ms slower on Ubuntu, but processes ~11% more
bytes. Snapshot hash content is ~11 ms slower for effectively equal bytes.
Yet full native median differs by only ~0.8 ms because macOS platform work adds
cost, and full snapshot by ~4.5 ms in this isolated sequence. These comparisons
are not additive attribution of a startup percentile. Isolated verification
does not explain the earlier 80 ms difference by itself.

### Limited concurrency

Per round, sum the *two dataset* serial-minus-parallel wall differences, then
compute percentiles. This avoids adding independent median savings:

| Workers | macOS saving min/p50/p95/max ms | Ubuntu saving min/p50/p95/max ms | Ubuntu CPU change p50/p95 ms |
| --- | ---: | ---: | ---: |
| 2 | 11.757 / 31.822 / 45.206 / 62.248 | 39.207 / 41.575 / 42.559 / 43.581 | +0.530 / +3.124 |
| 4 | 16.579 / 33.511 / 46.539 / 65.132 | 40.137 / 41.197 / 42.105 / 43.022 | +2.455 / +3.875 |

**Measured fact:** two workers consistently remove ~42 ms of serialized content
wall time on Ubuntu with almost unchanged total CPU. Four offers no additional
Ubuntu benefit and consumes slightly more CPU. Large single files retain a
serial SHA-256 floor (redo ~96 MiB, AOT ~66 MiB); this experiment parallelizes
files, not blocks of one SHA stream. No end-to-end change is measured.

Median Go allocated bytes per native content operation: 101,040/101,120/101,504
at 1/2/4 workers; Ubuntu snapshot: 369,712/369,792/370,064. Benchmark-process (excluding guest)
cumulative peak RSS median stayed 18.16 MiB Ubuntu / 13.63 MiB macOS across
cases. These observations show no material benchmark allocation/peak increase,
but peak RSS cannot reset per case and does not establish marginal physical/PSS
cost under concurrent DB startup. No production memory conclusion is claimed.

## Filesystem/cache sanity

Ubuntu native and snapshot paths are both on ext4 on the same root NVMe-backed
mount. macOS paths are both on the same APFS Data volume. The recorded mounts
show no overlay filesystem on these paths. Linux mount options and macOS
filesystem attributes are retained in raw JSON; nothing is tuned.

Ubuntu reports AMD EPYC 9V74, four vCPUs/two exposed cores with SMT, Microsoft
hypervisor, SHA-NI/AVX2 available; macOS reports VirtualMac2,1 and ARM SHA256
capability. GOMAXPROCS is 4/3, GODEBUG empty; compile targets GOAMD64=v1 and
GOARM64=v8.0. Availability/compile baseline does not prove a particular hashing
assembly branch executed. The guest AOT SSE2+SSSE3 baseline is separate from
Go's host hashing CPU dispatch. The earlier run lacks equivalent CPU-model
records, so a hardware change cannot be asserted or excluded.

All repetitions are ordinary warm-cache work after fixture validation/warmups,
with no page-cache eviction. Warm page residency is not directly measured.
Full versus content timings and existing sub-millisecond metadata measurements
show no large repeated-open/manifest bottleneck. These are host-native validation
reads, not the later WASIX `/snapshot-in` restore reads. File-system type alone
cannot assign the restore gap to APFS/ext4, physical disk, page cache or Wasmer
servicing; those boundaries remain unresolved.

## Cross-platform latency attribution

The ~80 ms gap is not a stable OS constant: it narrowed to ~56 ms in production
and ~37 ms with attribution, while unchanged Ubuntu itself improved ~100 ms.
Across both runs, restore has the largest positive phase difference; verification
is secondary, and MariaDB's contribution varies. Readiness/process startup does
not exhibit a universal Ubuntu penalty. Both CPU ISA/hardware and filesystem/
servicing differences remain confounded; no pure OS causality is established.

## Parallel verification hypothesis

**PARTIALLY SUPPORTED — it helps, but likely does not close the gap by itself.**
The content experiment causally removes ~42 ms of wall work on Ubuntu while
preserving every content check and almost all CPU. The earlier unchanged run
needed >54 ms at p95, so even the observed ~44 ms maximum saving is insufficient
as a sole explanation/solution. A thought experiment 554.333−41.575≈512.758 ms
is *not* measured end-to-end latency and must not be presented as a prediction
of the p95. Full-startup interaction and parallel-DB tails are untested.

This new run already meets the numerical milestone without parallel validation;
that does not erase the previous failure or establish stable hosted-run p95.
No low-risk candidate demonstrated here alone guarantees <500 ms across the
observed execution conditions.

## Next optimization candidate

At most one: bounded **two-worker independent-file content verification** inside
otherwise unchanged per-startup native/snapshot validation, if a subsequent
production-quality A/B is justified. It is a ~42 ms latency-headroom candidate,
not a CPU reduction or a proven sole closure of the slow-run milestone.
All manifest/inventory/build/hash/mutation checks and deterministic prelaunch
failure must remain, with no global trust cache. End-to-end Ubuntu/macOS,
cleanup/corruption, parallel tails and resource regressions remain mandatory.
Four workers, restore changes and architecture work are not selected.
No production optimization is implemented by this analysis task.

## Fresh-runner reproducibility result

[Run 36521228629](https://github.com/masahitojp/mariamem/actions/runs/36521228629)
measured exact clean commit `99072a8a7f993a6d1459e30233def6a1286932f8`.
Five separately provisioned Ubuntu jobs each completed all 30 independent
measured Go-process/DB trials and two labelled warmups. Diagnostics were OFF;
the same 1,000-row fixture, production verification and ps sampler were used.
Fixture preparation/Snapshot is outside timed Fork; required startup work and
first verified fixture query remain inside. No slow trial was removed.
Percentiles use linear interpolation over each job's 30 per-DB latency samples;
150 trials are not pooled as one machine.

### Identity and environment

All jobs used Go 1.26.8, Python 3.14.7, four vCPUs, image
`20260920.314.1`, kernel `6.17.0-1022-azure`, and ext4 root storage for both
native inputs and temporary snapshots. They used the identical Go runner
SHA256 `b2a54af4023838ab9f8e6a58244ccfe081f147284281f737d54a785660a65eb9`.
Every recorded harness source hash matches the measured commit.

The shared input archive SHA256 is
`10e064751c4ffdd176be44831990552bc8c7e87a9aaa7d4261e7cbb2dff5b917`.
It was recomputed after download; all sealed files were rehashed, and each job's
manifest/provenance/reuse seal matches the archive. AOT SHA256 is
`e729fc07d7cb03de6b4bbf5334f0e1da460a8abfff56b0d3661b2688969e73fb`,
consuming WASM `41e3acfb51fe52ad13d9691de0bd3f05619266571e84dd1a0ddf263e082add7f`
with Wasmer 7.4.2 and SSE2 + SSSE3 baseline. This is reused immutable build
output: its retained provenance source commit is `d44157ad...`, and reuse seal
build checkout is `a8e5d5b...`; neither is relabelled as the measured Go checkout.
Workers downloaded these same bytes and verified reuse; they did not rebuild.

Raw JSON/logs remain in Actions artifacts `fresh-latency-1..5-99072a8...`;
`fresh-latency-input-99072a8...` contains the shared archive. Downloaded copies
are under `/private/tmp/mariamem-fresh-36521228629/`, outside tracked source.
Fresh jobs do not prove distinct physical hosts, and model labels do not expose
host contention, actual frequency, or storage throughput.

### Per-job distribution

All latency values below are milliseconds. CPU is **Go runner SELF CPU seconds
over the broader batch** (including sampling, hold and cleanup), not combined
host + guest CPU confined to Fork. It is supporting evidence only.

| Job | CPU model | min | p50 | p95 | max | >=500 ms | CPU p50 / p95 |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | AMD EPYC 9V45 96-Core Processor | 337.5 | 353.9 | 369.8 | 402.7 | 0/30 | 0.132 / 0.136 |
| 2 | AMD EPYC 7763 64-Core Processor | 519.6 | 544.5 | 565.2 | 569.1 | 30/30 | 0.189 / 0.193 |
| 3 | AMD EPYC 7763 64-Core Processor | 518.1 | 536.3 | 555.2 | 562.9 | 30/30 | 0.186 / 0.189 |
| 4 | INTEL(R) XEON(R) PLATINUM 8573C | 469.1 | 518.6 | 541.2 | 548.7 | 25/30 | 0.170 / 0.173 |
| 5 | AMD EPYC 7763 64-Core Processor | 516.9 | 541.7 | 564.9 | 577.1 | 30/30 | 0.186 / 0.189 |

### Within-job versus between-job variance

| Job | sample standard deviation (ms) | IQR (ms) | p95 minus p50 (ms) |
|---|---:|---:|---:|
| 1 | 12.5 | 10.9 | 16.0 |
| 2 | 11.6 | 11.9 | 20.7 |
| 3 | 10.7 | 13.9 | 18.9 |
| 4 | 17.6 | 21.1 | 22.6 |
| 5 | 15.3 | 21.2 | 23.2 |

**Derived calculation:** job medians span 353.9–544.5 ms (190.6 ms).
Their sample standard deviation is 81.8 ms, versus 13.8 ms root-mean-square
within-job sample standard deviation: approximately 5.9 times larger. These are
descriptive spreads, not an estimate of population variance components from five
independent machines.

**Measured fact:** the three EPYC 7763 jobs have tightly grouped medians
536.3–544.5 ms; the EPYC 9V45 job is 353.9 ms, and Xeon 8573C is 518.6 ms.
There are clear sampled fast/slow regimes associated with CPU model. Runner SELF
CPU is also lower on the fast job. **Inference:** execution environment is a
material confounder, not merely occasional slow trials within a stable runner.
**Unknown:** CPU generation alone is not causally isolated; frequency,
virtualization contention and storage may covary. Diagnostics OFF provides no
new per-stage attribution, so this does not locate the regime difference in
hashing versus restore versus initialization.

Historical unchanged-production controls remain relevant: run 36517366853
had 534.3 / 554.3 ms p50/p95; run 36519208622 had 434.2 / 453.6 ms on EPYC
9V74. The former resembles the current 7763 jobs; its CPU model was not recorded.
The latter is a different intermediate environment, not evidence of a product
speedup. Historical runs are not paired with these five jobs.

### Reproducibility and the 500 ms gate

**NOT MET:** only job 1 has both p50 and p95 <500 ms. Jobs 2, 3 and 5 have
every measured trial above 500 ms; job 4 has 25/30 above it. All jobs completed
successfully, so this is a performance result rather than a correctness failure.
The target is unchanged, and the fast job cannot substitute for the four failures.

The unqualified `ubuntu-24.04` hosted label is not currently a controlled enough
environment for a hard 500 ms product-regression release gate: identical code
and artifacts change verdict with job allocation. It remains useful for recording
performance and testing the explicit milestone. A pass there is not reproducible
across this sample, and this observation does not redefine the milestone or
justify filtering runners after seeing their results.

### Two-worker headroom: counterfactual only

The earlier isolated-content probe measured median combined saving 41.575 ms
(range 39.207–43.581 ms) on EPYC 9V74. Applying that identical saving to these
jobs is a **derived thought experiment**, not measured end-to-end parallel
verification, and transfer to other CPU models is unproven.

| Job | observed p95 (ms) | p95 minus 41.575 ms | saving needed for p95 <500 ms |
|---|---:|---:|---:|
| 1 | 369.8 | 328.3 | >0.0 ms |
| 2 | 565.2 | 523.6 | >65.2 ms |
| 3 | 555.2 | 513.6 | >55.2 ms |
| 4 | 541.2 | 499.6 | >41.2 ms |
| 5 | 564.9 | 523.4 | >64.9 ms |

The thought experiment still leaves jobs 2, 3 and 5 at approximately
514–524 ms p95; even subtracting the earlier largest observed saving does not
close them. Job 4 would have essentially no headroom. Thus ~42 ms helps, but is
not demonstrated to cover observed runner variance. Parallel verification is
not implemented or selected here. Its benefit may differ on slower processors;
only a measured end-to-end comparison could establish that.

### Decision inputs

- Between-job variation dominates the within-job noise in this sample.
- There is a model-associated performance regime, not proof of Ubuntu being
  uniformly slower than macOS or of a single OS-specific bottleneck.
- Stable p95 <500 ms across fresh hosted jobs is not established.
- The known ~42 ms candidate alone does not provide demonstrated headroom for
  the slow regime. No production optimization or threshold change is made.
