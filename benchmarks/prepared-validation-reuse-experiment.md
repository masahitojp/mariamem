# Within-call validation reuse under prepared RSA keys

Branch: `experiment/prepared-auth-keys`. Experiment only; nothing is merged or
productionized. Paired measurements confirm preparation/CPU savings and
end-to-end median improvement on both platforms; macOS tail improvement is not
established.

## Exact conditions

- A: existing test RSA keys, current validation path.
- B: the same keys and native bytes, with the **existing**
  `benchmarks/validation_reuse.py::patch` applied only to a disposable source copy.

The probe skips two redundant AOT digests: sidecar validation consumes the digest
already checked by artifact resolution, and host startup receives that same
verified build identity within the current call. Initial manifest/native artifact
hashes, sidecar/build identity and snapshot inventory checks remain. No persistent
cache, new trust scope, restore change or MariaDB setting change is introduced.

`benchmarks/prepared_validation_reuse.py` archives the same exact committed source
twice, applies the existing patch to B only, runs artifact/snapshot/host tests on
both copies, and builds both Go canonical benchmark runners once before timing.
Both conditions use **one shared read-only native path** and one generated,
checked, disposable 2048-bit RSA pair. This avoids the previous control-original
versus reuse-private native-path confounder. No private PEM is uploaded; key hashes
are recorded and temporary material is deleted. Native/key hashes must be unchanged
after all trials. Public SQL probes check plugin ACTIVE and exact public-key match;
all 14 recorded Start/Fork diagnostics per invocation must prove successful loading
without key generation. Existing grant-bypass semantics remain unchanged; this is
not a full caching_sha2_password authentication exchange test.

## Paired measurement and immutable reuse

Dispatch `guest-build-boundary.yml` on this branch with
`prepared_validation_experiment=true`. Both macOS 15 arm64 and Ubuntu 24.04 x86_64
jobs reuse the existing identity/hash/provenance-verified experimental WASM/AOT
when their input identities match. No guest source/runtime/CPU settings changed.
The workflow verifies the AOT again after measurement. It does not release anything.

Two warmup pairs and 20 measured pairs alternate A/B and B/A ordering. Each runner
uses the canonical 1,000-row fixture, first COUNT readiness, and ×1/4/8 worker order.
Fixtures are separately prepared with identical logical contents. Memory diagnostics
are **off**; initialization events and sampled CPU/RSS remain. Separate-process
runs retain normal process/runtime lifecycle, not a prewarmed Database or cache.

Results are workflow artifacts named `initialization-<platform>-<source-sha>`,
under `benchmarks/results/init-prepared-validation/`: raw pair JSONs,
`summary.json`, `summary.md`, plus platform AOT provenance/manifest. The summary
records exact source SHA, modified-copy source hashes, both runner binary hashes,
native/key hashes, platform identity and paired differences. Raw files retain Go
version/server/CPU environment, CPU samples and structured guest counters.

The waterfall includes Fork→SQL, public-outside-host, host validation, combined
preparation, restore, embedded init and launch-envelope residual. Public-outside-host
includes preparation before host startup **and** trace/write/return tail afterward;
these are not separately timed. Combined preparation is calculated per DB before
quantiles. Launch residual starts at spawn-begin to avoid mistaking guest execution
overlapping `cmd.Start` for negative runtime overhead. It still includes unobserved
runtime/CRT setup and ready/diagnostic delivery; it is not pure Wasmer time.

Each parallel trial contributes one within-batch median to paired-difference
statistics; per-DB quantiles and batch completion quantiles are also retained.
Do not sum medians, treat parallel DB observations as independent batches, or call
historical hypothetical subtraction a new measurement. CPU collection has startup
and shutdown blind spots; process CPU includes other guest threads and Unix `ps`
has platform-dependent precision. No thresholds gate informational performance.

## Measured results

