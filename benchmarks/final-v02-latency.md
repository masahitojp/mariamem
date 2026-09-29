# Final v0.2 prepared-state latency pass

Status: before-change baseline completed in [run 36517366853](https://github.com/masahitojp/mariamem/actions/runs/36517366853). No optimization or final PASS/NOT MET
verdict is established yet. Work starts from main `262b29c`; restore,
verification, MariaDB configuration and runtime behavior are unchanged.

The milestone for this pass is **Ubuntu 24.04 x86_64 Fork → usable SQL p50
<500 ms and p95 <500 ms**, with at least 20 measured independent trials.
Slow trials remain in the distribution. This is stricter than the earlier
500/750 ms product KPI and is not silently substituted for it.

## Baseline

The latest resource-envelope run measured Ubuntu ×1 543.38 / 550.88 ms
p50/p95. It includes intrusive process-tree counter observations, so it is
context rather than a precise unobserved production latency distribution.
The verification probe measured 516.56 / 539.19 ms with lightweight timing
and `ps` sampling. These are different hosted runs, not a causal comparison.

Source inspection establishes sequential native and snapshot validation.
Both scan distinct bytes once; removing them would change required guarantees.
Readiness uses a response channel, not polling. Ready decode/handoff was
<0.1 ms. Restore and MariaDB initialization remain large separate guest stages.
There is no established redundant 43 ms operation to remove yet.

Dispatch the existing `guest-build-boundary.yml` with
`final_latency_baseline=true` at an exact pushed main commit. It reuses verified
unchanged WASM/AOT inputs and runs both supported platforms. The thin
`benchmarks/final_latency.py` supervisor invokes the existing canonical Go
runner; it does not introduce a different startup implementation.

- Thirty measurement rounds per condition, each in a fresh Go process with
  a fresh isolated Fork. Alternate condition order each round.
- Production condition: lifecycle diagnostics off. Attribution condition:
  existing host/guest stage diagnostics on. Both retain the existing `ps`
  cost sampler; this observer is not declared free.
- Two explicitly labelled warmup rounds per condition are retained but excluded
  from measured percentiles. Go compilation, fixture creation and Snapshot
  precede Fork entry. All validation, restore, runtime and readiness work from
  public Fork entry through connection and successful fixture COUNT is timed.
- No setup or ready observation is subtracted from that metric. VERSION and
  cleanup follow first SQL. CPU/RSS keep their existing broader interval and
  sampling limitations; no per-stage CPU or primary physical memory is invented.
- A failed trial fails collection, retaining prior evidence and the failure
  log. It cannot disappear from a successful distribution.

Artifacts: `initialization-<platform>-<candidate SHA>` contains
`init-final-latency.json`, per-child raw reports/logs, min/p50/p95/max summary,
stage waterfall and AOT provenance. Raw artifacts remain ignored.

## Changes and final result

Only baseline orchestration is added at this point. Product changes require a
concrete avoidable interval supported by this new profile. Any candidate must
preserve all native/snapshot integrity checks and pass SQL, Snapshot/Fork,
multi-client, interruption, cleanup and both-platform resource regressions.
No optimization is selected before these baseline results are available.

The completed follow-up will record every candidate's measured effect, final
30-trial distribution, CPU/memory observations and macOS regression result.
The final verdict must be either `PASS — stable prepared-state startup is below
500 ms` or `NOT MET — remaining latency requires work outside the permitted
v0.2 optimization scope`; pending measurements support neither verdict yet.

## Completed before-change profile

Measured commit: `9f20b21550bb7ee4d11ed727b1d7faa1a9be0f25`, clean.
Go 1.26.8, Python 3.14.7 and Wasmer 7.4.2; Ubuntu 24.04 x86_64,
kernel 6.17.0-1022-azure, four CPUs; macOS 15.7.9 arm64, three CPUs.
The machines are not equivalent hardware. All 64 child executions per platform
passed (four warmup children and 60 measured children).

Downloaded WASM handoff files were rehashed against their sealed reuse record;
AOT manifest hashes matched provenance, and both platforms identified the same
WASM. Harness source hashes matched the measured commit. AOT bytes are not in
these result bundles; their binary verification is performed by CI, not repeated
locally. The producing guest identity remains the verified reused identity.

### Full latency distribution

Public Fork entry through first successful fixture COUNT, milliseconds:

| Platform / condition | n | min | p50 | p95 | max | Trials >=500 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Ubuntu production | 30 | 522.725 | 534.336 | 554.333 | 564.033 | 30 |
| Ubuntu attribution | 30 | 522.049 | 540.972 | 565.070 | 572.008 | 30 |
| macOS production | 30 | 352.145 | 455.074 | 498.673 | 569.710 | 2 |
| macOS attribution | 30 | 360.174 | 436.207 | 534.612 | 576.832 | 2 |

**Measured fact:** unchanged Ubuntu does not meet either percentile target.
This run is sufficiently consistent to judge the failure: even its minimum is
above 500 ms. No slow run is removed. The production p95 gap is 54.333 ms,
larger than its p50 gap of 34.336 ms. Passing macOS p95 in one hosted run is not
proof of a production improvement; there were two >500 ms trials.

**Derived calculation:** paired attribution-minus-production median is +4.913 ms
on Ubuntu and -4.159 ms on macOS. Pair order alternates; each pair uses different
processes and freshly prepared snapshots. The negative macOS delta indicates
noise/order/resource variability, not that diagnostics accelerate startup.
Removing diagnostics alone cannot explain a reproducible 54 ms saving. Both
conditions retain ps sampling, so its perturbation has not been isolated.

### Phase attribution

Attribution condition, p50 / p95 milliseconds. Each row is an independently
computed distribution of a real interval; do not add percentile columns.

| Boundary | Ubuntu | macOS |
| --- | ---: | ---: |
| Native resolution/verification | 65.816 / 66.397 | 59.013 / 70.632 |
| Host snapshot verification | 105.167 / 105.699 | 87.842 / 104.104 |
| Guest restore | 232.150 / 241.568 | 160.755 / 181.813 |
| Guest MariaDB initialization | 87.532 / 105.027 | 65.856 / 89.706 |
| Startup envelope outside recorded guest interval | 39.789 / 42.591 | 47.169 / 60.917 |
| Connect | 6.679 / 9.183 | 6.482 / 12.367 |
| First fixture SQL | 0.948 / 1.418 | 1.096 / 3.834 |
| API/host handoff outside host trace | 0.096 / 0.134 | 0.160 / 0.545 |

Native read+hash is runtime 15.214/15.474 ms and AOT 50.245/50.736 ms
on Ubuntu. Snapshot redo read+hash is 72.792/73.207 ms; system file
9.080/9.284 ms and the three undo files each about 7.54/7.6 ms.
These are distinct required scans, not duplicate checks within Fork.
The residual startup envelope remains a duration difference with unaligned
host/guest clock origins; it is not measured pure Wasmer initialization CPU.

### CPU and memory observations

Production whole-batch Go runner CPU median is 0.185773 CPU-sec Ubuntu and
0.166622 macOS; attribution is 0.187608 and 0.160712. These counters include
host/sampler/driver/hold/cleanup. They are not exact first-SQL-interval CPU or
per-stage hashing CPU. Ubuntu ps descendant CPU is too coarse for the short
startup and must not be interpreted as zero guest CPU.

Secondary incremental ready tree RSS median is 405.0 MiB Ubuntu and 332.6 MiB
macOS in production, versus 405.6 and 335.5 MiB with attribution. This does not
replace the earlier PSS/private/physical-footprint envelope. No runtime change
was made and no physical-memory improvement/regression is claimed.

### Low-risk candidate boundary and current limits

**Source fact:** independent file hashes execute serially. Mandatory native and
snapshot checks account for about 171 ms of sequential verification on Ubuntu.
The non-redo snapshot files consume approximately 32 ms of read+hash; the native
runtime scan consumes another 15 ms. Their sequential placement is a concrete
candidate for bounded independent-file concurrency while retaining every hash,
inventory comparison, mutation check and prelaunch failure. CPU, memory and
macOS effects would need a real candidate A/B; current measurements establish
cost, not avoidability or savings.

**Derived bound:** merely hiding those smaller file scans behind the largest
scan suggests an optimistic order-of-magnitude opportunity of ~47 ms. This is
not measured end-to-end improvement, and is less than the current 54 ms p95 gap.
Scheduler/contention effects could reduce it. It therefore does not justify
promising stable sub-500 ms, nor does it establish that a prohibited architecture
change is necessary.

Ready notification and metadata/serialization are sub-millisecond opportunities.
The ~40 ms runtime-start envelope is substantial but still unsplit and cannot
safely be deleted. Restore remains required materialization under the unchanged
implementation. The final pass remains open: baseline failure is established;
no optimization has yet passed the correctness/resource guardrails, and no
structural impossibility verdict is supported by this profile alone.

## Later unchanged control

[Run 36519208622 analysis](cross-platform-verification.md) repeats this profile
without a product optimization: Ubuntu production p50/p95 became
434.187/453.558 ms (min 421.967, max 510.239), 30 independent trials.
This run meets both numerical percentiles, but does not invalidate the earlier
failure or establish stable hosted-run performance. The cross-platform report
separates this run variability from the benchmark-only parallel-hash experiment;
no final production improvement or across-run PASS is claimed.
