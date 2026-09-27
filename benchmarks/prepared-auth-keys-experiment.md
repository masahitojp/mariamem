# Prepared RSA keys: causal experiment

Branch: `experiment/prepared-auth-keys`. This is disposable experimental code,
not a production key-provisioning proposal. The paired experiment confirms RSA
key generation as the dominant authentication callback cost on both platforms.
It does not establish a production provisioning design.

## Source facts and setup

The pinned `plugin/auth_mysql_sha2/mysql_sha2.c::init_keys()` generates keys only
when both paths retain their default values, both files are absent, and
`auto_generate_rsa_keys` is enabled. It then calls `ssl_loadkeys()` regardless
of generation. `ssl_stuff.c::ssl_genkeys()` calls `EVP_RSA_gen(2048)` and writes
private and public PEM files. `ssl_loadkeys()` parses the private PEM, reads the
public PEM and installs the plugin's private/public key state. Upstream returns
success from `init_keys()` even when those helpers fail; ACTIVE alone is therefore
insufficient evidence of working RSA state.

The default relative files are `private_key.pem` and `public_key.pem`, resolved
from the guest working directory (not explicitly from `--datadir`). The explicit
experimental options remove that ambiguity:

```
--caching-sha2-password-private-key-path=/auth-keys/private.pem
--caching-sha2-password-public-key-path=/auth-keys/public.pem
```

`benchmarks/prepared_auth_keys.py` generates one disposable 2048-bit RSA pair
with OpenSSL, checks the private key and derives its public PEM before timing.
The host maps that temporary directory at `/auth-keys` only for existing-key runs.
No private key is committed or uploaded; only its hash is recorded, and setup
deletes the pair afterward. Input files must remain byte-identical across runs.

Both conditions use the same experimentally instrumented WASM/AOT. The separate
`guest/experimental.patch` adds success/failure events around the *unchanged*
generation predicate and both helper calls, plus the explicit startup options.
It does not disable the plugin or change cache defaults. Generation/load failure,
the wrong branch, absent diagnostics or collector overflow fails the experiment.
After first SQL (outside its latency interval), each startup also verifies the
plugin is ACTIVE and exposes a public key; existing-key runs require that key to
match the prepared PEM. This probe contributes to lifecycle CPU/RSS observations,
but not the measured first-SQL latency.

## Measurement protocol

Dispatch `guest-build-boundary.yml` on this branch with `auth_key_experiment=true`.
Linux builds the changed guest once. Both platform jobs use the existing immutable
WASM/AOT identity, hash and provenance verification, and never rebuild between
conditions. The workflow does not publish anything.

Each platform runs two warmup pairs, then 20 measured pairs, alternating A/B and
B/A order. Each condition invokes the canonical Go runner with one measurement,
the same 1,000-row/32-character fixture and first-SQL definitions, ×1/4/8, CPU/RSS
sampling and initialization diagnostics. This pairs complete runner invocations,
not simultaneous opposing conditions; each invocation prepares its own equivalent
fixture. Its canonical worker order remains 1/4/8. Per-DB observations within a
parallel batch are correlated; their quantiles are not independent trial counts.

Raw files and `summary.json` / `summary.md` are retained in the workflow's
`initialization-<platform>-<source-sha>` artifacts under
`benchmarks/results/init-auth-keys/`. The JSON contains commit, Go environment,
AOT provenance, test-key hashes, raw-file identities, branch-verification counts,
latency p50/p95 and callback/process/thread CPU/allocation/mapping summaries.
Compare each platform's paired conditions, not cross-platform absolute hardware
performance. Sampled CPU misses startup/exit edges; RSS double-counts shared pages.

## Authentication and semantic scope

Source fact: the existing embedded guest uses `--skip-grant-tables`; its public
SQL endpoint does not exercise a full caching_sha2_password authentication
exchange. This experiment preserves that behavior. Successful PEM parsing,
ACTIVE plugin and exact exposed public-key equality prove the load branch and
installed key identity, **not** end-to-end password/RSA challenge authentication.
There is no authentication bypass introduced by the experimental condition.
Production provisioning/security and a dedicated authentication exchange test
remain outside this causal measurement.

## Measured results

Run: https://github.com/masahitojp/mariamem/actions/runs/36284840859

Exact measured source: `25a02d2f516e77f749af68dfd16a263aeac3313a`.
Both jobs succeeded. macOS 15.7.9 arm64 had 3 reported CPUs; Ubuntu 24.04.5
x86_64 (6.17.0-1022-azure, glibc 2.39) had 4. Go 1.26.8, Wasmer 7.4.2,
MariaDB 13.1.0 embedded. Ubuntu AOT baseline remains SSE2 + SSSE3.

Artifact ZIP SHA256 values were checked against GitHub artifact digests before
extraction:

- macOS: `889442371e0f5a001f91b0b8d715a702d6710a61f8386a823dc31863b1b5edcc`
- Ubuntu: `780df2680a4096ff5e854d2b5ffbf24044a36d3d1be2b42aceb9c82ee886e4b1`