Run: https://github.com/masahitojp/mariamem/actions/runs/36288180288.
Measured source: `9741c850aee026a7a871adc7330fa6771379ba15`.
MacOS 15.7.9 arm64, 3 CPUs; Ubuntu 24.04.5 x86_64, 4 CPUs (kernel
6.17.0-1022-azure, glibc 2.39). Go 1.26.8, Wasmer 7.4.2, MariaDB 13.1 embedded.
Ubuntu CPU baseline remains SSE2+SSSE3. Cross-platform absolute latency is not
a comparison of equivalent hardware.

Artifact ZIP digests were checked before safe extraction:

- macOS: `52616ca4ba124512f1807255f51be11144c95738654fc00f0adc54b75746c099`
- Ubuntu: `e2ca7a97ae88dd474f82787d6b483aacc6c495129d7bd96ad077a41a50ce6319`

Both jobs reused the identical previously verified WASM
`5217a52112c28cd79925b41f462d1bd2bc758923b6d89ec3e3f1eaf9dc2cad65`.
Mac AOT: `c00d462ef9a1f5c520b6651ae00aad5661aca5c243c41ea42deedf917c86cef1`;
Ubuntu AOT: `c5667454f86d62cfb3a491493a5f75aa6d06511d170240698aac05d7c3b843e9`.
Original build provenance still identifies `25a02d2`; it was not relabelled.
No WASM/AOT rebuild occurred. Private native/key hashes remained unchanged.

All 44 runner invocations per platform completed and validated 14 recorded
prepared-key Start/Fork records each (616 total), with no RSA generation and
successful key loading. Public SQL probes checked ACTIVE/public-key match.
Artifact/snapshot/host integrity tests passed in both source copies before
measurement. Downloaded raw reports were revalidated, and recomputing the entire
summary from 20 measured pairs matched `summary.json` exactly.

### Updated prepared-key waterfall

Wall **p50 / p95 milliseconds**. Per-DB rows have n=20/80/160 at ×1/4/8;
batch completion has 20 samples. Combined preparation is computed per sample,
not by adding the preceding public/host medians. Those rows overlap; embedded
init includes post-srv plugins. Percentiles must not be added together.

