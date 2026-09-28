# First production FAST tranche

## Scope and evidence

Main adopts two experimentally established changes, without merging exploratory
history or changing restore:

- **Prepared public test RSA keys:** `caching_sha2_password` stays enabled; it
  loads a valid fixed pair instead of generating RSA-2048 keys on each startup.
- **Within-call verified native identity:** Go carries its already-hashed AOT
  identity through one startup, removing two repeated AOT scans. Every startup
  still verifies manifest/runtime/AOT/sidecar and snapshot integrity. Python's
  independent host-process validation remains.

The key fixture and source preparation are described in
[development](../docs/development.md#first-fast-tranche-prepared-authentication-keys-and-startup-validation).
The source-mounted snapshot → guest-memory copy, 64 KiB chunks, file inventory,
redo/undo sizes, engine caches and Snapshot/Fork semantics are unchanged.
No `guest/experimental.patch`, experimental runtime flags, pre-staging or
experimental trust cache enters production provenance.

## Historical comparison — not new main measurements

| Condition | Platform | Fork ×1 → first SQL p50 | Attribution |
| --- | --- | ---: | --- |
| Original canonical Go baseline | macOS arm64 | 1,224 ms | MariaDB init 762 ms; restore 156 ms; host validation 138 ms |
| Prepared keys, ordinary validation | macOS arm64 | ~649 ms | Authentication callback ~665 → ~0.64 ms; embedded init ~753 → ~108 ms |
| Prepared keys, ordinary validation | Ubuntu x86_64 | ~640 ms | Authentication callback ~612 → ~0.55 ms; embedded init ~694 → ~93 ms |
| Prepared keys + experimental within-call reuse | macOS arm64 | ~485 ms | Remaining preparation ~164 ms; restore ~156 ms |
| Prepared keys + experimental within-call reuse | Ubuntu x86_64 | ~532 ms | Restore is the largest remaining measured interval |

These are **historical measurements**, from different runs; they are neither
production acceptance nor same-run speedup ratios. Do not add component medians
or compare hosted platforms as equivalent hardware. Original data/limitations:
[FAST baseline](fast-baseline-analysis.md), [initialization investigation](mariadb-init-investigation.md).
The prepared-key and validation A/B reports remain on `experiment/prepared-auth-keys`;
that branch is evidence, not production source.

## Accepted canonical main baseline

[Run 36314985195](https://github.com/masahitojp/mariamem/actions/runs/36314985195)
completed successfully for exact source
`d44157adbc527da6482e205c176616489cb3ccbc` (clean checkout). Measurements used
macOS 15.7.9 arm64 / 3 visible CPUs and Ubuntu 24.04.5 x86_64 / 4 visible CPUs,
Go 1.26.8, Python 3.14.7, Wasmer 7.4.2 and MariaDB 13.1.0 embedded.
Ubuntu AOT uses SSE2+SSSE3. These hosted machines are not equivalent hardware.
The benchmark used 1,000 rows, 20 trials plus two warmups, ×1/4/8, 100 steady
queries and two SQL clients; initialization/stage diagnostics were enabled,
expensive memory diagnostics were disabled. No timing threshold was enforced.

### Verified acceptance and identities

**Measured fact:** both platform jobs passed packaged acceptance, the maintained
Go race/Python lifecycle integration, and the baseline. Each external Go module
resolved the exact remote candidate with no local replace. Isolated installed
wheel tests exercised Snapshot/Fork, multiple clients, reconnect, ordinary SQL,
interrupted-query invalidation, cleanup and startup diagnostics. Direct packaged
guest checks accepted the real full-auth callback and rejected missing/corrupt
keys. Both public APIs observed the enabled plugin and expected public key.
Successful callback acceptance records `generated=false`; normal startup also fails closed unless
keys loaded without generation. This is callback/key correctness, not a claim
of full public network account/grant authentication: grant bypass is unchanged.

The accepted archive/wheel shared runtime/AOT/sidecar hashes reconcile with the
benchmark manifest and AOT provenance. Both AOT records identify the same WASM:
`41e3acfb51fe52ad13d9691de0bd3f05619266571e84dd1a0ddf263e082add7f`.
These are measurement packages labeled 0.1.0, **not** replacements for the
published 0.1.0 release; nothing was published.

| Platform | Checked package | SHA256 from exact-artifact acceptance |
| --- | --- | --- |
| macOS | `mariamem-native-darwin-arm64.tar.gz` | `5b9061580cb9cf57bc9d5a2d0bd85ba1ec037f33060f3855619cdc83f600b8a6` |
| macOS | `mariamem-0.1.0-py3-none-macosx_15_0_arm64.whl` | `e1f83afcacf57361484b1cdd13c1392baff000be593a9fa51b9244ce08528583` |
| Ubuntu | `mariamem-native-ubuntu24.04-x86_64.tar.gz` | `312fc209823e6734799bd622198c712386ab89eb9f26a2e22c72e88b06a1e940` |
| Ubuntu | `mariamem-0.1.0-py3-none-linux_x86_64.whl` | `ec6436afb4a57903516b89680cd04cc3ba5a2a07d529810be7c6c769c2ffafaa` |

Raw evidence/result JSON stays ignored in `benchmarks/results/fast-tranche-d44157a/`.
Actions artifacts are named `initialization-<platform>-d44157adbc527da6482e205c176616489cb3ccbc`
with 30-day retention. `init-fast-acceptance/acceptance.json` retains step results,
package/source identities and logs; `init-fast-tranche.json` retains raw samples.
Downloaded benchmark JSON identities:

- macOS: `25c37357cd81729a57ac8bf04cca240d9f4975fff9caed3db96697f2b4a20ecd`
- Ubuntu: `be935955393dd88be542eaa1b60dadd746f14d1eb37b6c5db8fdf1b142e5b099`

### End-to-end latency

All entries are **p50 / p95 in ms**. Fork latency pools the per-instance samples
(20 / 80 / 160 at ×1/4/8); batch-ready measures the last DB in each of 20 groups.
They are different metrics. Percentiles are recomputable from retained raw data.

| Case | macOS | Ubuntu |
| --- | ---: | ---: |
| Start → first SQL | 443.9 / 520.9 | 268.0 / 300.1 |
| Snapshot | 773.3 / 873.6 | 634.5 / 648.4 |
| Fork ×1 → first SQL | 516.9 / 688.7 | 539.2 / 566.4 |
| Fork ×4 → first SQL per DB | 809.5 / 1047.6 | 734.8 / 807.1 |
| Fork ×8 → first SQL per DB | 1791.7 / 2129.9 | 1289.1 / 1404.6 |
| Steady SELECT 1 | 0.4 / 0.8 | 0.4 / 0.4 |
| Two-client SELECT 1 | 0.4 / 0.8 | 0.4 / 0.6 |
| Fork ×4 batch-ready | 854.6 / 1083.2 | 783.4 / 812.4 |
| Fork ×8 batch-ready | 1975.7 / 2232.2 | 1390.9 / 1496.3 |

### Fork waterfall and concurrency

p50 / p95 ms. Nested host/guest intervals overlap; **do not add percentile
columns**. Preparation outside host startup is a per-instance derived duration:
caller begin→Database return minus host begin→end. It includes public validation
and other caller preparation, not exclusively hashing. Combined preparation is
computed per instance before taking percentiles, rather than adding medians.
Host metadata/snapshot validation still performs mandatory snapshot verification.

| Platform | DBs | Before-host preparation (derived) | Host validation | Combined preparation (derived) | Guest restore | MariaDB init | Unobserved startup envelope |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| macOS | 1 | 65.0 / 86.7 | 93.5 / 126.6 | 159.1 / 206.2 | 196.5 / 266.5 | 82.7 / 131.1 | 65.0 / 93.0 |
| macOS | 4 | 102.9 / 145.7 | 147.7 / 291.6 | 255.3 / 410.6 | 229.8 / 377.9 | 171.2 / 260.5 | 94.8 / 228.3 |
| macOS | 8 | 216.6 / 346.6 | 318.0 / 774.4 | 548.5 / 1007.2 | 495.7 / 774.0 | 364.3 / 637.1 | 235.9 / 387.3 |
| Ubuntu | 1 | 65.8 / 66.3 | 104.7 / 105.0 | 170.5 / 171.0 | 230.5 / 245.5 | 88.5 / 106.3 | 42.5 / 44.2 |
| Ubuntu | 4 | 71.7 / 81.7 | 117.0 / 130.6 | 191.1 / 206.6 | 298.7 / 419.0 | 143.2 / 182.6 | 69.2 / 85.3 |
| Ubuntu | 8 | 137.6 / 197.6 | 236.1 / 303.7 | 377.9 / 458.6 | 510.3 / 682.0 | 226.9 / 306.0 | 132.7 / 189.0 |

**Measured fact:** restore is the largest individual recorded Fork ×1 interval
on both platforms (196 / 231 ms p50), followed by combined preparation (159 /
170 ms, derived). MariaDB init is now 83 / 89 ms rather than the historical
762 ms cold RSA-generation bucket. The auth callback remains under 1 ms even
at ×8. At ×8, restore is 496 / 510 ms; macOS combined preparation rises to
549 ms and Ubuntu to 378 ms. Restore and preparation remain material, alongside
MariaDB wall-time growth (364 / 227 ms). Spawn ×1 is only 1.86 / 0.29 ms.

Cold Start differs from prepared Fork: its recorded MariaDB init p50 is 295 ms
on macOS and 151 ms on Ubuntu. A new data directory and an existing prepared
snapshot exercise different initialization work; no RSA regeneration is observed.
Snapshot remains costly: export acknowledgement p50 316 / 269 ms and host publish
348 / 252 ms. Those intervals combine multiple operations, not physical disk I/O.

The startup envelope (65 / 42 ms at ×1, 236 / 133 at ×8) remains unassigned:
pre-main WASIX/AOT/CRT work, ready delivery, diagnostic output and scheduling
are not split. It is not a measured Wasmer-only cost. Client connection ×1
p50 is about 6.3 ms on both platforms; first SQL about 1.1 / 0.9 ms.

### CPU and RSS observations

CPU table entries are p50 in ms. Embedded-init process CPU includes other guest
threads; thread CPU is the initializing thread. Runner CPU is per batch, includes
the Go host/harness and collection/hold/cleanup, and is not exclusive validation
CPU. No per-stage CPU is inferred for restore or host validation.

| Platform | DBs | Embedded init wall | Init thread CPU | Init process CPU | RSA callback wall | Runner batch CPU |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| macOS | 1 | 82.58 | 48.65 | 88.07 | 0.42 | 176.23 |
| macOS | 4 | 171.05 | 48.61 | 109.45 | 0.36 | 679.98 |
| macOS | 8 | 364.13 | 59.70 | 120.98 | 0.38 | 1380.91 |
| Ubuntu | 1 | 88.40 | 38.83 | 99.90 | 0.21 | 184.96 |
| Ubuntu | 4 | 143.09 | 52.63 | 118.69 | 0.33 | 754.56 |
| Ubuntu | 8 | 226.64 | 53.68 | 120.65 | 0.33 | 1509.37 |

**Inference:** wall-time growth exceeds initialization-thread CPU growth,
consistent with concurrency scheduling/contention rather than repeated RSA CPU.
It does not quantify waiting or identify a specific runtime bottleneck.
Sampled macOS descendant CPU per batch p50 is 365 / 1,545 / 3,460 ms at ×1/4/8;
Ubuntu reports zero at these boundaries because `ps` CPU accounting is coarse.
Those zeros do **not** mean no CPU work; use the nonzero embedded CPU clocks above.
Sampling can miss startup/shutdown edges and cannot support complete CPU accounting.

Sampled incremental ready RSS per DB p50 is 333 / 342 / 342 MiB on macOS and
405 / 401 / 400 MiB on Ubuntu at ×1/4/8. This is observed RSS, not unique physical
allocation; shared mappings can be counted repeatedly. No expensive mapping
analysis was repeated. The tranche removes latency/CPU work, not the Aria/cache
mapping issue, and does not yet deliver cheap memory isolation.

**Resource-baseline update:** the later corrected 128 MiB Aria control provides
the current comparable CPU and incremental-memory measurements. Use its combined
host/runtime CPU and macOS physical-footprint / Ubuntu PSS values in
[the post-Aria FAST note](fast-gap-after-aria.md); treat this report's RSS and
runner-CPU figures as historical. The accepted latency baseline above remains
the canonical production reference; the newer Aria control is diagnostic and
does not replace it.

### Interpretation and next checkpoint

**Historical comparison (derived):** macOS ×1 p50 517 ms is about 58% below the
original 1,224 ms canonical baseline. It is ~7% above the exploratory prepared-key
+ validation result (~485 ms); Ubuntu 539 ms is ~1% above ~532 ms. These runs are
not paired controls, so percentages describe historical numbers, not a controlled
causal estimate. Main's macOS preparation is similar (~159 vs ~164 ms), restore
is higher (~196 vs ~156 ms) and MariaDB init lower (~83 vs ~108 ms). These
component medians cannot explain an exact end-to-end delta. Hosted scheduling,
diagnostics and run conditions remain confounders; no production restore change
was introduced to explain the variation. Ubuntu's main init (~89 vs ~93 ms)
and end-to-end latency are close to the exploratory values.

The independent earlier A/B experiments establish the causality of the two
adopted changes; this run establishes their production correctness and the new
baseline. The exploratory FAST target (p50 <250 ms / p95 <500 ms) is still unmet
at ×1 and concurrency increases cost substantially. Keys and redundant native
validation are closed for this tranche. Restore is the next active investigation
on a fresh experiment branch; no storage/runtime architecture is chosen here.

## Next boundary

Restore remains the next FAST investigation, from this new main baseline on a
fresh `experiment/*` branch. Prior source-boundary evidence establishes an
expensive host-mounted/WASIX read path; pre-staging was an attribution probe,
not an accepted optimization. The next probe should use this accepted main
baseline; no restore architecture is selected here. Framework dogfood remains 0.3+.