Both provenance records identify WASM
`5217a52112c28cd79925b41f462d1bd2bc758923b6d89ec3e3f1eaf9dc2cad65`.
Mac AOT: `c00d462ef9a1f5c520b6651ae00aad5661aca5c243c41ea42deedf917c86cef1`;
Ubuntu AOT: `c5667454f86d62cfb3a491493a5f75aa6d06511d170240698aac05d7c3b843e9`.
WASM was built once; each platform AOT was built once and verified before/after
A/B. Neither condition rebuilt artifacts.

### Branch proof and causality

Measured fact: 616 recorded startup/Fork checks per platform (including warmup)
passed: 308 control records generated keys successfully and then loaded them;
308 existing-key records loaded successfully without entering generation.
All public API startup probes verified ACTIVE status and a nonempty public key;
existing-key probes additionally verified exact prepared-public-key equality.
Seed startup is also checked by SQL probes but is not included in recorded
initialization samples. Raw branch evidence was revalidated after download.

Measured ×1 generation wall p50: macOS 664.878 ms; Ubuntu 612.094 ms.
Control load p50 was 0.122 / 0.101 ms; existing-key load was 0.633 / 0.538 ms.
Inference: removing generation, rather than bypassing plugin initialization,
explains almost all callback savings. The filesystem load itself is not free
and uses a mapped test directory in the experimental condition.

### Authentication callback

All values below are milliseconds, p50 / p95. CPU is measured inside the
guest callback; process CPU may include other threads. These are distributions
of 20 / 80 / 160 per-DB observations, not independent parallel batches.

| Platform | × | Condition | Wall | Process CPU | Current-thread CPU |
|---|---:|---|---:|---:|---:|
| macos | 1 | control | 665.05 / 1745.51 | 670.62 / 1405.94 | 660.10 / 1391.08 |
| macos | 1 | existing-keys | 0.64 / 1.59 | 0.91 / 2.91 | 0.56 / 1.01 |
| macos | 4 | control | 737.10 / 2110.71 | 536.66 / 1637.10 | 536.25 / 1635.91 |
| macos | 4 | existing-keys | 0.68 / 7.49 | 0.65 / 1.94 | 0.56 / 1.34 |
| macos | 8 | control | 1639.40 / 2968.21 | 652.25 / 1385.92 | 651.32 / 1383.20 |
| macos | 8 | existing-keys | 0.81 / 19.28 | 0.72 / 2.70 | 0.60 / 1.38 |
| ubuntu | 1 | control | 612.23 / 1341.36 | 612.36 / 1341.74 | 612.21 / 1341.27 |
| ubuntu | 1 | existing-keys | 0.55 / 0.60 | 0.51 / 1.24 | 0.36 / 0.41 |
| ubuntu | 4 | control | 1118.48 / 1941.11 | 1053.97 / 1824.07 | 1034.51 / 1819.52 |
| ubuntu | 4 | existing-keys | 1.14 / 8.35 | 0.70 / 5.53 | 0.47 / 0.54 |
| ubuntu | 8 | control | 1991.51 / 3214.53 | 973.21 / 2020.67 | 965.18 / 2019.32 |
| ubuntu | 8 | existing-keys | 2.83 / 13.11 | 0.76 / 6.76 | 0.49 / 0.57 |

### Enclosing initialization and end-to-end Fork

Wall milliseconds, p50 / p95. Fork per-DB values preserve the first successful
COUNT readiness definition. Batch values measure completion of all workers.
Differences of percentiles below are descriptive, not paired-effect estimates.

| Platform | × | Condition | Post-srv plugins | Embedded init | Fork per DB | Fork batch |
|---|---:|---|---:|---:|---:|---:|
| macos | 1 | control | 675.49 / 1759.06 | 753.47 / 1860.65 | 1321.4 / 2398.6 | 1321.4 / 2398.6 |
| macos | 1 | existing-keys | 11.01 / 22.18 | 107.90 / 130.75 | 648.6 / 789.6 | 648.6 / 789.6 |
| macos | 4 | control | 769.25 / 2119.97 | 992.52 / 2393.50 | 1978.6 / 3310.6 | 2547.5 / 3813.5 |
| macos | 4 | existing-keys | 14.15 / 40.81 | 221.21 / 356.37 | 1214.4 / 1883.6 | 1291.2 / 1897.9 |
| macos | 8 | control | 1650.82 / 2987.74 | 2049.07 / 3582.53 | 3776.4 / 5767.0 | 4399.6 / 6093.9 |
| macos | 8 | existing-keys | 18.15 / 74.36 | 418.87 / 810.45 | 1938.9 / 3133.9 | 2211.4 / 3152.7 |
| ubuntu | 1 | control | 623.19 / 1350.94 | 693.66 / 1446.09 | 1236.2 / 1981.5 | 1236.3 / 1981.5 |
| ubuntu | 1 | existing-keys | 10.94 / 14.23 | 92.70 / 106.30 | 640.5 / 661.3 | 640.5 / 661.3 |
| ubuntu | 4 | control | 1143.56 / 1973.98 | 1289.61 / 2100.33 | 2000.3 / 2864.6 | 2462.0 / 3450.9 |
| ubuntu | 4 | existing-keys | 24.60 / 41.62 | 147.25 / 192.75 | 837.2 / 935.9 | 894.5 / 974.4 |
| ubuntu | 8 | control | 2038.99 / 3253.59 | 2225.36 / 3525.35 | 3494.9 / 4723.8 | 4296.4 / 5997.4 |
| ubuntu | 8 | existing-keys | 39.19 / 79.59 | 231.09 / 340.22 | 1512.2 / 1639.1 | 1618.6 / 1702.1 |