| Platform | Condition | Stage | ×1 | ×4 | ×8 |
|---|---|---|---:|---:|---:|
| macos | control | per-DB Fork to SQL | 564.4 / 641.7 | 918.0 / 1081.0 | 1670.4 / 1912.1 |
| macos | control | batch Fork to SQL | 564.4 / 641.7 | 961.6 / 1123.5 | 1846.4 / 1969.5 |
| macos | control | public outside host | 113.8 / 139.2 | 160.1 / 239.0 | 330.2 / 512.6 |
| macos | control | host validation | 132.1 / 151.3 | 214.2 / 421.6 | 506.2 / 844.2 |
| macos | control | combined preparation | 246.2 / 292.5 | 374.6 / 631.2 | 839.0 / 1287.3 |
| macos | control | restore | 157.2 / 179.7 | 219.8 / 353.1 | 202.2 / 399.6 |
| macos | control | embedded init | 82.9 / 122.1 | 161.4 / 228.6 | 338.4 / 533.0 |
| macos | control | launch envelope residual | 63.9 / 73.3 | 93.2 / 191.4 | 112.4 / 281.0 |
| macos | reuse | per-DB Fork to SQL | 485.4 / 691.2 | 799.5 / 1119.2 | 1405.5 / 1679.6 |
| macos | reuse | batch Fork to SQL | 485.4 / 691.3 | 821.9 / 1124.2 | 1596.8 / 1760.5 |
| macos | reuse | public outside host | 71.0 / 85.4 | 92.9 / 139.6 | 193.0 / 404.2 |
| macos | reuse | host validation | 91.7 / 103.1 | 142.8 / 344.2 | 347.8 / 718.8 |
| macos | reuse | combined preparation | 163.6 / 185.1 | 237.4 / 480.6 | 546.0 / 991.8 |
| macos | reuse | restore | 156.2 / 202.2 | 242.1 / 407.4 | 234.4 / 450.1 |
| macos | reuse | embedded init | 75.9 / 107.2 | 165.9 / 263.2 | 363.2 / 549.1 |
| macos | reuse | launch envelope residual | 62.2 / 77.8 | 95.3 / 213.2 | 153.9 / 362.7 |
| ubuntu | control | per-DB Fork to SQL | 634.5 / 650.2 | 835.6 / 946.8 | 1487.6 / 1614.6 |
| ubuntu | control | batch Fork to SQL | 634.5 / 650.2 | 912.2 / 974.2 | 1596.2 / 1652.8 |
| ubuntu | control | public outside host | 114.8 / 116.4 | 129.7 / 142.6 | 249.3 / 304.2 |
| ubuntu | control | host validation | 154.0 / 154.7 | 175.0 / 189.9 | 355.2 / 445.6 |
| ubuntu | control | combined preparation | 268.9 / 271.1 | 306.7 / 322.6 | 606.7 / 720.3 |
| ubuntu | control | restore | 223.4 / 236.8 | 282.8 / 422.0 | 475.1 / 651.9 |
| ubuntu | control | embedded init | 87.6 / 104.5 | 140.6 / 184.5 | 223.5 / 317.6 |
| ubuntu | control | launch envelope residual | 43.1 / 45.6 | 69.5 / 84.7 | 128.5 / 202.7 |
| ubuntu | reuse | per-DB Fork to SQL | 531.5 / 554.9 | 731.7 / 812.4 | 1286.2 / 1431.2 |
| ubuntu | reuse | batch Fork to SQL | 531.5 / 554.9 | 783.7 / 838.6 | 1395.9 / 1501.2 |
| ubuntu | reuse | public outside host | 66.0 / 66.4 | 71.9 / 84.4 | 143.8 / 194.4 |
| ubuntu | reuse | host validation | 104.5 / 105.0 | 118.6 / 133.4 | 243.2 / 334.0 |
| ubuntu | reuse | combined preparation | 170.5 / 171.3 | 191.4 / 206.6 | 386.2 / 486.2 |
| ubuntu | reuse | restore | 225.8 / 236.1 | 300.5 / 398.2 | 490.0 / 676.7 |
| ubuntu | reuse | embedded init | 85.8 / 106.2 | 147.8 / 181.9 | 234.6 / 312.5 |
| ubuntu | reuse | launch envelope residual | 43.3 / 45.9 | 69.8 / 87.5 | 133.5 / 191.0 |

### Paired effect

Positive differences mean control was slower. Each pair contributes one
within-batch median per-DB/interval difference or one batch completion difference.
This is **not** subtraction of the aggregate table medians. The p95 column is
a quantile of observed savings, not a confidence limit or readiness p95.

| Platform | × | Metric | Savings p50 / p95 ms | Positive pairs / 20 |
|---|---:|---|---:|---:|
| macos | 1 | combined preparation | 85.3 / 128.9 | 20/20 |
| macos | 1 | per-DB Fork to SQL | 103.1 / 199.5 | 18/20 |
| macos | 1 | batch Fork to SQL | 103.1 / 199.5 | 18/20 |
| macos | 4 | combined preparation | 130.5 / 267.7 | 19/20 |
| macos | 4 | per-DB Fork to SQL | 76.0 / 328.1 | 15/20 |
| macos | 4 | batch Fork to SQL | 96.6 / 324.8 | 16/20 |
| macos | 8 | combined preparation | 312.3 / 507.9 | 20/20 |
| macos | 8 | per-DB Fork to SQL | 298.5 / 430.5 | 19/20 |
| macos | 8 | batch Fork to SQL | 288.7 / 399.6 | 19/20 |
| ubuntu | 1 | combined preparation | 98.1 / 100.3 | 20/20 |
| ubuntu | 1 | per-DB Fork to SQL | 97.4 / 126.3 | 20/20 |
| ubuntu | 1 | batch Fork to SQL | 97.4 / 126.3 | 20/20 |
| ubuntu | 4 | combined preparation | 114.4 / 123.4 | 20/20 |
| ubuntu | 4 | per-DB Fork to SQL | 97.5 / 244.3 | 19/20 |
| ubuntu | 4 | batch Fork to SQL | 131.7 / 238.1 | 20/20 |
| ubuntu | 8 | combined preparation | 220.7 / 270.0 | 20/20 |
| ubuntu | 8 | per-DB Fork to SQL | 207.2 / 322.0 | 20/20 |
| ubuntu | 8 | batch Fork to SQL | 207.8 / 265.2 | 20/20 |

