# Final v0.2 prepared-state latency pass

Status: baseline collection pending. No optimization or final PASS/NOT MET
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