Derived paired batch-latency savings (control minus existing-key, median of
20 matched invocation differences): macOS ×1/4/8 = **671.0 / 1298.9 / 2246.0 ms**;
Ubuntu = **606.8 / 1533.9 / 2661.1 ms**. This is distinct from subtracting table
medians. The same paired calculation for callback process CPU gives macOS
×1/4/8 = **667.3 / 515.1 / 622.1 ms** and Ubuntu
**611.9 / 1095.1 / 1040.4 ms**; parallel values compare within-batch callback
medians rather than total batch CPU. See raw paired arrays for uncertainty.

Measured Start→SQL p50/p95: macOS control 1064.0/1429.6 ms versus existing keys
560.9/616.5 ms; Ubuntu 919.9/1495.5 versus 360.9/382.6 ms.

Inference: the strong callback and end-to-end reduction holds on both platforms
and substantially reduces ×4/×8 cost. It does not remove concurrency degradation:
existing-key per-DB Fork p50 still rises from 649 to 1939 ms on macOS and from
640 to 1512 ms on Ubuntu. These hosted machines are not equivalent hardware.

### Memory, CPU accounting and macOS job duration

Measured mapping balances are unchanged in both conditions at every worker count:
Aria main page cache **124.2265625 MiB**, post-srv plugins **126.15625 MiB**,
complete embedded init **242.2392578125 MiB**. Auth callback net mapping delta
remains zero. This experiment removes latency/CPU, not Aria mapping growth.

Sampled peak runtime-tree RSS divided by worker count (MiB, median):

| Platform | Condition | ×1 | ×4 | ×8 |
|---|---|---:|---:|---:|
| macOS | control | 338.7 | 344.1 | 337.0 |
| macOS | existing keys | 336.6 | 343.6 | 337.0 |
| Ubuntu | control | 406.2 | 400.7 | 400.8 |
| Ubuntu | existing keys | 410.8 | 404.5 | 402.1 |

This is aggregate sampled RSS divided by workers, not unique physical memory or
a precise incremental allocation. There is no demonstrated material RSS saving.
Mac sampled batch descendant CPU p50 falls from 1.055/4.745/9.165 seconds to
0.450/2.250/3.775 at ×1/4/8. Ubuntu `ps` CPU values have coarse whole-second
granularity: ×1 is zero in both conditions; zero is not proof of zero CPU.
Use callback CPU clocks above for causal CPU attribution.

Measured post-ready diagnostics explain much of the longer macOS job: across
measured records, control/existing diagnostic totals were **302.69/307.74 seconds**
on macOS versus **2.35/2.56 seconds** on Ubuntu. Mac per-process diagnostic p50
was ~1.07 seconds (p95 1.32/1.42); Ubuntu ~0.008/0.009 seconds.
Mac uses `vmmap` + `ps -M`; Ubuntu reads `/proc`. These diagnostics run after
first SQL with sampling stopped, outside the reported readiness latency, but
extend how long parallel instances stay alive before cleanup. Warmup costs are
not included in these totals. The diagnostic difference is directly measured;
the exact split between individual diagnostic commands is not recorded.

### Remaining unknowns

- A full caching_sha2_password challenge/password exchange was not tested;
  existing embedded grant bypass is unchanged. Key provisioning security and
  compatibility need a separate design before integration.
- This experiment does not attribute remaining runtime initialization, validation,
  restore, or memory cost. No production integrity/cache changes were made.
- Random RSA generation has a wide tail. Twenty paired trials support the large
  effect, not a precise portable performance guarantee. No diagnostic-off A/B
  control was added, and all measurements retain sampling/instrumentation.

## Implication for 0.2 architecture

RSA generation hypothesis: **confirmed for these measured guests**. The next
smallest probe should focus on a cold-start/prepared-state key arrangement that
preserves the real plugin and makes its security/lifetime explicit. Do not
productionize this disposable mapped-key setup automatically.

Continuation is no longer justified solely by the former 600–800 ms auth init
bucket: existing-key embedded init ×1 is ~108 ms macOS / 93 ms Ubuntu. However,
Fork→SQL remains ~640–649 ms p50 and above the exploratory 250/500 ms p50/p95
targets, with hundreds of MiB per DB and substantial concurrency degradation.
After the small key probe, reattribute the remaining path before deciding between
further cold-start work, initialized-state continuation and storage/runtime
sharing. No production architecture is chosen, and nothing is merged to main.