Measured fact: ×1 paired preparation savings are **85.3 ms macOS / 98.1 ms
Ubuntu**, positive in all 20 pairs. Paired first-SQL savings are **103.1 / 97.4 ms**,
positive in 18/20 macOS and 20/20 Ubuntu pairs. Inference: the removed repeated
hashing materially contributes to readiness; the stronger paired design now
supports end-to-end causality on both platforms. Variation in other stages means
it is not valid to attribute every individual latency difference to hashing.

At ×4/8, paired preparation savings are macOS 130.6/312.3 ms and Ubuntu
114.4/220.7 ms; batch-readiness savings are macOS 96.6/288.7 and Ubuntu
131.8/207.8 ms. The savings persist under concurrency but do not remove its cost:
reuse per-DB median rises ×1→×8 from 485→1405 ms macOS and 532→1286 ms Ubuntu.

**Tail caveat:** macOS ×1 readiness p95 increases 641.7→691.2 ms; ×4 per-DB
p95 increases 1081.0→1119.2 ms (batch p95 is essentially unchanged). ×8 improves.
Ubuntu p95 improves at every level. Twenty pairs demonstrate a median benefit,
not stable tail guarantees, no-regression evidence for every percentile or a
portable performance promise.

### CPU observations

Median CPU seconds for the Go runner over the full batch (host hashing, driver,
GC, sampler, hold and cleanup included; guest subprocess CPU excluded). This is
not directly instrumented validation-only CPU.

| Platform | Condition | ×1 | ×4 | ×8 |
|---|---|---:|---:|---:|
| macos | control | 0.256 | 0.992 | 1.995 |
| macos | reuse | 0.174 | 0.630 | 1.262 |
| ubuntu | control | 0.285 | 1.189 | 2.376 |
| ubuntu | reuse | 0.186 | 0.762 | 1.527 |

Derived differences of these full-run medians: macOS ~82/362/733 ms less
runner CPU at ×1/4/8; Ubuntu ~99/427/849 ms less. Source fact: only the known
digest-reuse patch differs. Inference: the CPU reduction is consistent with
removing two AOT reads/hashes per DB, but includes all runner CPU, not exclusive
validation attribution.

Embedded-init per-DB process CPU p50 control→reuse stays close: macOS
88.8→81.9 / 103.3→105.4 / 105.8→103.3 ms; Ubuntu
97.2→96.0 / 115.2→115.7 / 118.8→118.3 ms. Guest workload is not bypassed.
Mac sampled descendant batch CPU p50 is control 0.32/1.46/2.66 s versus reuse
0.33/1.46/2.575 s. Ubuntu sampled descendant CPU is zero at the median in both
conditions because `ps` uses coarse whole-second values; zero is not no CPU.
Guest counter process/thread CPU quantiles remain in raw/summary JSON.

### What remains and what now dominates

1. **Remaining integrity work (source fact):** initial required native artifact
   hashes, manifest checks, sidecar/WASM build identity, snapshot root/layout,
   full snapshot file inventory/type/size/content hashes. There is no global
   path cache or cross-call trust. Reuse host validation still costs ×1
   ~91.7 ms macOS / 104.5 ms Ubuntu; public-outside-host ~71.0/66.0 ms.
   Host timers do not split snapshot hashing from metadata/filesystem overhead.
2. **Remaining ×1 cost:** Ubuntu restore ~225.8 ms exceeds combined preparation
   ~170.5 ms, init ~85.8 and residual ~43.3. Mac restore ~156.2 and combined
   preparation ~163.6 are effectively co-dominant, ahead of init ~75.9 and
   residual ~62.2. It is inaccurate to declare restore uniquely dominant on both.
