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

## New canonical main measurement

**Status: pending CI acceptance and measurement. No new main p50/p95 is claimed.**

Dispatch `guest-build-boundary.yml` with `fast_tranche=true` on the exact pushed
main commit. One verified WASM feeds platform-specific AOT on macOS 15 arm64
and Ubuntu 24.04 x86_64 (SSE2+SSSE3). Source, toolchain, native hashes and original
build/reuse provenance are retained. Harness-only changes reuse exact artifacts;
this tranche changes guest inputs and therefore requires a new WASM/AOT once.

Before benchmarking, CI accepts matching native bundle and installed wheel from
outside the checkout, validates real auth callback/key behavior, and runs the
maintained lifecycle integration/race checks. The benchmark uses the packaged
native directory, Go public API, 1,000-row committed InnoDB fixture, 20 measured
samples plus two warmups, and ×1/4/8 isolation. It retains Start, Snapshot, Fork →
first SQL, SELECT/multi-client, caller/host/guest stages, and initialization CPU
markers. There are no performance thresholds and no expensive mapping diagnostics.

Outputs in the `initialization-<platform>-<commit>` Actions artifact:

- `init-fast-acceptance/`: exact package hashes, public-ref Go evidence,
  installed-wheel checks, key diagnostics, stdout/stderr/exit results.
- `init-fast-tranche.json`: raw samples, p50/p95, exact measured source/environment,
  guest/runtime identity, stages and sampled CPU/RSS observations.
- `init-fast-tranche-stages.md`, `init-fast-tranche-init.md`: measured waterfalls.
- AOT `provenance.json` and `manifest.json`.

Raw results stay ignored. After CI completes, append the actual run/commit and
both-platform ×1/4/8 tables here. Investigate/document any difference from the
experimental runs before claiming completion of the baseline checkpoint.

CPU sampling can miss startup/shutdown edges; current-thread/process stage CPU
is not per-component exclusive attribution. Sampled peak/incremental RSS is not
unique physical memory; shared mappings can be double-counted. No memory saving
is claimed: the separate Aria/cache mapping issue is unchanged.

## Next boundary

Restore remains the next FAST investigation, from this new main baseline on a
fresh `experiment/*` branch. Prior source-boundary evidence establishes an
expensive host-mounted/WASIX read path; pre-staging was an attribution probe,
not an accepted optimization. Choose no restore architecture until the new
baseline and its correctness checkpoint have completed. Framework dogfood
remains 0.3+.