3. **Concurrency:** Ubuntu reuse restore grows to ~490.0 ms at ×8 versus combined
   preparation ~386.2, init ~234.6. Mac ×8 preparation ~546.0 and init ~363.2
   exceed restore ~234.4. There is no universal dominant stage across workloads.
4. **Other-stage variation:** ×1 restore is nearly unchanged within this run;
   ×4/8 reuse restore is sometimes higher; macOS ×8 residual also increases
   ~112→154 ms. Do not subtract preparation savings from baseline and advertise
   that value as a new measured readiness result. Required filesystem/runtime
   work and scheduling are still present.
5. **Earlier baseline comparison:** old prepared-key macOS restore was ~225 ms
   and readiness ~649 ms; this new control is ~157/564 ms. Ubuntu control remains
   ~223/634 versus old ~226/640. No causal claim is made about cross-run changes:
   different runner state, native path/cache warmth and removing post-ready
   diagnostics can confound them. Use the current paired control for this effect.
6. **FAST target:** measured reuse ×1 p50/p95 is macOS 485/691 ms and Ubuntu
   532/555 ms, still missing p50<250/p95<500. At this point restore is a justified
   next investigation target, especially Ubuntu, but eliminating it alone has
   not been measured and cannot be promised to reach the goal.

### CI efficiency and verification

Measured operational fact: first guest-job start to final platform-job completion
was **5 minutes**. Guest preparation finished in 11 seconds via verified WASM
reuse; both AOT build steps were skipped via verified reuse. Experiment steps
lasted **3m53s Ubuntu / 4m15s macOS**, including private-source integrity tests
and runner compilation. No expensive memory diagnostics were run.
This is evidence the reusable build boundary avoids needless guest rebuilds,
not a mariamem SQL/lifecycle speed metric. No CI polling or infrastructure changes
were needed to analyze completion.

Raw artifacts remain ignored under `benchmarks/results/validation-36288180288/`.
Only this report is committed. Analysis verification: ZIP hashes, exact source,
616 prepared-key diagnostic checks/platform, complete raw runs, exact summary
recomputation; `git diff --check` and public-source check. No runtime code changed.

## Ready for main?

**Prepared RSA keys: sufficient causal performance evidence, not yet a
production-ready implementation.** The dramatic original callback/CPU result
persists without plugin disablement, and this run proves it composes with host
validation reuse. Still required before integration: choose explicit key
lifetime/location and test-only security policy; test missing/corrupt/mismatched
key failure and diagnostics; verify Start, Snapshot/Fork/isolation, multi-client,
timeout/invalidation and cleanup on both platforms; verify packaged identity,
licenses/provenance and production defaults. Clarify actual supported auth
behavior: the embedded guest retains skip-grant-tables and these public SQL
probes do not test a full caching_sha2_password authentication exchange.
No production provisioning choice or merge is authorized by these measurements.

**Validation reuse: measured median/CPU benefit and private-copy integrity tests
pass.** Integration would still need a production-quality typed within-call
identity design and explicit immutable-input/ownership assumptions. The shared
read-only experiment bundle does not prove correctness for native files mutated
during a public startup call. Preserve rejection/cleanup tests and both platform
lifecycle/race checks; do not merge the prototype context-string/variadic patch
or introduce persistent trust caches. MacOS tail variability remains unresolved.

## Recommended next 0.2 FAST step

Exactly one next step: **a bounded restore-copy attribution probe under prepared
keys plus the same within-call validation reuse**, separating snapshot reads/
host→WASIX materialization from guest copying/allocation. Keep the same snapshot
contents and independent writable state, and record copy CPU/bytes/time at
×1/4/8 without altering SQL/recovery semantics or implementing VFS/CoW yet.
This resolves whether the remaining storage bucket is avoidable copy work or
required runtime/engine work before choosing an optimization or architecture.
Nothing beyond that measurement is implemented here.
